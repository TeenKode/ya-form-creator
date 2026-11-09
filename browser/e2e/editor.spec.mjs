import { test, expect, chromium } from "@playwright/test";
import { readFile } from "node:fs/promises";
import path from "node:path";
const SITE = "https://teenkode.github.io/ya-form-creator/";
async function localSite(run) {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.YAFORM_OPERA_BINARY
      ? { executablePath: process.env.YAFORM_OPERA_BINARY }
      : process.env.YAFORM_UI_CHANNEL
        ? { channel: process.env.YAFORM_UI_CHANNEL }
        : {}),
  });
  const context = await browser.newContext();
  try {
    await context.route("**/*", async (route) => {
      if (!route.request().url().startsWith(SITE)) return route.abort();
      const name =
        new URL(route.request().url()).pathname.slice(
          "/ya-form-creator/".length,
        ) || "index.html";
      const type = {
        html: "text/html",
        mjs: "application/javascript",
        css: "text/css",
        png: "image/png",
        txt: "text/plain",
      }[name.split(".").at(-1)];
      await route.fulfill({
        body: await readFile(path.join("web-dist", name)),
        contentType: type ?? "application/octet-stream",
      });
    });
    const page = await context.newPage(),
      errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(SITE);
    await run(page);
    expect(errors).toEqual([]);
  } finally {
    await context.close();
    await browser.close();
  }
}
async function seed(page, config) {
  await page.locator("#jsonDetails").evaluate((el) => (el.open = true));
  await page.locator("#json").fill(JSON.stringify(config));
  await page.locator("#applyJson").click();
  await page.locator("#manualEditor").evaluate(el => el.open = true);
}
const saved = (page) => page.locator("#json").inputValue().then(JSON.parse);
async function saveQuestion(page) {
  await page.locator("#questionForm button[type=submit]").click();
  await expect(page.locator("#questionDialog")).toBeHidden();
}

