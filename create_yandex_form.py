#!/usr/bin/env python3
"""CLI-режим универсального конструктора Яндекс Форм."""
import argparse
import json
import sys
from getpass import getpass
from pathlib import Path

import engine


def input_required(prompt: str, default: str = "", secret: bool = False) -> str:
    while True:
        reader = getpass if secret else input
        result = reader(f"{prompt}" + (f" [{default}]" if default else "") + ": ").strip()
        result = result or default
        if result:
            return result
        print("Поле не может быть пустым.")


def yes_no(prompt: str, default: bool = False) -> bool:
    answer = input(f"{prompt} [{'Д/н' if default else 'д/Н'}]: ").strip().lower()
    if not answer:
        return default
    return answer in ("д", "да", "y", "yes", "1")


def choose_config_path(path: Path | None) -> Path:
    if path:
        return path
    # No bundled questionnaire: only explicit or previously saved user files.
    settings = engine.load_settings()
    last = settings.get("last_form_path", "")
    if last and Path(last).is_file():
        return Path(last)
    if engine.DEFAULT_CONFIG.is_file():
        return engine.DEFAULT_CONFIG
    try:
        from tkinter import Tk, filedialog
        root = Tk(); root.withdraw()
        result = filedialog.askopenfilename(title="Выберите JSON анкеты", filetypes=[("JSON", "*.json")])
        root.destroy()
        if result:
            return Path(result)
    except Exception:
        pass
    return Path(input_required("Путь к файлу JSON"))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Универсальное создание Яндекс Форм из JSON")
    p.add_argument("--config", type=Path, help="JSON-конфигурация любой анкеты")
    p.add_argument("--validate", action="store_true", help="Проверить структуру, варианты и условия")
    p.add_argument("--dry-run", action="store_true", help="Вывести payload API, не создавая форму")
    p.add_argument("--create", action="store_true", help="Создать форму через API")
    p.add_argument("--reset-credentials", action="store_true", help="Удалить сохранённый токен")
    args = p.parse_args(argv)
    if args.reset_credentials:
        engine.CREDENTIALS_FILE.unlink(missing_ok=True)
        print("Сохранённые данные авторизации удалены.")
        return 0
    path = choose_config_path(args.config)
    try:
        config = engine.load_config(path)
        payloads, conditions = engine.expand_questions(config)
    except engine.ConfigError as exc:
        print("Ошибка конфигурации:", exc, file=sys.stderr)
        return 2
    if args.validate:
        print(f"Проверка пройдена: {path}\nЭлементов: {len(config['questions'])}\n"
              f"Вопросов и блоков API: {len(payloads)}\nУсловий показа: {len(conditions)}")
        return 0
    if args.dry_run:
        print(json.dumps(engine.dry_run(config), ensure_ascii=False, indent=2))
        return 0
    creds = engine.environment_credentials() or engine.load_credentials()
    if creds:
        print(f"Использую настройки организации: {creds['org_id']}")
    else:
        print("Данные Яндекс Форм:")
        auth = input("Тип токена: [1] OAuth, [2] IAM/Bearer [1]: ").strip()
        org = input("Организация: [1] Яндекс 360 (X-Org-Id), [2] Cloud (X-Cloud-Org-Id) [1]: ").strip()
        creds = {"auth_scheme": "Bearer" if auth == "2" else "OAuth",
                 "org_header": "X-Cloud-Org-Id" if org == "2" else "X-Org-Id",
                 "token": input_required("Токен", secret=True),
                 "org_id": input_required("ID организации")}
        if yes_no("Сохранить токен в файл в открытом виде?", False):
            engine.save_credentials(creds)
    name = input_required("Название формы", config["form"]["name"])
    publish = yes_no("Опубликовать сразу после создания?", bool(config["form"].get("publish_by_default", False)))
    if not yes_no("Создать НОВУЮ форму?", False):
        print("Создание отменено.")
        return 0
    try:
        result = engine.create_form(config, creds, name=name, publish=publish, progress=print)
    except (engine.ApiError, engine.ConfigError) as exc:
        print("Ошибка:", exc, file=sys.stderr)
        return 1
    print("\nГотово.\nРедактирование:", result["edit_url"], "\nЗаполнение:", result["fill_url"])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyboardInterrupt, EOFError):
        print("\nОтменено пользователем.")
        sys.exit(130)
