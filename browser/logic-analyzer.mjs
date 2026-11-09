// Local, conservative heuristics shared in behavior with logic_analyzer.py.
import { validateConfig, dryRun } from "./core.mjs";

function normalize(value) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[.!?]+$/, "")
    .replace(/\s+/g, " ")
    .trim();
}
function tokens(label) {
  const result = new Set();
  for (const token of label.toLowerCase().match(/[a-zа-яё0-9]+/g) ?? []) {
    if (STOPWORDS.includes(token)) continue;
    if (token.length <= 2) {
      if (["ии", "ai"].includes(token)) result.add("topic_ai");
      continue;
    }
    if (
      [
        "нейросет",
        "искусственн",
        "chatgpt",
        "deepseek",
        "yandexgpt",
        "интеллект",
      ].some((s) => token.startsWith(s))
    )
      result.add("topic_ai");
    if (token.length >= 5) {
      const stem = token.slice(0, 5);
      if (
        ![
          ...GENERIC_ROOTS,
          "какие",
          "какой",
          "вашей",
          "своей",
          "может",
        ].includes(stem)
      )
        result.add(stem);
    } else result.add(token);
  }
  return result;
}
export function analyzeLogic(config, lookahead = 12) {
  validateConfig(config, { allowEmpty: true });
  if (!Number.isInteger(lookahead) || lookahead < 1)
    throw new Error("lookahead must be a positive integer");
  const results = [],
    proposed = new Set();
  config.questions.forEach((source, index) => {
    if (!["radio", "dropdown"].includes(source.type) || source.hidden) return;
    const sourceText = normalize(source.label);
    if (
      !USAGE_VERBS.some((v) => sourceText.includes(v)) ||
      !tokens(source.label).size
    )
      return;
    const yesNo =
      (" " + sourceText + " ").includes(" ли ") ||
      ["есть ли", "используете", "пользуетесь", "посещаете", "имеете"].some(
        (s) => sourceText.startsWith(s),
      );
    const negatives = source.options
      .map((o) => (typeof o === "string" ? o : o.label))
      .filter((o) => {
        const text = normalize(o);
        return NEGATIVE_ANSWERS.includes(text) && (text !== "нет" || yesNo);
      });
    if (!negatives.length) return;
    let count = 0;
    for (const target of config.questions.slice(index + 1)) {
      if (["section", "comment"].includes(target.type)) continue;
      if (++count > lookahead) break;
      if (
        target.hidden ||
        proposed.has(target.slug) ||
        ![
          "radio",
          "dropdown",
          "checkbox",
          "scale",
          "stars",
          "onerow",
          "text",
          "matrix",
          "integer",
          "date",
        ].includes(target.type)
      )
        continue;
      const text = normalize(target.label);
      if (INCLUSIVE_PATTERNS.some((s) => text.includes(s))) continue;
      const explicit = [
        "если да",
        "если используете",
        "если посещаете",
        "если пользуетесь",
      ].some((s) => text.startsWith(s));
      if (!explicit && !PRESUPPOSITION_PATTERNS.some((s) => text.includes(s)))
        continue;
      if (
        !explicit &&
        ![...tokens(source.label)].some((t) => tokens(target.label).has(t))
      )
        continue;
      const rules = (config.conditions ?? []).filter(
          (c) => c.target === target.slug,
        ),
        same = rules.filter((c) => c.source === source.slug);
      let suggestion = null,
        kind,
        message;
      if (same.length) {
        if (
          !same.some(
            (c) =>
              (c.condition ?? "eq") === "eq" &&
              c.answers.some((a) => negatives.includes(a)),
          )
        )
          continue;
        kind = "conflicting_condition";
        message =
          "Условие уже показывает вопрос при отрицательном ответе. Проверьте его вручную.";
      } else if (rules.length) {
        kind = "complex_condition";
        message =
          "У вопроса уже есть другие условия показа. Возможна конфликтующая логика; новое условие не добавляется автоматически.";
      } else {
        kind = "missing_condition";
        message =
          "Если участник выбрал отрицательный ответ в предыдущем вопросе, последующий вопрос предполагает опыт использования или участия.";
        suggestion = {
          target: target.slug,
          source: source.slug,
          answers: negatives,
          condition: "neq",
          operator: "and",
        };
      }
      results.push({
        kind,
        source: source.slug,
        source_label: source.label,
        target: target.slug,
        target_label: target.label,
        negative_answers: negatives,
        message,
        suggestion,
      });
      proposed.add(target.slug);
    }
  });
  return results;
}
export function applySuggestions(config, targets = null) {
  const next = structuredClone(config);
  const suggestions = analyzeLogic(config).filter(
    (i) => i.suggestion && (targets === null || targets.has(i.target)),
  );
  next.conditions ??= [];
  for (const issue of suggestions)
    next.conditions.push(structuredClone(issue.suggestion));
  validateConfig(next, { allowEmpty: true });
  if (next.questions.length) dryRun(next);
  return next;
}
const NEGATIVE_ANSWERS = [
  "не имею",
  "не использую",
  "не получаю",
  "не пользуюсь",
  "не посещаю",
  "не применяю",
  "не работаю",
  "не участвую",
  "нет",
  "ни разу",
  "никогда",
];
const INCLUSIVE_PATTERNS = [
  "что мешает",
  "почему не",
  "препятств",
  "хотели бы",
  "хотите ли",
  "планируете",
  "собираетесь",
  "нужно ли",
  "нужна ли",
  "какие трудности",
  "считаете ли",
  "следует ли",
  "стоит ли",
  "как относитесь",
  "интересно ли",
  "готовы ли",
  "если не",
  "если нет",
  "при отказе",
  "причины отказа",
];
const PRESUPPOSITION_PATTERNS = [
  "какие",
  "какой",
  "какую",
  "для каких",
  "с какой целью",
  "с какими",
  "что именно",
  "где именно",
  "как часто",
  "сколько",
  "оцените",
  "как оцениваете",
  "насколько полез",
  "какую пользу",
  "опишите ваш опыт",
  "приведите пример",
  "приведите примеры",
  "каким образом",
  "пользу принос",
  "для чего",
];
const USAGE_VERBS = [
  "использ",
  "пользу",
  "примен",
  "посещ",
  "приним",
  "участв",
  "работа",
  "получа",
  "обраща",
  "занима",
  "имеет",
];
const STOPWORDS = [
  "анкет",
  "будет",
  "были",
  "было",
  "в",
  "вам",
  "вариант",
  "вас",
  "ваш",
  "вашей",
  "ваши",
  "вопрос",
  "вы",
  "выберите",
  "да",
  "для",
  "его",
  "есть",
  "за",
  "и",
  "из",
  "или",
  "использовать",
  "используете",
  "используется",
  "к",
  "как",
  "какие",
  "каким",
  "каких",
  "какой",
  "какую",
  "ли",
  "мне",
  "можно",
  "на",
  "не",
  "нет",
  "области",
  "они",
  "от",
  "ответ",
  "по",
  "пользу",
  "пользуетесь",
  "почему",
  "при",
  "работа",
  "работе",
  "работы",
  "раз",
  "разных",
  "с",
  "своей",
  "своем",
  "своих",
  "сотрудн",
  "так",
  "у",
  "укажите",
  "учебн",
  "часто",
  "что",
  "школ",
  "это",
  "этого",
  "этой",
];
const GENERIC_ROOTS = [
  "вариа",
  "вопро",
  "исполь",
  "польз",
  "приме",
  "работ",
  "сотру",
  "учебн",
  "школ",
];