test("full visual editor: all types, ranges, Other, exclusions, API and settings round-trip", async () =>
  localSite(async (page) => {
    const config = {
      form: { name: "Synthetic", extra: "preserved" },
      questions: [],
    };
    await seed(page, config);
    await page.locator("#formSettings").click();
    await page.locator("#settingsSubmit").fill("Готово");
    await page.locator("#settingsTitle").fill("Принято");
    await page.locator("#settingsSubtitle").fill("Спасибо");
    await page.locator("#settingsMultiple").uncheck();
    await page.locator("#settingsAuth").check();
    await page.locator("#settingsPublish").check();
    await page.locator("#formSettingsForm button[type=submit]").click();
    expect((await saved(page)).form).toMatchObject({
      submit_text: "Готово",
      success_title: "Принято",
      success_subtitle: "Спасибо",
      allow_multiple_answers: false,
      need_auth: true,
      publish_by_default: true,
      extra: "preserved",
    });
    for (const type of [
      "scale",
      "stars",
      "onerow",
      "matrix",
      "text",
      "integer",
      "date",
      "checkbox",
      "api",
      "section",
      "comment",
    ]) {
      await page.locator("#add").click();
      await page.locator("#qType").selectOption(type);
      await page.locator("#qLabel").fill("Synthetic " + type);
      if (["scale", "stars", "onerow", "checkbox"].includes(type))
        await page.locator("#qOptions").fill("A\nB");
      if (type === "matrix") {
        await page.locator("#qRows").fill("R1\nR2");
        await page.locator("#qColumns").fill("C1\nC2");
      }
      if (type === "text") {
        await page.locator("#qSlug").fill("long_text");
        await page.locator("#qComment").fill("Hint");
        await page.locator("#qMultiline").check();
        await page.locator("#qMinLength").fill("2");
        await page.locator("#qMaxLength").fill("20");
        await page.locator("#qPlaceholder").fill("Enter text");
      }
      if (type === "integer") {
        await page.locator("#qMin").fill("1");
        await page.locator("#qMax").fill("5");
      }
      if (type === "date") {
        await page.locator("#qMin").fill("2026-01-01");
        await page.locator("#qMax").fill("2026-12-31");
      }
      if (type === "checkbox") {
        await page.locator("#qOptions").fill("A\nB\nНет");
        await page.locator("#qOther").check();
        await page.locator("#qOtherLabel").fill("Your answer");
        await page.locator("#qExclusiveAuto").uncheck();
        await page.locator("#qExclusive").fill("Нет");
      }
      if (type === "api")
        await page
          .locator("#qPayload")
          .fill(
            JSON.stringify({ type: "string", validators: [{ type: "email" }] }),
          );
      await saveQuestion(page);
    }
    const result = await saved(page);
    expect(result.questions).toHaveLength(11);
    expect(result.questions.find((q) => q.type === "text")).toMatchObject({
      slug: "long_text",
      multiline: true,
      min_length: 2,
      max_length: 20,
      comment: "Hint",
      placeholder: "Enter text",
    });
    expect(result.questions.find((q) => q.type === "matrix").rows).toEqual([
      "R1",
      "R2",
    ]);
    expect(result.questions.find((q) => q.type === "checkbox")).toMatchObject({
      exclusive_options: ["Нет"],
      options: ["A", "B", "Нет", "Другое"],
      other: { label: "Your answer" },
    });
    expect(
      result.questions.find((q) => q.type === "api").payload.validators,
    ).toEqual([{ type: "email" }]);
    await page
      .getByRole("button", { name: "Изменить вопрос 1", exact: true })
      .click();
    await expect(page.locator("#qType")).toHaveValue("scale");
    await page.locator("#qLabel").fill("Changed scale");
    await saveQuestion(page);
    // A different type starts a valid new type contract rather than leaving options/format behind.
    await page
      .getByRole("button", { name: "Изменить вопрос 4", exact: true })
      .click();
    await page.locator("#qType").selectOption("integer");
    await saveQuestion(page);
    expect((await saved(page)).questions[3].type).toBe("integer");
    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator("#add").click();
    await page.locator("#qType").selectOption("matrix");
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    expect(
      await page
        .locator("#questionDialog")
        .evaluate((el) => el.scrollWidth <= el.clientWidth),
    ).toBe(true);
    await page.screenshot({
      path: "test-results/editor-mobile.png",
      fullPage: true,
    });
    await page.locator("#questionDialog .dialog-close").click();
    await page.reload();
    expect((await saved(page)).questions).toHaveLength(11);
  }));

