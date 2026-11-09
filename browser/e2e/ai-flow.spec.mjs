import { test, expect, chromium } from "@playwright/test";
import { readFile } from "node:fs/promises";
import path from "node:path";
const SITE = "https://teenkode.github.io/ya-form-creator/";
const config = {
  form: { name: "Синтетическая анкета" },
  questions: [
    {
      type: "radio",
      slug: "choice",
      label: "Выберите вариант",
      options: ["Первый", "Второй"],
    },
    { type: "text", slug: "comment", label: "Комментарий", multiline: true },
  ],
};
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
      await route.fulfill({
        body: await readFile(path.join("web-dist", name)),
        contentType:
          {
            html: "text/html",
            mjs: "application/javascript",
            css: "text/css",
            png: "image/png",
            txt: "text/plain",
          }[name.split(".").at(-1)] ?? "application/octet-stream",
      });
    });
    const page = await context.newPage(),
      errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(SITE);
    await run(page, context);
    expect(errors).toEqual([]);
  } finally {
    await context.close();
    await browser.close();
  }
}
const saved = (page) => page.locator("#json").inputValue().then(JSON.parse);
test("AI-first journey: describe, copy, import, review and restore without extension", async () =>
  localSite(async (page, context) => {
    await expect(page.locator("#manualEditor")).not.toHaveAttribute("open", "");
    await page.locator("#copyPrompt").click();
    await expect(page.locator("#briefError")).toContainText("Опишите");
    await expect(page.locator("#aiBrief")).toBeFocused();
    const brief =
      "Анкета для теста: два необязательных вопроса, без личных данных.";
    await page.locator("#aiBrief").fill(brief);
    // Assert that the site only copies locally; no external chat is contacted.
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await page.locator("#copyPrompt").click();
    await expect(page.locator("#promptNext")).toBeVisible();
    const prompt = await page.evaluate(() => navigator.clipboard.readText());
    expect(prompt).toContain(brief);
    expect(prompt).toContain("Доступ к GitHub и интернету не требуется");
    expect(prompt).not.toContain("Синтетическая анкета");
    await expect(page.locator("#stepImport")).toHaveAttribute(
      "aria-current",
      "step",
    );
    await page.locator("#pasteAfterPrompt").click();
    await expect(page.locator("#importText")).toBeFocused();
    await page
      .locator("#importText")
      .fill(
        "Вот анкета:\n```json\n" + JSON.stringify(config) + "\n```\nГотово.",
      );
    await page.locator("#importAnswer").click();
    await expect(page.locator("#importDialog")).toBeHidden();
    await expect(page.locator("#previewTitle")).toHaveText(config.form.name);
    await expect(page.locator("#stepReview")).toHaveAttribute(
      "aria-current",
      "step",
    );
    await expect(page.locator("#manualEditor")).not.toHaveAttribute("open", "");
    await expect(page.locator("#send")).toBeDisabled();
    await expect(page.locator("#connectForSend")).toBeVisible();
    await page.locator("#connectForSend").click();
    await expect(page.locator("#installDialog")).toBeVisible();
    await page.locator("#installDialog .dialog-close").click();
    await page.setViewportSize({ width: 1440, height: 1100 });
    await page.screenshot({
      path: "test-results/ai-desktop-filled.png",
      fullPage: true,
    });
    await page.reload();
    await expect(page.locator("#aiBrief")).toHaveValue(brief);
    await expect(page.locator("#previewTitle")).toHaveText(config.form.name);
    await expect(page.locator("#manualEditor")).not.toHaveAttribute("open", "");
    page.once("dialog", (d) => d.accept());
    await page.locator("#new").click();
    await expect(page.locator("#aiBrief")).toHaveValue("");
    await expect(page.locator("#empty")).toBeVisible();
    await expect(page.locator("#stepPrompt")).toHaveAttribute(
      "aria-current",
      "step",
    );
  }));
test("AI import is transactional: invalid answer, dismissed replacement and API limits keep draft", async () =>
  localSite(async (page) => {
    await page.locator("#pasteAiInline").click();
    await page.locator("#importText").fill(JSON.stringify(config));
    await page.locator("#importAnswer").click();
    await page.locator("#pasteAiInline").click();
    await page.locator("#importText").fill('```json\n{"form":');
    await page.locator("#importAnswer").click();
    await expect(page.locator("#importError")).toContainText("целиком");
    expect(await saved(page)).toEqual(config);
    const replacement = { ...config, form: { name: "Replacement" } };
    await page.locator("#importText").fill(JSON.stringify(replacement));
    page.once("dialog", (d) => d.dismiss());
    await page.locator("#importAnswer").click();
    expect(await saved(page)).toEqual(config);
    await expect(page.locator("#importDialog")).toBeVisible();
    page.once("dialog", (d) => d.accept());
    await page.locator("#importAnswer").click();
    expect((await saved(page)).form.name).toBe("Replacement");
    await page.locator("#pasteAiInline").click();
    await page.locator("#importText").fill(" ".repeat(750001));
    await page.locator("#importAnswer").click();
    await expect(page.locator("#importError")).toContainText("750");
    expect((await saved(page)).form.name).toBe("Replacement");
  }));
test("AI workflow on mobile: clipboard fallback, keyboard focus and layouts", async () =>
  localSite(async (page) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({
      path: "test-results/ai-mobile-empty.png",
      fullPage: true,
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page
      .locator("#aiBrief")
      .fill("Синтетическая форма для тестирования.");
    await page.evaluate(() =>
      Object.defineProperty(navigator, "clipboard", {
        configurable: true,
        value: { writeText: () => Promise.reject(new Error("Denied")) },
      }),
    );
    await page.locator("#copyPrompt").click();
    await expect(page.locator("#aiDialog")).toBeVisible();
    await expect(page.locator("#aiFallback")).toHaveAttribute("open", "");
    await expect(page.locator("#aiText")).toBeFocused();
    expect(await page.locator("#aiText").inputValue()).toContain(
      "Синтетическая форма",
    );
    await page.locator("#pasteAi").click();
    await expect(page.locator("#importText")).toBeFocused();
    await page.locator("#importText").fill(JSON.stringify(config));
    await page.screenshot({
      path: "test-results/ai-mobile-import.png",
      fullPage: true,
    });
    expect(
      await page
        .locator("#importDialog")
        .evaluate((el) => el.scrollWidth <= el.clientWidth),
    ).toBe(true);
    await page.locator("#importAnswer").click();
    await expect(page.locator("#reviewHeading")).toBeFocused();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.locator("#manualEditor summary").click();
    await page
      .getByRole("button", { name: "Изменить вопрос 1", exact: true })
      .click();
    await expect(page.locator("#qLabel")).toHaveValue("Выберите вариант");
    await page.keyboard.press("Escape");
    await page.setViewportSize({ width: 320, height: 700 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }));
