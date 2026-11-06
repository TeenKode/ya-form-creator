"""Conservative, explainable cross-question logic review for YaFormCreator.

Never automatically changes a form during validation or publication. Suggestions
are explicit, reviewed by a user, and use the public JSON conditions schema.
No remote NLP requests and no questionnaire data embedded in the application.
"""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

import engine


NEGATIVE_ANSWERS = {
    "не использую", "не пользуюсь", "не применяю", "никогда",
    "не посещаю", "не участвую", "не работаю", "не получаю",
    "не имею", "ни разу", "нет",
}
STRONG_NEGATIVE_ANSWERS = NEGATIVE_ANSWERS - {"нет"}
# These questions may be relevant precisely to respondents who are NOT users.
INCLUSIVE_PATTERNS = (
    "что мешает", "почему не", "препятств", "хотели бы", "хотите ли",
    "планируете", "собираетесь", "нужно ли", "нужна ли",
    "какие трудности", "считаете ли", "следует ли", "стоит ли",
    "как относитесь", "интересно ли", "готовы ли",
    "если не", "если нет", "при отказе", "причины отказа",
)
PRESUPPOSITION_PATTERNS = (
    "какие", "какой", "какую", "для каких", "с какой целью", "с какими",
    "что именно", "где именно", "как часто", "сколько", "оцените",
    "как оцениваете", "насколько полез", "какую пользу",
    "опишите ваш опыт", "приведите пример", "приведите примеры",
    "каким образом", "пользу принос", "для чего",
)
USAGE_VERBS = (
    "использ", "пользу", "примен", "посещ", "приним", "участв",
    "работа", "получа", "обраща", "занима", "имеет",
)
STOPWORDS = {
    "какие", "какой", "какую", "каким", "каких", "используете", "использовать",
    "используется", "пользуетесь", "пользу", "работе", "работа",
    "работы", "своей", "своих", "своем", "вашей", "ваши", "вас", "вам",
    "есть", "были", "было", "будет", "часто", "почему", "можно",
    "укажите", "выберите", "ответ", "вариант", "вопрос", "анкет",
    "сотрудн", "учебн", "школ", "разных", "этого", "области",
    "как", "что", "для", "или", "при", "нет", "да", "ли", "вы",
    "не", "на", "от", "это", "мне", "его", "они", "этой", "так",
    "раз", "ваш", "у", "в", "с", "и", "по", "из", "за", "к",
}
GENERIC_ROOTS = {"работ", "исполь", "польз", "приме", "школ", "сотру", "учебн", "вопро", "вариа"}


def _normalize_label(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold().rstrip(".!?")).strip()


def _tokens(label: str) -> set[str]:
    tokens = re.findall(r"[a-zа-яё0-9]+", label.casefold())
    result = set()
    for token in tokens:
        if token in STOPWORDS:
            continue
        if len(token) <= 2:
            # Short subject words such as ИИ and AI are important.
            if token in {"ии", "ai"}:
                result.add("topic_ai")
            continue
        if token.startswith(("нейросет", "искусственн")):
            result.add("topic_ai")
        if token.startswith(("chatgpt", "deepseek", "yandexgpt")):
            result.add("topic_ai")
        if token.startswith("интеллект"):
            result.add("topic_ai")
        if len(token) >= 5:
            stem = token[:5]
            if stem not in GENERIC_ROOTS and stem not in {"какие", "какой", "вашей", "своей", "может"}:
                result.add(stem)
        elif len(token) >= 3:
            result.add(token)
    return result


def _options(question: dict) -> list[str]:
    return [engine._option_label(opt) for opt in question.get("options", [])]


def _gate_negatives(question: dict) -> list[str]:
    if question.get("type") not in {"radio", "dropdown"} or question.get("hidden"):
        return []
    question_text = _normalize_label(question["label"])
    if not any(verb in question_text for verb in USAGE_VERBS):
        return []
    # A simple "Нет" is unambiguous only for yes/no questions.
    is_yes_no = (" ли " in " " + question_text + " " or question_text.startswith(
        ("есть ли", "используете", "пользуетесь", "посещаете", "имеете")
    ))
    negatives = []
    for option in _options(question):
        value = _normalize_label(option)
        if value in STRONG_NEGATIVE_ANSWERS or (value == "нет" and is_yes_no):
            negatives.append(option)
    return negatives


