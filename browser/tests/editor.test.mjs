import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { analyzeLogic, applySuggestions } from "../logic-analyzer.mjs";
import {
  replaceQuestion,
  duplicateQuestion,
  deleteQuestion,
  relatedConditions,
  nextSlug,
} from "../editor-model.mjs";
const fixtures = JSON.parse(
  execFileSync(
    process.env.PYTHON ?? "python",
    ["browser/tests/logic-fixtures.py"],
    { encoding: "utf8", env: { ...process.env, PYTHONIOENCODING: "utf-8" } },
  ),
);
for (const [i, { config, issues, applied }] of fixtures.entries())
  test("Python/JS logic parity " + i, () => {
    const original = structuredClone(config);
    assert.deepEqual(analyzeLogic(config), issues);
    assert.deepEqual(applySuggestions(config), applied);
    assert.deepEqual(config, original);
    assert.deepEqual(applySuggestions(applied), applied);
  });
test("selected suggestions are recomputed; unrelated and complex conditions stay intact", () => {
  const config = fixtures[0].config;
  const fixed = applySuggestions(config, new Set(["tools"]));
  assert.deepEqual(
    fixed.conditions.map((c) => c.target),
    ["tools"],
  );
  assert.deepEqual(
    analyzeLogic(fixed).map((i) => i.target),
    ["tasks", "benefit"],
  );
  const complex = fixtures[3].config;
  assert.deepEqual(
    applySuggestions(complex, new Set(["tools"])).conditions,
    complex.conditions,
  );
});
const make = () => ({
  form: { name: "Synthetic", need_auth: true },
  questions: [
    {
      type: "radio",
      slug: "gate",
      label: "Gate",
      options: [{ label: "A", scores: 3 }, "Другое"],
      other: { label: "Other" },
    },
    {
      type: "text",
      slug: "follow",
      label: "Follow",
      comment: "Keep me",
      multiline: true,
      extra: { a: 1 },
    },
  ],
  conditions: [
    { source: "gate", target: "follow", answers: ["A"] },
    { source: "gate", target: "gate_other", answers: ["A"] },
  ],
});
test("rename repairs source, target and implicit Other references without mutating input", () => {
  const c = make(),
    old = structuredClone(c),
    q = { ...c.questions[0], slug: "renamed" };
  const next = replaceQuestion(c, 0, q);
  assert.equal(next.conditions[0].source, "renamed");
  assert.equal(next.conditions[1].target, "renamed_other");
  assert.deepEqual(c, old);
  assert.deepEqual(next.form, c.form);
  assert.throws(() => replaceQuestion(c, 0, { ...q, slug: "follow" }));
  assert.throws(() => replaceQuestion(c, 0, { ...q, options: ["X", "Y"] }));
});
test("duplicate gets fresh codes and copies incoming conditions and advanced data", () => {
  const c = make(),
    next = duplicateQuestion(c, 1);
  assert.equal(next.questions[2].slug, "q1");
  assert.deepEqual(next.questions[2].extra, { a: 1 });
  assert.deepEqual(next.conditions.at(-1), {
    source: "gate",
    target: "q1",
    answers: ["A"],
  });
  const other = duplicateQuestion(c, 0);
  assert.equal(other.questions[1].slug, "q1");
  assert.equal(other.questions[1].other.slug, undefined);
  assert.deepEqual(other.questions[1].options, c.questions[0].options);
  assert.equal(other.conditions.at(-1).target, "q1_other");
  const api = {
    form: { name: "API" },
    questions: [
      {
        type: "api",
        slug: "custom",
        label: "Custom",
        payload: {
          type: "string",
          slug: "custom",
          validators: [{ type: "required" }],
        },
      },
    ],
  };
  assert.equal(duplicateQuestion(api, 0).questions[1].payload.slug, "q1");
});
test("delete removes incoming, outgoing and Other conditions and supports empty config", () => {
  const c = make(),
    old = structuredClone(c);
  assert.equal(relatedConditions(c, 0).length, 2);
  const next = deleteQuestion(c, 0);
  assert.deepEqual(next.conditions, []);
  assert.equal(next.questions.length, 1);
  assert.deepEqual(deleteQuestion(next, 0).questions, []);
  assert.deepEqual(c, old);
});
test("generated codes avoid service codes and duplication validates expansion", () => {
  const c = {
    form: { name: "Codes" },
    questions: [{ type: "text", slug: "q1_other", label: "Occupied" }],
  };
  assert.equal(nextSlug(c), "q2");
  const limit = {
    form: { name: "Limit" },
    questions: Array.from({ length: 150 }, (_, i) => ({
      type: "text",
      slug: "f" + i,
      label: "Field",
    })),
  };
  assert.throws(() => duplicateQuestion(limit, 0));
  assert.equal(limit.questions.length, 150);
});
