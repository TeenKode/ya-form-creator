import { TYPES, FORMATS, optionLabel, exclusiveOptions } from "./core.mjs";
import { checked, nextSlug, replaceQuestion } from "./editor-model.mjs";
import { analyzeLogic, applySuggestions } from "./logic-analyzer.mjs";

const $ = (id) => document.getElementById(id);
const ENUM = ["radio", "checkbox", "dropdown", "scale", "stars", "onerow"];
const SOURCES = ["radio", "checkbox", "dropdown"];
const BLOCKS = ["section", "comment"];
const lines = (value) =>
  value
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
function node(tag, text, className) {
  const el = document.createElement(tag);
  el.textContent = text;
  if (className) el.className = className;
  return el;
}
function button(label, callback) {
  const el = node("button", label, "secondary");
  el.type = "button";
  el.addEventListener("click", callback);
  return el;
}
function dialog(id, title, body) {
  const el = document.createElement("dialog");
  el.id = id;
  el.className = "editor-dialog";
  const close = button("×", () => el.close());
  close.className = "dialog-close quiet";
  close.setAttribute("aria-label", "Закрыть");
  el.append(close, node("h2", title));
  const content = document.createElement("div");
  content.innerHTML = body;
  el.append(content);
  document.body.append(el);
  return el;
}
function options(select, values, value) {
  select.replaceChildren(
    ...values.map(([code, label]) => new Option(label, code)),
  );
  if (value !== undefined) select.value = value;
}
function showGroup(id, visible) {
  const el = $(id);
  el.hidden = !visible;
  for (const input of el.querySelectorAll("input,select,textarea"))
    input.disabled = !visible;
}
function put(id, value) {
  $(id).value = value ?? "";
}
function numeric(q, key, id) {
  const raw = $(id).value.trim();
  if (!raw) delete q[key];
  else q[key] = Number(raw);
}
function retainLabels(raw, old = []) {
  return lines(raw).map((label) =>
    structuredClone(old.find((o) => optionLabel(o) === label) ?? label),
  );
}