test("visual conditions: add, edit, rename, duplicate, remove references and discard", async () =>
  localSite(async (page) => {
    await seed(page, {
      form: { name: "Conditions" },
      questions: [
        {
          type: "radio",
          slug: "source",
          label: "Source",
          options: ["A", "B", "Другое"],
          other: { label: "Other" },
        },
        { type: "text", slug: "follow", label: "Follow" },
      ],
    });
    await page.locator("#editConditions").click();
    await page.locator("#conditionSource").selectOption("source");
    await page.locator("#conditionTarget").selectOption("follow");
    await page
      .locator("#conditionAnswers")
      .getByLabel("A", { exact: true })
      .check();
    await page.locator("#addCondition").click();
    await page.locator("#saveConditions").click();
    await expect(
      page.getByRole("textbox", { name: "Follow", exact: true }),
    ).toBeHidden();
    await page.locator("#blocks").getByLabel("A", { exact: true }).check();
    await expect(
      page.getByRole("textbox", { name: "Follow", exact: true }),
    ).toBeVisible();
    await page.locator("#editConditions").click();
    await page
      .getByRole("button", { name: "Изменить условие 1", exact: true })
      .click();
    await page
      .locator("#conditionAnswers")
      .getByLabel("A", { exact: true })
      .uncheck();
    await page
      .locator("#conditionAnswers")
      .getByLabel("B", { exact: true })
      .check();
    await page.locator("#conditionOperator").selectOption("or");
    await page.locator("#addCondition").click();
    await page.locator("#saveConditions").click();
    expect((await saved(page)).conditions[0]).toMatchObject({
      answers: ["B"],
      operator: "or",
    });
    await page
      .getByRole("button", { name: "Изменить вопрос 1", exact: true })
      .click();
    await page.locator("#qSlug").fill("renamed");
    await saveQuestion(page);
    expect((await saved(page)).conditions[0].source).toBe("renamed");
    await page
      .getByRole("button", { name: "Дублировать вопрос 2", exact: true })
      .click();
    expect((await saved(page)).questions).toHaveLength(3);
    expect((await saved(page)).conditions).toHaveLength(2);
    await page.locator("#editConditions").click();
    await page
      .getByRole("button", { name: "Удалить условие 1", exact: true })
      .click();
    await page.locator("#conditionsDialog .dialog-close").click();
    expect((await saved(page)).conditions).toHaveLength(2);
    page.once("dialog", (d) => {
      expect(d.message()).toContain("Связанных условий");
      return d.accept();
    });
    await page
      .getByRole("button", { name: "Удалить вопрос 1", exact: true })
      .click();
    expect((await saved(page)).conditions).toEqual([]);
    expect((await saved(page)).questions).toHaveLength(2);
    // Per-question JSON preserves fields which have no dedicated control.
    await page
      .getByRole("button", { name: "Изменить вопрос 1", exact: true })
      .click();
    await page.locator("#questionJsonDetails summary").click();
    const q = JSON.parse(await page.locator("#questionJson").inputValue());
    q.placeholder = "Advanced";
    await page.locator("#questionJson").fill(JSON.stringify(q));
    await page.locator("#applyQuestionJson").click();
    await expect(page.locator("#questionDialog")).toBeHidden();
    expect((await saved(page)).questions[0].placeholder).toBe("Advanced");
  }));

test("logic review: validation warns, selected/all suggestions require confirmation, existing rules stay", async () =>
  localSite(async (page) => {
    await seed(page, {
      form: { name: "Logic" },
      questions: [
        {
          type: "radio",
          slug: "usage",
          label: "Как часто используете ИИ?",
          options: ["Часто", "Не использую"],
        },
        {
          type: "text",
          slug: "tools",
          label: "Какие инструменты ИИ используете?",
        },
        {
          type: "text",
          slug: "tasks",
          label: "Для каких задач используете ИИ?",
        },
        {
          type: "text",
          slug: "barriers",
          label: "Что мешает использовать ИИ?",
        },
      ],
    });
    await page.locator("#validate").click();
    await expect(page.locator("#logicDialog")).toBeVisible();
    expect((await saved(page)).conditions).toBeUndefined();
    await page.locator("#logicIssues input[value=tools]").check();
    page.once("dialog", (d) => d.dismiss());
    await page.locator("#applySelectedLogic").click();
    expect((await saved(page)).conditions).toBeUndefined();
    page.once("dialog", (d) => d.accept());
    await page.locator("#applySelectedLogic").click();
    expect((await saved(page)).conditions.map((c) => c.target)).toEqual([
      "tools",
    ]);
    page.once("dialog", (d) => d.accept());
    await page.locator("#applyAllLogic").click();
    expect((await saved(page)).conditions.map((c) => c.target)).toEqual([
      "tools",
      "tasks",
    ]);
    await expect(page.locator("#applyAllLogic")).toBeDisabled();
    await page.locator("#logicDialog .dialog-close").click();
    await page.getByLabel("Не использую", { exact: true }).check();
    await expect(
      page.getByRole("textbox", {
        name: "Какие инструменты ИИ используете?",
        exact: true,
      }),
    ).toBeHidden();
    await expect(
      page.getByRole("textbox", {
        name: "Что мешает использовать ИИ?",
        exact: true,
      }),
    ).toBeVisible();
    const c = await saved(page);
    c.conditions[0].condition = "eq";
    await seed(page, c);
    await page.keyboard.press("F6");
    await expect(page.locator("#logicIssues")).toContainText("вручную");
    await expect(page.locator("#applyAllLogic")).toBeDisabled();
    expect((await saved(page)).conditions[0].condition).toBe("eq");
  }));