def _presupposes_action(label: str) -> bool:
    text = _normalize_label(label)
    if any(x in text for x in INCLUSIVE_PATTERNS):
        return False
    if text.startswith(("если да", "если используете", "если посещаете", "если пользуетесь")):
        return True
    return any(x in text for x in PRESUPPOSITION_PATTERNS)


def _similar_topic(source: str, target: str) -> bool:
    return bool(_tokens(source) & _tokens(target))


def analyze_logic(config: dict, *, lookahead: int = 12) -> list[dict[str, Any]]:
    """Return actionable suggestions and non-actionable warnings.

    Only high-confidence links are suggested. A custom human explanation is
    required where existing conditions could interact in unknown ways.
    """
    engine.validate_config(config, allow_empty=True)
    if not config["questions"]:
        return []
    if type(lookahead) is not int or lookahead < 1:
        raise ValueError("lookahead must be a positive integer")

    questions = config["questions"]
    conditions = config.get("conditions", [])
    results: list[dict[str, Any]] = []
    proposed_targets: set[str] = set()
    for index, source in enumerate(questions):
        negatives = _gate_negatives(source)
        if not negatives:
            continue
        if not _tokens(source["label"]):
            continue
        checked = 0
        for target in questions[index + 1:]:
            if target.get("type") in {"section", "comment"}:
                # A section boundary is useful context but not a hard stop.
                continue
            checked += 1
            if checked > lookahead:
                break
            if target.get("hidden") or target.get("type") == "api" or "slug" not in target:
                continue
            if target["slug"] in proposed_targets:
                continue
            if target["type"] not in {"radio", "dropdown", "checkbox", "scale",
                                      "stars", "onerow", "text", "matrix", "integer", "date"}:
                continue
            if not _presupposes_action(target["label"]):
                continue
            if not (_similar_topic(source["label"], target["label"]) or
                    _normalize_label(target["label"]).startswith(
                        ("если да", "если используете", "если пользуетесь", "если посещаете"))):
                continue
            target_rules = [c for c in conditions if c["target"] == target["slug"]]
            same_rules = [c for c in target_rules if c["source"] == source["slug"]]
            if same_rules:
                # A relevant rule already exists. Don't duplicate or second-guess it
                # automatically. Warn when it explicitly shows the question on "No".
                wrong = any(c.get("condition", "eq") == "eq" and
                            set(c["answers"]) & set(negatives) for c in same_rules)
                if not wrong:
                    continue
                message = "Условие уже показывает вопрос при отрицательном ответе. Проверьте его вручную."
                proposed = None
                kind = "conflicting_condition"
            elif target_rules:
                message = ("У вопроса уже есть другие условия показа. Возможна конфликтующая логика; "
                           "новое условие не добавляется автоматически.")
                proposed = None
                kind = "complex_condition"
            else:
                message = ("Если участник выбрал отрицательный ответ в предыдущем вопросе, "
                           "последующий вопрос предполагает опыт использования или участия.")
                proposed = {"target": target["slug"], "source": source["slug"],
                            "answers": negatives, "condition": "neq", "operator": "and"}
                kind = "missing_condition"
            results.append({
                "kind": kind,
                "source": source["slug"], "source_label": source["label"],
                "target": target["slug"], "target_label": target["label"],
                "negative_answers": negatives,
                "message": message, "suggestion": proposed,
            })
            proposed_targets.add(target["slug"])
    return results


def apply_suggestions(config: dict, issues: list[dict], targets: set[str] | None = None) -> dict:
    """Return a validated copy with selected missing conditions added once."""
    engine.validate_config(config, allow_empty=True)
    updated = deepcopy(config)
    candidates = analyze_logic(config)
    approved = {i["target"]: i["suggestion"] for i in candidates
                if i.get("suggestion") is not None and (targets is None or i["target"] in targets)}
    existing = updated.setdefault("conditions", [])
    for target, suggestion in approved.items():
        if suggestion not in existing:
            existing.append(deepcopy(suggestion))
    engine.validate_config(updated, allow_empty=True)
    if updated["questions"]:
        # Ensure the result will survive the checkbox exclusivity transformation
        # and can actually be published, not merely parsed as JSON.
        engine.resolve_exclusive_config(updated)
    return updated