export function installEditor({ getConfig, commit, notice }) {
  let editing = null,
    original = {},
    conditionDraft = [],
    editingCondition = null;
  const questionForm = $("questionForm");
  options($("qType"), Object.entries(TYPES));
  options($("qFormat"), Object.entries(FORMATS));
  const fields = document.createElement("div");
  fields.innerHTML = `
    <div id="qIdentity"><label>Код вопроса<input id="qSlug" pattern="[A-Za-z][A-Za-z0-9_-]*" required></label></div>
    <label>Подсказка к вопросу<textarea id="qComment" rows="2"></textarea></label>
    <div id="qTextFields"><label class="check"><input id="qMultiline" type="checkbox">Многострочный ответ</label>
      <label>Текст внутри пустого поля<input id="qPlaceholder"></label>
      <div class="editor-grid"><label>Минимальная длина<input id="qMinLength" type="number" min="0" step="1"></label><label>Максимальная длина<input id="qMaxLength" type="number" min="0" step="1"></label></div></div>
    <div id="qBounds" class="editor-grid"><label>Минимум<input id="qMin"></label><label>Максимум<input id="qMax"></label></div>
    <div id="qMatrix"><label>Строки матрицы, каждая с новой строки<textarea id="qRows" rows="4"></textarea></label><label>Столбцы матрицы, каждый с новой строки<textarea id="qColumns" rows="4"></textarea></label></div>
    <div id="qOtherFields"><label class="check"><input id="qOther" type="checkbox">Добавить поле «Другое»</label>
      <div id="qOtherDetails"><label>Вариант, открывающий поле<input id="qOtherOption" placeholder="Другое"></label><label>Название дополнительного поля<input id="qOtherLabel" placeholder="Укажите свой вариант"></label></div></div>
    <div id="qExclusiveFields"><label>Исключающие варианты, каждый с новой строки<textarea id="qExclusive" rows="3"></textarea></label>
      <label class="check"><input id="qExclusiveAuto" type="checkbox">Определять исключающие варианты автоматически</label><p class="tiny">Например, «Не использую» исключает остальные ответы. Для списка нужны минимум два обычных варианта.</p></div>
    <div id="qApi"><label>Payload расширенного API<textarea id="qPayload" rows="8" spellcheck="false"></textarea></label></div>
    <details id="questionJsonDetails"><summary>JSON вопроса</summary><p>Для дополнительных параметров API и вариантов с баллами. Кнопка заменяет вопрос целиком.</p><textarea id="questionJson" rows="10" aria-label="JSON вопроса" spellcheck="false"></textarea><button id="applyQuestionJson" type="button" class="secondary">Применить JSON вопроса</button></details>`;
  questionForm.querySelector("button[type=submit]").before(fields);
  $("questionDialog").classList.add("editor-dialog");
  $("questionError").setAttribute("role", "alert");

  function controls() {
    const type = $("qType").value;
    showGroup("formatLabel", type === "text");
    showGroup("optionsLabel", ENUM.includes(type));
    showGroup("choiceLimits", type === "checkbox");
    showGroup("qIdentity", !BLOCKS.includes(type));
    showGroup("qTextFields", type === "text");
    showGroup("qBounds", ["integer", "date"].includes(type));
    showGroup("qMatrix", type === "matrix");
    showGroup("qOtherFields", SOURCES.includes(type));
    showGroup("qExclusiveFields", type === "checkbox");
    showGroup("qApi", type === "api");
    $("qRequired").disabled = BLOCKS.includes(type);
    $("qRequired").closest("label").hidden = BLOCKS.includes(type);
    $("qMultiline").disabled =
      type !== "text" || $("qFormat").value !== "plain";
    if ($("qMultiline").disabled) $("qMultiline").checked = false;
    for (const id of ["qMin", "qMax"]) {
      $(id).type = type === "date" ? "date" : "number";
      $(id).step = "1";
    }
    showGroup("qOtherDetails", SOURCES.includes(type) && $("qOther").checked);
    $("qExclusive").disabled =
      type !== "checkbox" || $("qExclusiveAuto").checked;
  }
  for (const id of ["qType", "qFormat", "qOther", "qExclusiveAuto"])
    $(id).addEventListener("change", controls);

  function collect() {
    const type = $("qType").value,
      sameType = original.type === type;
    // Retain advanced properties for unchanged types. Changing type starts a clean type contract.
    const q = sameType ? structuredClone(original) : {};
    q.type = type;
    q.label = $("qLabel").value.trim();
    if (!BLOCKS.includes(type)) {
      q.slug = $("qSlug").value.trim();
      q.required = $("qRequired").checked;
    } else {
      delete q.slug;
      delete q.required;
    }
    if ($("qComment").value.trim()) q.comment = $("qComment").value.trim();
    else delete q.comment;
    if (type === "text") {
      q.format = $("qFormat").value;
      q.multiline = q.format === "plain" && $("qMultiline").checked;
      if ($("qPlaceholder").value.trim())
        q.placeholder = $("qPlaceholder").value.trim();
      else delete q.placeholder;
      numeric(q, "min_length", "qMinLength");
      numeric(q, "max_length", "qMaxLength");
    }
    if (ENUM.includes(type))
      q.options = retainLabels(
        $("qOptions").value,
        sameType ? original.options : [],
      );
    if (type === "checkbox") {
      numeric(q, "min_choices", "qMinChoices");
      numeric(q, "max_choices", "qMaxChoices");
      if ((q.min_choices ?? 0) > (q.max_choices ?? Infinity))
        throw new Error("Минимум ответов не может быть больше максимума.");
      if ($("qExclusiveAuto").checked) delete q.exclusive_options;
      else q.exclusive_options = lines($("qExclusive").value);
    }
    if (type === "matrix") {
      q.rows = retainLabels($("qRows").value, sameType ? original.rows : []);
      q.columns = retainLabels(
        $("qColumns").value,
        sameType ? original.columns : [],
      );
    }
    if (["integer", "date"].includes(type))
      for (const [key, id] of [
        ["min", "qMin"],
        ["max", "qMax"],
      ]) {
        if (type === "integer") numeric(q, key, id);
        else if ($(id).value) q[key] = $(id).value;
        else delete q[key];
      }
    if (SOURCES.includes(type) && $("qOther").checked) {
      q.other = {
        ...(original.other ?? {}),
        option: $("qOtherOption").value.trim() || "Другое",
        label: $("qOtherLabel").value.trim() || "Укажите свой вариант",
      };
      if (!q.options.some((o) => optionLabel(o) === q.other.option))
        q.options.push(q.other.option);
    } else delete q.other;
    if (type === "api") {
      q.payload = JSON.parse($("qPayload").value);
      if (
        q.payload &&
        typeof q.payload === "object" &&
        !Array.isArray(q.payload)
      )
        q.payload.slug = q.slug;
    }
    return q;
  }
  function saveQuestion(q) {
    const config = getConfig();
    if (editing === null) {
      const next = structuredClone(config);
      next.questions.push(q);
      commit(checked(next));
    } else commit(replaceQuestion(config, editing, q));
    $("questionDialog").close();
    notice(editing === null ? "Вопрос добавлен." : "Изменения сохранены.");
  }
  function openQuestion(index = null) {
    editing = index;
    questionForm.reset();
    $("questionError").textContent = "";
    original = structuredClone(
      index === null ? {} : getConfig().questions[index],
    );
    const q = original;
    $("qType").disabled = false;
    put("qType", q.type ?? "text");
    put("qLabel", q.label);
    put("qSlug", q.slug ?? nextSlug(getConfig()));
    put("qComment", q.comment);
    $("qRequired").checked = q.required ?? false;
    put("qFormat", q.format ?? "plain");
    $("qMultiline").checked = q.multiline ?? (q.format ?? "plain") === "plain";
    put("qPlaceholder", q.placeholder);
    put("qOptions", (q.options ?? []).map(optionLabel).join("\n"));
    put("qMinChoices", q.min_choices);
    put("qMaxChoices", q.max_choices);
    put("qMinLength", q.min_length);
    put("qMaxLength", q.max_length);
    put("qRows", (q.rows ?? []).map(optionLabel).join("\n"));
    put("qColumns", (q.columns ?? []).map(optionLabel).join("\n"));
    $("qOther").checked = !!q.other;
    put("qOtherOption", q.other?.option ?? "Другое");
    put("qOtherLabel", q.other?.label ?? "Укажите свой вариант");
    $("qExclusiveAuto").checked = q.exclusive_options === undefined;
    put("qExclusive", exclusiveOptions(q).join("\n"));
    put("qPayload", JSON.stringify(q.payload ?? { type: "string" }, null, 2));
    $("questionJsonDetails").open = false;
    put(
      "questionJson",
      JSON.stringify(
        q.type
          ? q
          : {
              type: "text",
              slug: $("qSlug").value,
              label: "",
              multiline: true,
            },
        null,
        2,
      ),
    );
    controls();
    put("qMin", q.min);
    put("qMax", q.max);
    $("questionDialog").querySelector("h2").textContent =
      index === null ? "Новый вопрос" : "Редактировать вопрос";
    questionForm.querySelector("button[type=submit]").textContent =
      index === null ? "Добавить в анкету" : "Сохранить изменения";
    $("questionDialog").showModal();
    $("qLabel").focus();
  }
  questionForm.addEventListener("submit", (e) => {
    e.preventDefault();
    try {
      saveQuestion(collect());
    } catch (e) {
      $("questionError").textContent = e.message;
    }
  });
  $("questionJsonDetails")
    .querySelector("summary")
    .addEventListener("click", () => {
      if (!$("questionJsonDetails").open)
        try {
          put("questionJson", JSON.stringify(collect(), null, 2));
        } catch (e) {
          $("questionError").textContent = e.message;
        }
    });
  $("applyQuestionJson").addEventListener("click", () => {
    try {
      saveQuestion(JSON.parse($("questionJson").value));
    } catch (e) {
      $("questionError").textContent = e.message;
    }
  });

  const settings = dialog(
    "formSettingsDialog",
    "Параметры анкеты",
    `<form id="formSettingsForm">
    <label>Название формы<input id="settingsName" required></label><label>Текст кнопки отправки<input id="settingsSubmit"></label>
    <label>Заголовок после отправки<input id="settingsTitle"></label><label>Подзаголовок после отправки<input id="settingsSubtitle"></label>
    <label class="check"><input id="settingsMultiple" type="checkbox">Разрешить повторные ответы</label><label class="check"><input id="settingsAuth" type="checkbox">Требовать авторизацию</label>
    <label class="check"><input id="settingsPublish" type="checkbox">Предлагать публикацию сразу</label><p>Публикация всегда подтверждается отдельно в расширении. Анонимный доступ зависит также от настроек Яндекса.</p>
    <p id="settingsError" role="alert"></p><button type="submit" class="primary">Сохранить параметры</button></form>`,
  );
  function openSettings() {
    const f = getConfig().form;
    put("settingsName", f.name);
    put("settingsSubmit", f.submit_text ?? "Отправить");
    put("settingsTitle", f.success_title ?? "Спасибо за ответы!");
    put("settingsSubtitle", f.success_subtitle);
    $("settingsMultiple").checked = f.allow_multiple_answers ?? true;
    $("settingsAuth").checked = f.need_auth ?? false;
    $("settingsPublish").checked = f.publish_by_default ?? false;
    $("settingsError").textContent = "";
    settings.showModal();
  }
  $("formSettingsForm").addEventListener("submit", (e) => {
    e.preventDefault();
    try {
      const next = structuredClone(getConfig());
      Object.assign(next.form, {
        name: $("settingsName").value.trim(),
        submit_text: $("settingsSubmit").value,
        success_title: $("settingsTitle").value,
        success_subtitle: $("settingsSubtitle").value,
        allow_multiple_answers: $("settingsMultiple").checked,
        need_auth: $("settingsAuth").checked,
        publish_by_default: $("settingsPublish").checked,
      });
      commit(checked(next));
      settings.close();
      notice("Параметры анкеты сохранены.");
    } catch (e) {
      $("settingsError").textContent = e.message;
    }
  });

  const conditions = dialog(
    "conditionsDialog",
    "Условия показа",
    `<p>Все правила для одного вопроса должны выполняться одновременно. Источник должен находиться раньше зависимого вопроса.</p>
    <div id="conditionList"></div><form id="conditionForm"><label>Предыдущий вопрос<select id="conditionSource"></select></label><label>Зависимый вопрос<select id="conditionTarget"></select></label>
    <label>Сравнение<select id="conditionCompare"><option value="eq">Выбраны ответы</option><option value="neq">Не выбраны ответы</option></select></label>
    <fieldset id="conditionAnswers"><legend>Ответы предыдущего вопроса</legend></fieldset><label>Соединение ответов<select id="conditionOperator"><option value="and">Все выбранные ответы (И)</option><option value="or">Хотя бы один ответ (ИЛИ)</option></select></label>
    <div class="editor-actions"><button id="addCondition" type="submit" class="secondary">Добавить условие</button><button id="cancelConditionEdit" type="button" class="quiet" hidden>Отменить редактирование</button></div></form>
    <p id="conditionError" role="alert"></p><button id="saveConditions" class="primary" type="button">Сохранить условия</button>`,
  );
  function sourceChanged(selectedTarget, selectedAnswers = []) {
    const config = getConfig(),
      index = config.questions.findIndex(
        (q) => q.slug === $("conditionSource").value,
      ),
      source = config.questions[index];
    const targets = [];
    config.questions.forEach((q, i) => {
      if (i > index && q.slug && !BLOCKS.includes(q.type))
        targets.push([q.slug, q.label]);
      if (i >= index && q.other)
        targets.push([
          q.other.slug ?? q.slug + "_other",
          (q.other.label ?? "Укажите свой вариант") + " — " + q.label,
        ]);
    });
    options($("conditionTarget"), targets, selectedTarget);
    if (!$("conditionTarget").value && targets.length)
      $("conditionTarget").selectedIndex = 0;
    const answers = $("conditionAnswers");
    answers.replaceChildren(node("legend", "Ответы предыдущего вопроса"));
    for (const opt of source?.options ?? []) {
      const value = optionLabel(opt),
        label = node("label", "", "check"),
        input = document.createElement("input");
      input.type = "checkbox";
      input.value = value;
      input.checked = selectedAnswers.includes(value);
      label.append(input, document.createTextNode(value));
      answers.append(label);
    }
    $("addCondition").disabled = !source || !targets.length;
  }
  function resetCondition() {
    editingCondition = null;
    $("conditionForm").reset();
    $("addCondition").textContent = "Добавить условие";
    $("cancelConditionEdit").hidden = true;
    sourceChanged();
  }
  function renderConditions() {
    const config = getConfig(),
      label = (slug) =>
        config.questions.find((q) => q.slug === slug)?.label ?? slug;
    $("conditionList").replaceChildren();
    if (!conditionDraft.length)
      $("conditionList").append(node("p", "Условия пока не добавлены."));
    conditionDraft.forEach((rule, i) => {
      const row = node("div", "", "condition-card");
      row.append(
        node(
          "p",
          `${label(rule.target)} ← ${label(rule.source)}: ${rule.condition === "neq" ? "не выбраны" : "выбраны"} ${rule.answers.join(", ")} (${rule.operator === "or" ? "ИЛИ" : "И"})`,
        ),
      );
      row.append(
        button("Изменить условие " + (i + 1), () => {
          editingCondition = i;
          put("conditionSource", rule.source);
          put("conditionCompare", rule.condition ?? "eq");
          put("conditionOperator", rule.operator ?? "and");
          sourceChanged(rule.target, rule.answers);
          $("addCondition").textContent = "Обновить условие";
          $("cancelConditionEdit").hidden = false;
        }),
        button("Удалить условие " + (i + 1), () => {
          conditionDraft.splice(i, 1);
          resetCondition();
          renderConditions();
        }),
      );
      $("conditionList").append(row);
    });
  }
  function openConditions() {
    conditionDraft = structuredClone(getConfig().conditions ?? []);
    $("conditionError").textContent = "";
    options(
      $("conditionSource"),
      getConfig()
        .questions.filter((q) => SOURCES.includes(q.type))
        .map((q) => [q.slug, q.label]),
    );
    resetCondition();
    renderConditions();
    conditions.showModal();
  }
  $("conditionSource").addEventListener("change", () => sourceChanged());
  $("cancelConditionEdit").addEventListener("click", resetCondition);
  $("conditionForm").addEventListener("submit", (e) => {
    e.preventDefault();
    try {
      const rule = {
        ...(editingCondition === null ? {} : conditionDraft[editingCondition]),
        source: $("conditionSource").value,
        target: $("conditionTarget").value,
        answers: [
          ...$("conditionAnswers").querySelectorAll("input:checked"),
        ].map((i) => i.value),
        condition: $("conditionCompare").value,
        operator: $("conditionOperator").value,
      };
      const next = structuredClone(conditionDraft);
      if (editingCondition === null) next.push(rule);
      else next[editingCondition] = rule;
      checked({ ...getConfig(), conditions: next });
      conditionDraft = next;
      $("conditionError").textContent = "";
      resetCondition();
      renderConditions();
    } catch (e) {
      $("conditionError").textContent = e.message;
    }
  });
  $("saveConditions").addEventListener("click", () => {
    try {
      if (editingCondition !== null)
        throw new Error(
          "Сначала обновите условие или отмените его редактирование.",
        );
      commit(checked({ ...getConfig(), conditions: conditionDraft }));
      conditions.close();
      notice("Условия показа сохранены.");
    } catch (e) {
      $("conditionError").textContent = e.message;
    }
  });

  const logic = dialog(
    "logicDialog",
    "Проверка логики между вопросами",
    `<p>Локальная проверка ищет вероятные противоречия. Это эвристики: непрямые связи могут остаться незамеченными. Сложные существующие условия не изменяются автоматически.</p><div id="logicIssues"></div>
    <p id="logicError" role="alert"></p><div class="editor-actions"><button id="applySelectedLogic" class="secondary">Применить выбранные</button><button id="applyAllLogic" class="primary">Применить все предложения</button></div>`,
  );
  function renderLogic() {
    const issues = analyzeLogic(getConfig());
    $("logicIssues").replaceChildren();
    $("logicError").textContent = "";
    if (!issues.length)
      $("logicIssues").append(
        node("p", "Предполагаемых противоречий не найдено."),
      );
    for (const issue of issues) {
      const card = node("section", "", "condition-card"),
        label = node("label", "", "check"),
        input = document.createElement("input");
      input.type = "checkbox";
      input.value = issue.target;
      input.disabled = !issue.suggestion;
      label.append(input, document.createTextNode(issue.target_label));
      card.append(
        label,
        node("p", issue.source_label + " → " + issue.target_label),
        node("p", issue.message),
      );
      card.append(
        node(
          "p",
          issue.suggestion
            ? "Предложение: показывать вопрос, когда не выбраны ответы «" +
                issue.negative_answers.join("», «") +
                "»."
            : "Проверить вручную в условиях показа.",
        ),
      );
      $("logicIssues").append(card);
    }
    $("applyAllLogic").disabled = !issues.some((i) => i.suggestion);
    $("applySelectedLogic").disabled = true;
  }
  function openLogic() {
    try {
      renderLogic();
      logic.showModal();
    } catch (e) {
      notice(e.message, true);
    }
  }
  $("logicIssues").addEventListener("change", () => {
    $("applySelectedLogic").disabled = !$("logicIssues").querySelector(
      "input:checked:not(:disabled)",
    );
  });
  function applyLogic(all) {
    const targets = all
      ? null
      : new Set(
          [
            ...$("logicIssues").querySelectorAll(
              "input:checked:not(:disabled)",
            ),
          ].map((i) => i.value),
        );
    const count = analyzeLogic(getConfig()).filter(
      (i) => i.suggestion && (all || targets.has(i.target)),
    ).length;
    if (!count || !confirm("Добавить условия показа: " + count + "?")) return;
    try {
      commit(applySuggestions(getConfig(), targets));
      renderLogic();
      notice("Условия добавлены. Проверьте предпросмотр.");
    } catch (e) {
      $("logicError").textContent = e.message;
    }
  }
  $("applySelectedLogic").addEventListener("click", () => applyLogic(false));
  $("applyAllLogic").addEventListener("click", () => applyLogic(true));

  const actions = node("div", "", "editor-actions");
  for (const [id, label, callback] of [
    ["formSettings", "Параметры анкеты", openSettings],
    ["editConditions", "Условия показа", openConditions],
    ["checkLogic", "Проверка логики", openLogic],
  ]) {
    const el = button(label, callback);
    el.id = id;
    actions.append(el);
  }
  document.querySelector(".form-meta").append(actions);
  return { openQuestion, openSettings, openConditions, openLogic };
}
