"""Offline structural validation plus conservative semantic hints for AI output."""
import argparse
import json
import sys
from pathlib import Path
import re

import engine


def validate_schema(config: dict) -> None:
    try:
        from jsonschema import Draft202012Validator, FormatChecker
    except ImportError:
        raise engine.ConfigError("Для проверки контракта установите: python -m pip install -r requirements-dev.txt") from None
    schema = json.loads((Path(__file__).parent / "schema/form.schema.json").read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(config),
                    key=lambda error: str(list(error.absolute_path)))
    if errors:
        first = errors[0]
        path = ".".join(str(part) for part in first.absolute_path) or "JSON"
        raise engine.ConfigError(f"JSON Schema, {path}: {first.message}")


def review_config(config: dict) -> list[str]:
    """Find common mistakes; does not prove completeness or understand a brief."""
    engine.validate_config(config)
    engine.resolve_exclusive_config(config)
    warnings = []
    if config["form"].get("publish_by_default"):
        warnings.append("form.publish_by_default: включена публикация; для подготовки ИИ используйте false.")
    for question in config["questions"]:
        kind = question["type"]
        if kind in ("section", "comment"):
            continue
        label = question["label"].casefold()
        slug = question["slug"]
        phone = bool(re.search(r"телефон|\bphone\b|\bмобильный\b", label))
        email = bool(re.search(r"(?:электронн\w*\s+почт)|\be-?mail\b|^почта$", label))
        name = bool(re.search(r"\bфио\b|фамили|отчеств|полное имя|^имя$", label))
        inn = bool(re.search(r"\bинн\b", label))
        identifier = bool(re.search(r"номер\s+(?:заказа|заявки|договора|паспорта|документа|сч[её]та)|снилс|почтовый индекс|\bбик\b|артикул", label))
        if phone or email or name or inn or identifier:
            if kind != "text":
                warnings.append(f"{slug}: подпись похожа на персональное/контактное поле или идентификатор; используйте text, чтобы не терять символы и нули.")
            elif question.get("multiline", question.get("format", "plain") == "plain"):
                warnings.append(f"{slug}: для этого поля обычно нужен multiline: false.")
        if kind == "text":
            fmt = question.get("format", "plain")
            if email and fmt != "email":
                warnings.append(f"{slug}: для электронной почты ожидается format: email.")
            if inn and fmt != "inn":
                warnings.append(f"{slug}: для ИНН ожидается format: inn.")
            if name and fmt not in ("plain", "full_name"):
                warnings.append(f"{slug}: имя/ФИО не должно проверяться как {fmt}.")
            if phone and fmt not in ("plain", "phone"):
                warnings.append(f"{slug}: телефон должен быть строкой; phone — РФ, plain — международный формат по заданию.")
            if identifier and fmt not in ("plain",):
                warnings.append(f"{slug}: идентификатор нельзя проверять как {fmt}; обычно нужен plain-текст.")
        if "initial" in question or "default" in question or "initial" in question.get("payload", {}):
            warnings.append(f"{slug}: задан начальный ответ; убедитесь, что он явно запрошен и не содержит персональных данных.")
    import logic_analyzer
    for issue in logic_analyzer.analyze_logic(config):
        warnings.append("Межвопросная логика: " + str(issue.get("message", issue.get("title", issue))))
    return warnings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="UTF-8 JSON, подготовленный агентом")
    args = parser.parse_args(argv)
    try:
        config = engine.load_config(args.config)
        validate_schema(config)
        warnings = review_config(config)
        # Building is essential: validate what will actually reach the API.
        engine.dry_run(config)
    except engine.ConfigError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2
    if warnings:
        print("Структура корректна, но проверьте назначение полей:")
        for warning in warnings:
            print("- " + warning)
        print("Эвристики могут ошибаться. Сверьте замечания с исходным заданием; не исправляйте смысл автоматически.")
        return 3
    print("Offline-проверка пройдена: структура и построение API payload корректны; типичных ошибок назначения не найдено.")
    print("Сверьте полноту с исходным заданием. Эта проверка не вызывает Яндекс API и не доказывает понимание задания агентом.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
