# YaFormCreator — универсальный редактор Яндекс Форм

Приложение для Windows: визуальный редактор JSON-анкет и создание новых Яндекс Форм через API.
Работает с текстом, выбором вариантов, шкалами, матрицами, условиями показа, «Другим» и сырыми API-вопросами.

## Скачать программу

Откройте **[Releases](https://github.com/TeenKode/ya-form-creator/releases)** и скачайте **YaFormCreator.exe**.
EXE автономный: для запуска не нужен Python и отдельные DLL. Требуются Windows 10/11 и интернет только при создании формы в Яндексе.

При первом запуске рядом с EXE появляется рабочая `form_config.json` (готовая анкета для сотрудников школы).
**Все пользовательские файлы лежат рядом с EXE**, а не во временной папке PyInstaller или AppData:

| Файл | Назначение |
| --- | --- |
| `form_config.json` | стартовая анкета; не перезаписывается при обновлении EXE |
| `user_settings.json` | последнее открытое JSON, размер и положение окна |
| `.yandex_form_credentials.json` | OAuth/IAM-токен и ID организации (только если пользователь выбрал запоминание) |

**Важно:** сохранённый токен хранится в открытом виде. Не выкладывайте эти файлы в GitHub,
не пересылайте их и не храните EXE в общедоступной папке. Для переносной версии используйте
отдельную папку с ограниченным доступом на запись. Для сброса авторизации удалите
`.yandex_form_credentials.json` при закрытой программе.

## Работа с анкетами

Редактирование: запустите EXE, откройте JSON, добавьте вопросы и проверьте конфигурацию,
затем нажмите «Создать в Яндексе». Публикация по умолчанию выключена.
Создание **не редактирует существующую форму**, а всегда создаёт новую.

## Разработка и запуск из исходников

```powershell
py -3 -m pip install -r requirements.txt
py -3 form_editor.py
py -3 create_yandex_form.py --validate
py -3 create_yandex_form.py --dry-run
py -3 -m unittest -v test_offline
```

## Сборка одного EXE

На Windows 10/11 с Python 3.12:

```powershell
py -3 -m pip install -r requirements-build.txt
py -3 -m unittest -v test_offline
pyinstaller --noconfirm --clean yaformcreator.spec
```

Результат: `dist/YaFormCreator.exe`. Программа использует внешние конфиги рядом с EXE,
а встроенный шаблон копирует туда только при первом запуске. Установщик не нужен.

## CI и релизы

`.github/workflows/build-release.yml` запускает тесты и собирает Windows EXE на каждом PR, push в `main` и ручном запуске `workflow_dispatch`.
Готовый EXE доступен в **Actions → Artifacts**.
Для официального релиза создайте и отправьте тег вида `v2.1.0`:

```bash
git tag v2.1.0
git push origin v2.1.0
```

Workflow создаст GitHub Release и прикрепит **один YaFormCreator.exe**.
Настройки и токены не включаются ни в коммиты, ни в артефакты релиза.

Подробнее: [README_RU.txt](README_RU.txt).