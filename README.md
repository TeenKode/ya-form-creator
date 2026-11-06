# YaFormCreator — универсальный конструктор Яндекс Форм

Настольное приложение для Windows: визуальное создание и редактирование JSON-конфигураций любых анкет, проверка структуры и создание **новых** Яндекс Форм через API.

**В репозитории и EXE нет готовых анкет, форм или демонстрационных конфигураций.** При запуске открывается пустой конструктор. Готовую анкету можно создать вручную, сформировать по [правилам для ИИ](AI_JSON_RULES.md) или открыть локальный JSON через «Открыть JSON».

## Скачать EXE

В [Releases](https://github.com/TeenKode/ya-form-creator/releases) опубликованные версии содержат один автономный файл `YaFormCreator.exe`, собранный PyInstaller на Windows (Python при запуске не требуется).

Скопируйте EXE в **папку с правом записи**. Все персональные файлы будут находиться рядом с ним:

- `user_settings.json` — последние настройки окна и путь к открытой анкете;
- `.yandex_form_credentials.json` — токен и ID организации, **только если явно согласились сохранить**;
- ваши анкеты `*.json` — создаются при нажатии «Сохранить» / «Сохранить как»; никогда не вшиваются в EXE.

**Безопасность:** токен записывается без шифрования. Не храните его в общей папке и не отправляйте вместе с EXE. Для сброса авторизации удалите `.yandex_form_credentials.json` при закрытой программе. Настройки не сохраняются в AppData.

## Создание JSON по описанию

Передайте ИИ документ или описание анкеты и файл [AI_JSON_RULES.md](AI_JSON_RULES.md). Попросите вернуть **только валидный UTF-8 JSON**, соответствующий правилам. Сохраните его под произвольным именем `.json`, откройте в конструкторе и нажмите «Проверить» / «Предпросмотр», затем «Создать в Яндексе».

## Разработка

На Windows с Python 3.12:

```powershell
py -3 -m pip install -r requirements.txt
py -3 app.py
py -3 create_yandex_form.py --config "C:\path\to\my-form.json" --validate
py -3 create_yandex_form.py --config "C:\path\to\my-form.json" --dry-run
py -3 -m unittest -v test_offline
```

`--dry-run` не отправляет запросы в API. Создание формы создаёт **новый** объект; существующую форму программа не изменяет. По умолчанию публикация выключена.

## Сборка и релизы

```powershell
py -3 -m pip install -r requirements-build.txt
py -3 -m unittest -v test_offline
pyinstaller --noconfirm --clean yaformcreator.spec
```

Результат: `dist/YaFormCreator.exe` (one-file). [.github/workflows/build-release.yml](.github/workflows/build-release.yml) тестирует и собирает EXE на Windows в каждом PR и push `main`; EXE сохраняется в Actions → Artifacts. Тег `v*` дополнительно публикует его в GitHub Releases.
