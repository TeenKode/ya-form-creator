import { validateConfig, dryRun } from "./core.mjs";

const clone = (value) => structuredClone(value);
export function checked(config) {
  validateConfig(config, { allowEmpty: true });
  if (config.questions.length) dryRun(config);
  return config;
}
function codes(config, except = -1) {
  return new Set(
    config.questions.flatMap((q, index) =>
      index === except || !q.slug
        ? []
        : [q.slug, q.slug + "_choice", q.other?.slug ?? q.slug + "_other"],
    ),
  );
}
export function nextSlug(config) {
  const taken = codes(config);
  let n = 1;
  while (
    ["q" + n, "q" + n + "_choice", "q" + n + "_other"].some((s) => taken.has(s))
  )
    n++;
  return "q" + n;
}
export function replaceQuestion(config, index, question) {
  const next = clone(config),
    old = next.questions[index];
  if (!old) throw new Error("Вопрос не найден.");
  // Keep conditions attached when the user changes a code, including implicit Other codes.
  const renames = new Map();
  if (old.slug && question.slug && old.slug !== question.slug)
    renames.set(old.slug, question.slug);
  if (old.other && question.other) {
    renames.set(
      old.other.slug ?? old.slug + "_other",
      question.other.slug ?? question.slug + "_other",
    );
  }
  next.questions[index] = clone(question);
  next.conditions = (next.conditions ?? []).map((c) => ({
    ...c,
    source: renames.get(c.source) ?? c.source,
    target: renames.get(c.target) ?? c.target,
  }));
  return checked(next);
}
export function duplicateQuestion(config, index) {
  const next = clone(config),
    question = clone(next.questions[index]);
  if (!question) throw new Error("Вопрос не найден.");
  const oldSlug = question.slug;
  if (oldSlug) {
    question.slug = nextSlug(config);
    if (question.other) delete question.other.slug;
    if (question.type === "api") question.payload.slug = question.slug;
    // Copy incoming visibility rules, but leave questions depending on the original alone.
    const oldOther = config.questions[index].other?.slug ?? oldSlug + "_other";
    const added = (next.conditions ?? [])
      .filter(
        (c) =>
          c.target === oldSlug || (question.other && c.target === oldOther),
      )
      .map((c) => ({
        ...clone(c),
        target: c.target === oldSlug ? question.slug : question.slug + "_other",
      }));
    if (added.length) next.conditions = [...(next.conditions ?? []), ...added];
  }
  next.questions.splice(index + 1, 0, question);
  return checked(next);
}
export function relatedConditions(config, index) {
  const q = config.questions[index];
  const removed = new Set(
    q?.slug
      ? [q.slug, q.other?.slug ?? q.slug + "_other", q.slug + "_choice"]
      : [],
  );
  return (config.conditions ?? []).filter(
    (c) => removed.has(c.source) || removed.has(c.target),
  );
}
export function deleteQuestion(config, index) {
  const next = clone(config),
    removed = new Set(relatedConditions(config, index));
  next.questions.splice(index, 1);
  next.conditions = (config.conditions ?? [])
    .filter((c) => !removed.has(c))
    .map(clone);
  return checked(next);
}
