import { buildAiPrompt } from "./ai-prompt.mjs";
const $ = (id) => document.getElementById(id);
const BRIEF_KEY = "yaform:ai-brief:v1";
export function installAiFlow({
  getConfig,
  commit,
  parseConfigText,
  dryRun,
  notice,
}) {
  let pack,
    copied = false;
  try {
    $("aiBrief").value = localStorage.getItem(BRIEF_KEY) ?? "";
  } catch {}
  $("aiBrief").addEventListener("input", () => {
    copied = false;
    $("promptNext").hidden = true;
    $("briefError").textContent = "";
    $("copyPrompt").textContent = "Скопировать запрос для ИИ →";
    sync();
    try {
      localStorage.setItem(BRIEF_KEY, $("aiBrief").value);
      $("briefSaveState").textContent = "Описание сохранено в браузере";
    } catch {
      $("briefSaveState").textContent =
        "Описание останется только в этой вкладке";
    }
  });
  async function load() {
    if (pack) return pack;
    const response = await fetch("ai-instructions.txt");
    if (!response.ok)
      throw new Error(
        "Не удалось загрузить инструкцию. Обновите страницу или скачайте TXT-файл.",
      );
    pack = await response.text();
    return pack;
  }
  async function prompt() {
    return buildAiPrompt(await load(), $("aiBrief").value);
  }
  async function openAi() {
    $("aiDialog").showModal();
    $("copyAi").disabled = true;
    try {
      $("aiText").value = await prompt();
      $("aiStatus").textContent = "";
      $("copyAi").disabled = false;
    } catch (e) {
      $("aiStatus").textContent = e.message;
    }
  }
  function markCopied() {
    copied = true;
    $("promptNext").hidden = false;
    $("copyPrompt").textContent = "Скопировать запрос ещё раз";
    sync();
  }
  async function copy(main = false) {
    if (main && !$("aiBrief").value.trim()) {
      $("briefError").textContent = "Опишите, какую форму хотите получить.";
      $("aiBrief").focus();
      return;
    }
    const control = $(main ? "copyPrompt" : "copyAi");
    control.disabled = true;
    let value;
    try {
      value = await prompt();
      $("aiText").value = value;
    } catch (e) {
      $(main ? "briefError" : "aiStatus").textContent = e.message;
      control.disabled = false;
      return;
    }
    try {
      await navigator.clipboard.writeText(value);
      markCopied();
      $("aiStatus").textContent =
        "Скопировано. Вставьте запрос в свой чат с ИИ.";
    } catch {
      if (!$("aiDialog").open) $("aiDialog").showModal();
      $("aiFallback").open = true;
      $("aiText").focus();
      $("aiText").select();
      $("aiStatus").textContent =
        "Браузер не разрешил копирование. Нажмите Ctrl+C или скопируйте выделенный текст вручную.";
    } finally {
      control.disabled = false;
      $("copyAi").disabled = false;
    }
  }
  function openImport() {
    if ($("aiDialog").open) $("aiDialog").close();
    $("importError").textContent = "";
    $("importDialog").showModal();
    $("importText").focus();
  }
  $("copyPrompt").addEventListener("click", () => copy(true));
  $("copyAi").addEventListener("click", () => copy());
  for (const id of ["ai", "aiInline"]) $(id).addEventListener("click", openAi);
  for (const id of ["pasteAi", "pasteAiInline", "pasteAfterPrompt"])
    $(id).addEventListener("click", openImport);
  $("selectAi").addEventListener("click", () => {
    $("aiText").focus();
    $("aiText").select();
  });
  $("aiFallback").addEventListener("toggle", () => {
    if ($("aiFallback").open && !$("aiText").value)
      prompt()
        .then((v) => ($("aiText").value = v))
        .catch((e) => ($("aiStatus").textContent = e.message));
  });
  $("importForm").addEventListener("submit", (e) => {
    e.preventDefault();
    try {
      const input = $("importText").value;
      if (new TextEncoder().encode(input).length > 750000)
        throw new Error(
          "Ответ больше 750 КБ. Для больших анкет используйте настольное приложение.",
        );
      const config = parseConfigText(input);
      dryRun(config);
      if (
        getConfig().questions.length &&
        !confirm(
          "Заменить текущую анкету ответом ИИ? Сохраните её, если она ещё нужна.",
        )
      )
        return;
      commit(config);
      $("manualEditor").open = false;
      $("importDialog").close();
      $("importText").value = "";
      notice(
        "Форма собрана. Сверьте вопросы с вашим заданием и попробуйте заполнить предпросмотр.",
      );
      $("reviewHeading").focus({ preventScroll: true });
      $("reviewHeading").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) {
      $("importError").textContent =
        e.message +
        " Если ответ неполный, попросите ИИ вернуть анкету целиком.";
    }
  });
  function sync() {
    const ready = getConfig().questions.length > 0;
    document.body.classList.toggle("has-form", ready);
    $("reviewHint").textContent = ready
      ? "Сверьте содержание с вашим заданием. Попробуйте ответы и условия показа."
      : "Здесь появится анкета, когда вы вставите ответ ИИ.";
    $("save").disabled = !ready;
    $("validate").disabled = !ready;
    $("clearAnswers").hidden = !ready;
    for (const [id, active, done] of [
      ["stepPrompt", !ready && !copied, copied || ready],
      ["stepImport", !ready && copied, ready],
      ["stepReview", ready, false],
    ]) {
      const step = $(id);
      step.classList.toggle("done", done);
      if (active) step.setAttribute("aria-current", "step");
      else step.removeAttribute("aria-current");
    }
  }
  function reset() {
    copied = false;
    $("aiBrief").value = "";
    $("promptNext").hidden = true;
    $("briefError").textContent = "";
    $("copyPrompt").textContent = "Скопировать запрос для ИИ →";
    $("importText").value = "";
    $("manualEditor").open = false;
    try {
      localStorage.removeItem(BRIEF_KEY);
    } catch {}
    sync();
  }
  return { sync, reset };
}
