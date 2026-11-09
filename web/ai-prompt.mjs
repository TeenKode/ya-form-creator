// A portable prompt, prepared locally. No model API, credentials or automatic transmission.
export function buildAiPrompt(instructions, brief = "") {
  const rules = instructions.replaceAll("\r\n", "\n").trim();
  if (!rules)
    throw new Error("Инструкция для ИИ пуста. Попробуйте обновить страницу.");
  const description = brief.trim();
  return (
    rules +
    (description
      ? "\n\n--- МОЁ ЗАДАНИЕ ---\n" +
        description +
        "\n\nСоставь анкету по этому заданию. Если чего-то важного не хватает, сначала задай уточняющие вопросы."
      : "") +
    "\n"
  );
}
