// Accept common chat presentation wrappers, but never guess or repair the schema.
export function parseConfigText(value) {
  const text = value.replace(/^\uFEFF/, '').trim();
  try { return JSON.parse(text); } catch { /* A chat may wrap one JSON block. */ }
  const fences = [...text.matchAll(/^```[^\r\n]*\r?\n[\s\S]*?^```[ \t]*$/gm)];
  if (fences.length === 1) {
    const match = fences[0][0].match(/^```(?:json)?[ \t]*\r?\n([\s\S]*?)\r?\n```[ \t]*$/i);
    if (match) try { return JSON.parse(match[1]); } catch { /* Show a useful error below. */ }
  }
  throw new Error('Не удалось прочитать JSON. Попросите ИИ вернуть один целый файл form.json без комментариев внутри JSON. Если ответ оборвался, попросите прислать файл заново.');
}
