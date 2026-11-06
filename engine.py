"""Универсальный генератор Яндекс Форм: формат данных, валидация, API.

Никаких привязок к содержимому анкет. Формат конфигурации сохраняет
обратную совместимость с create_yandex_form_it.py (октябрь 2026).
"""
from __future__ import annotations

import json
import os
import re
import sys
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any, Callable

API = "https://api.forms.yandex.net/v1"
def runtime_dir() -> Path:
    """Writable directory adjacent to executable, never PyInstaller's _MEIPASS."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = runtime_dir()
DEFAULT_CONFIG = BASE_DIR / "form_config.json"
CREDENTIALS_FILE = BASE_DIR / ".yandex_form_credentials.json"
SETTINGS_FILE = BASE_DIR / "user_settings.json"


def load_settings(path: Path = SETTINGS_FILE) -> dict:
    """User preferences only. No credentials in this JSON."""
    try:
        val = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(val, dict):
            return {k: val[k] for k in ("last_form_path", "window_geometry")
                    if isinstance(val.get(k), str)}
    except (OSError, ValueError):
        pass
    return {}


def save_settings(settings: dict, path: Path = SETTINGS_FILE) -> None:
    data = {k: settings[k] for k in ("last_form_path", "window_geometry")
            if isinstance(settings.get(k), str)}
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)
TIMEOUT = 30
SLUG_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
ENUM_TYPES = {"radio", "checkbox", "dropdown", "scale", "stars", "onerow"}
CONDITION_SOURCE_TYPES = {"radio", "checkbox", "dropdown"}
QUESTION_TYPES = ENUM_TYPES | {"text", "matrix", "boolean", "integer", "date", "section", "comment", "api"}


class ConfigError(ValueError):
    pass


class ApiError(RuntimeError):
    pass


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _unique_labels(values: list[Any], context: str) -> None:
    labels = []
    for v in values:
        label = v if isinstance(v, str) else v.get("label") if isinstance(v, dict) else None
        if not _nonempty(label):
            raise ConfigError(f"{context}: все элементы должны иметь непустой label.")
        labels.append(label)
    if len(labels) != len(set(labels)):
        raise ConfigError(f"{context}: есть повторяющиеся варианты.")


def _validate_nonneg(item: dict, field: str, context: str) -> None:
    if field in item and (type(item[field]) is not int or item[field] < 0):
        raise ConfigError(f"{context}.{field}: ожидается неотрицательное целое число.")


def _validate_date_field(item: dict, field: str, context: str) -> None:
    if field in item:
        try:
            date.fromisoformat(item[field])
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"{context}.{field}: формат даты YYYY-MM-DD.") from exc


def load_config(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    try:
        config = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise ConfigError(f"Не удалось открыть файл {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Ошибка JSON, строка {exc.lineno}, столбец {exc.colno}: {exc.msg}") from exc
    validate_config(config)
    return config


def validate_config(config: dict[str, Any]) -> None:
    if not isinstance(config, dict):
        raise ConfigError("Корень JSON должен быть объектом.")
    form = config.get("form")
    questions = config.get("questions")
    if not isinstance(form, dict) or not _nonempty(form.get("name")):
        raise ConfigError("form.name: укажите название формы.")
    for flag in ("allow_multiple_answers", "need_auth", "publish_by_default"):
        if flag in form and type(form[flag]) is not bool:
            raise ConfigError(f"form.{flag}: ожидается true или false.")
    if not isinstance(questions, list) or not questions:
        raise ConfigError("questions: необходим непустой список элементов.")
    slugs: set[str] = set()
    answer_options: dict[str, set[str]] = {}
    source_types: dict[str, str] = {}
    indices: dict[str, int] = {}
    deferred_others: list[tuple[str, str, str]] = []
    for idx, item in enumerate(questions, 1):
        where = f"questions[{idx}]"
        if not isinstance(item, dict):
            raise ConfigError(f"{where}: ожидается объект.")
        qtype = item.get("type")
        if qtype not in QUESTION_TYPES:
            raise ConfigError(f"{where}: неизвестный тип {qtype!r}.")
        if not _nonempty(item.get("label")):
            raise ConfigError(f"{where}.label: необходим текст.")
        if "required" in item and type(item["required"]) is not bool:
            raise ConfigError(f"{where}.required: ожидается true или false.")
        if item.get("hidden") is True and item.get("required") is True:
            raise ConfigError(f"{where}: нельзя одновременно сделать вопрос скрытым и обязательным.")
        if qtype in {"section", "comment"}:
            if "other" in item:
                raise ConfigError(f"{where}: other доступен только для вариантов ответа.")
            continue
        slug = item.get("slug")
        if not _nonempty(slug) or not SLUG_RE.fullmatch(slug):
            raise ConfigError(f"{where}.slug: используйте латиницу, цифры, _ или -; первый символ — буква.")
        if slug in slugs:
            raise ConfigError(f"{where}: повторяется slug {slug!r}.")
        slugs.add(slug)
        indices[slug] = idx
        if qtype in ENUM_TYPES:
            opts = item.get("options")
            if not isinstance(opts, list) or len(opts) < 2:
                raise ConfigError(f"{where}.options: минимум два варианта.")
            _unique_labels(opts, f"{where}.options")
            for opt in opts:
                if isinstance(opt, dict):
                    for key in ("correct", "hidden"):
                        if key in opt and type(opt[key]) is not bool:
                            raise ConfigError(f"{where}.options.{key}: ожидается true/false.")
                    if "scores" in opt and (isinstance(opt["scores"], bool) or not isinstance(opt["scores"], (int, float))):
                        raise ConfigError(f"{where}.options.scores: ожидается число.")
            answer_options[slug] = set(v if isinstance(v, str) else v["label"] for v in opts)
            source_types[slug] = qtype
            if qtype == "checkbox":
                for field in ("min_choices", "max_choices"):
                    _validate_nonneg(item, field, where)
                    if field in item and item[field] > len(opts):
                        raise ConfigError(f"{where}.{field}: больше числа вариантов.")
                if item.get("min_choices", 0) > item.get("max_choices", len(opts)):
                    raise ConfigError(f"{where}: min_choices больше max_choices.")
        elif qtype == "matrix":
            for field, minimum in (("rows", 1), ("columns", 2)):
                vals = item.get(field)
                if not isinstance(vals, list) or len(vals) < minimum:
                    raise ConfigError(f"{where}.{field}: минимум {minimum} элементов.")
                _unique_labels(vals, f"{where}.{field}")
        elif qtype == "text":
            for field in ("min_length", "max_length"):
                _validate_nonneg(item, field, where)
            if item.get("min_length", 0) > item.get("max_length", float('inf')):
                raise ConfigError(f"{where}: min_length больше max_length.")
        elif qtype == "integer":
            for field in ("min", "max"):
                if field in item and type(item[field]) is not int:
                    raise ConfigError(f"{where}.{field}: требуется целое число.")
            if "min" in item and "max" in item and item["min"] > item["max"]:
                raise ConfigError(f"{where}: min больше max.")
        elif qtype == "date":
            for field in ("min", "max"):
                _validate_date_field(item, field, where)
            if "min" in item and "max" in item and item["min"] > item["max"]:
                raise ConfigError(f"{where}: min позже max.")
        elif qtype == "api":
            payload = item.get("payload")
            if not isinstance(payload, dict) or not _nonempty(payload.get("type")):
                raise ConfigError(f"{where}.payload: укажите необработанный JSON объекта вопроса API.")
            if payload.get("slug", slug) != slug:
                raise ConfigError(f"{where}.payload.slug должен совпадать с slug элемента.")
        other = item.get("other")
        if other is not None:
            if qtype not in CONDITION_SOURCE_TYPES:
                raise ConfigError(f"{where}.other допустим только для radio, checkbox, dropdown.")
            if not isinstance(other, dict):
                raise ConfigError(f"{where}.other: ожидается объект.")
            other_option = other.get("option", "Другое")
            if other_option not in answer_options[slug]:
                raise ConfigError(f"{where}.other.option: вариант {other_option!r} отсутствует.")
            other_slug = other.get("slug", f"{slug}_other")
            if not _nonempty(other_slug) or not SLUG_RE.fullmatch(other_slug):
                raise ConfigError(f"{where}.other.slug: недопустимый slug.")
            deferred_others.append((other_slug, slug, other_option))
    for other_slug, source, _ in deferred_others:
        if other_slug in slugs:
            raise ConfigError(f"Слаг поля 'Другое' {other_slug!r} уже занят.")
        slugs.add(other_slug)
        indices[other_slug] = indices[source]
    conditions = config.get("conditions", [])
    if not isinstance(conditions, list):
        raise ConfigError("conditions должен быть массивом.")
    generated_other_slugs = {target for target, _, _ in deferred_others}
    all_conds = conditions + [
        {"target": target, "source": src, "answers": [option]}
        for target, src, option in deferred_others
    ]
    edges: dict[str, set[str]] = {}
    for idx, cond in enumerate(all_conds, 1):
        where = f"conditions[{idx}]"
        if not isinstance(cond, dict):
            raise ConfigError(f"{where}: ожидается объект.")
        target, source = cond.get("target"), cond.get("source")
        if target not in slugs or source not in slugs:
            raise ConfigError(f"{where}: несуществующий target/source: {target!r} <- {source!r}.")
        if source not in answer_options or source_types.get(source) not in CONDITION_SOURCE_TYPES:
            raise ConfigError(f"{where}: источник {source!r} должен иметь тип radio, checkbox или dropdown.")
        # UI Яндекс Форм позволяет ветвление только от предшествующих вопросов.
        if indices[source] >= indices[target] and not (target in generated_other_slugs and indices[source] == indices[target]):
            raise ConfigError(f"{where}: источник условия {source!r} должен идти раньше {target!r}.")
        answers = cond.get("answers", [])
        if not isinstance(answers, list) or not answers or not all(_nonempty(a) for a in answers):
            raise ConfigError(f"{where}.answers: нужен минимум один вариант ответа.")
        unknown = set(answers) - answer_options[source]
        if unknown:
            raise ConfigError(f"{where}.answers: варианты отсутствуют в {source}: {', '.join(sorted(unknown))}.")
        if cond.get("operator", "and") not in {"and", "or"}:
            raise ConfigError(f"{where}.operator: допустимы and/or.")
        if cond.get("condition", "eq") not in {"eq", "neq"}:
            raise ConfigError(f"{where}.condition: допустимы eq/neq.")
        edges.setdefault(source, set()).add(target)
    visited: set[str] = set()
    working: set[str] = set()
    def visit(node: str) -> None:
        if node in working:
            raise ConfigError("Условия показа образуют циклическую зависимость.")
        if node in visited:
            return
        working.add(node)
        for child in edges.get(node, set()):
            visit(child)
        working.remove(node)
        visited.add(node)
    for node in edges:
        visit(node)


def enum_items(options: list[str | dict]) -> list[dict]:
    return [{"label": option} if isinstance(option, str) else deepcopy(option) for option in options]


def validators_for(q: dict) -> list[dict]:
    rules = [{"type": "required"}] if q.get("required", False) else []
    mapping = {
        "checkbox": (("min_choices", "min"), ("max_choices", "max")),
        "text": (("min_length", "min"), ("max_length", "max")),
        "integer": (("min", "min"), ("max", "max")),
        "date": (("min", "min"), ("max", "max")),
    }
    for original, rule in mapping.get(q["type"], ()):
        if original in q:
            rules.append({"type": rule, "value": q[original]})
    return rules


def build_question(q: dict) -> dict:
    qtype = q["type"]
    common = {"label": q["label"]}
    for field in ("comment", "placeholder", "hidden"):
        if field in q and q[field] not in (None, ""):
            common[field] = q[field]
    if qtype in ("comment", "section"):
        common.pop("placeholder", None)
        return {**common, "type": "comment", "header": bool(q.get("header", qtype == "section"))}
    if qtype == "api":
        payload = deepcopy(q["payload"])
        payload = {**payload, **common, "slug": q["slug"]}
        if q.get("required") is True:
            validators = payload.setdefault("validators", [])
            if not any(v.get("type") == "required" for v in validators):
                validators.append({"type": "required"})
        return payload
    common["slug"] = q["slug"]
    if qtype in ENUM_TYPES:
        w = {"scale": "onerow", "stars": "stars", "onerow": "onerow"}.get(qtype, qtype)
        payload = {**common, "type": "enum", "widget": q.get("widget", w),
                   "items": enum_items(q["options"]), "validators": validators_for(q)}
        if q.get("has_quiz") is True:
            payload["has_quiz"] = True
        for field in ("show_first", "show_suggest", "modify_choices"):
            if field in q:
                payload[field] = q[field]
        return payload
    if qtype == "text":
        return {**common, "type": "string", "multiline": bool(q.get("multiline", True)),
                "validators": validators_for(q)}
    if qtype == "matrix":
        return {**common, "type": "matrix",
                "rows": [{"slug": f"{q['slug']}_r{i}", "label": v if isinstance(v,str) else v['label']}
                         for i, v in enumerate(q["rows"], 1)],
                "columns": [{"slug": f"{q['slug']}_c{i}", "label": v if isinstance(v,str) else v['label']}
                            for i, v in enumerate(q["columns"], 1)],
                "validators": validators_for(q)}
    if qtype in {"boolean", "integer", "date"}:
        payload = {**common, "type": qtype, "validators": validators_for(q)}
        if "initial" in q:
            payload["initial"] = q["initial"]
        return payload
    raise ConfigError(f"Неизвестный тип {qtype!r}.")


def expand_questions(config: dict) -> tuple[list[dict], list[dict]]:
    validate_config(config)
    payloads = []
    conditions = deepcopy(config.get("conditions", []))
    for q in config["questions"]:
        payloads.append(build_question(q))
        other = q.get("other")
        if other:
            slug = other.get("slug", q["slug"] + "_other")
            payloads.append({"type": "string", "label": other.get("label", "Укажите свой вариант"),
                             "slug": slug, "multiline": bool(other.get("multiline", False)),
                             "placeholder": other.get("placeholder", "Введите свой вариант"),
                             "validators": [{"type": "required"}] if other.get("required", True) else []})
            conditions.append({"target": slug, "source": q["slug"],
                               "answers": [other.get("option", "Другое")], "operator": "and"})
    return payloads, conditions


def build_survey_body(config: dict, name: str | None = None) -> dict:
    form = config["form"]
    return {
        "name": name or form["name"],
        "allow_multiple_answers": bool(form.get("allow_multiple_answers", True)),
        "need_auth": bool(form.get("need_auth", False)),
        "texts": {
            "submit": form.get("submit_text", "Отправить"),
            "title": form.get("success_title", "Спасибо за ответы!"),
            "subtitle": form.get("success_subtitle", "")
        }
    }


def dry_run(config: dict) -> dict:
    payloads, conditions = expand_questions(config)
    return {"survey": build_survey_body(config), "questions": payloads, "conditions": conditions}


def load_credentials(path: Path = CREDENTIALS_FILE) -> dict | None:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if isinstance(obj, dict) and all(_nonempty(obj.get(k)) for k in
                                     ("auth_scheme", "org_header", "token", "org_id")):
        if obj["auth_scheme"] in {"OAuth", "Bearer"} and obj["org_header"] in {"X-Org-Id", "X-Cloud-Org-Id"}:
            return obj
    return None


def save_credentials(data: dict, path: Path = CREDENTIALS_FILE) -> None:
    clean = {k: data[k] for k in ("auth_scheme", "org_header", "token", "org_id")}
    # Atomic replace prevents truncating credentials when disk writes fail.
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            tmp.chmod(0o600)
        except OSError:
            pass
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink()


def environment_credentials() -> dict | None:
    token = os.getenv("YANDEX_FORMS_TOKEN")
    org = os.getenv("YANDEX_FORMS_ORG_ID")
    if not token or not org:
        return None
    return {
        "auth_scheme": os.getenv("YANDEX_FORMS_AUTH_SCHEME", "OAuth"),
        "org_header": os.getenv("YANDEX_FORMS_ORG_HEADER", "X-Org-Id"),
        "token": token,
        "org_id": org,
    }


def _response_error(response: Any) -> str:
    try:
        body = json.dumps(response.json(), ensure_ascii=False)
    except (ValueError, TypeError):
        body = response.text or "(пустой ответ)"
    return body[:3000]


def _api_call(session: Any, method: str, url: str, headers: dict, payload: Any = None) -> dict:
    try:
        if method == "GET":
            resp = session.get(url, headers=headers, timeout=TIMEOUT)
        else:
            kw = {"headers": headers, "timeout": TIMEOUT}
            if payload is not None:
                kw["json"] = payload
            resp = session.post(url, **kw)
    except Exception as exc:
        # Requests raises RequestException and subclasses; no retry on POST (could duplicate).
        raise ApiError(f"Сбой сети при {method} {url}: {type(exc).__name__}: {exc}") from exc
    if not resp.ok:
        raise ApiError(f"Ошибка API {resp.status_code} при {method} {url}: {_response_error(resp)}")
    try:
        return resp.json()
    except ValueError:
        return {}


def create_form(config: dict, credentials: dict, *, name: str | None = None,
                publish: bool = False, progress: Callable[[str], None] | None = None,
                session: Any = None) -> dict:
    """Creates a *new* form. On failure reports the draft ID if it already exists.

    API POSTs are deliberately not automatically retried to avoid duplicates.
    """
    validate_config(config)
    if credentials.get("auth_scheme") not in {"OAuth", "Bearer"}:
        raise ConfigError("auth_scheme должен быть OAuth или Bearer.")
    if credentials.get("org_header") not in {"X-Org-Id", "X-Cloud-Org-Id"}:
        raise ConfigError("org_header должен быть X-Org-Id или X-Cloud-Org-Id.")
    if not credentials.get("token") or not credentials.get("org_id"):
        raise ConfigError("Не заполнены токен или ID организации.")
    if session is None:
        try:
            import requests
        except ImportError as exc:
            raise ApiError("Не найден пакет requests. Установите: py -3 -m pip install requests") from exc
        session = requests.Session()
    log = progress or (lambda _: None)
    headers = {
        "Authorization": credentials["auth_scheme"] + " " + credentials["token"],
        "Content-Type": "application/json", credentials["org_header"]: credentials["org_id"],
    }
    log("Проверка доступа к организации...")
    # Other header variant may work for the same organization.
    org_key = credentials["org_header"]
    alternatives = [org_key, "X-Cloud-Org-Id" if org_key == "X-Org-Id" else "X-Org-Id"]
    errors = []
    for key in alternatives:
        candidate = {k: v for k, v in headers.items() if k not in ("X-Org-Id", "X-Cloud-Org-Id")}
        candidate[key] = credentials["org_id"]
        try:
            _api_call(session, "GET", f"{API}/surveys", candidate)
            headers = candidate
            break
        except ApiError as exc:
            errors.append(str(exc))
    else:
        raise ApiError("Не удалось проверить доступ к организации. " + "; ".join(errors))
    payloads, conds = expand_questions(config)
    log("Создание формы...")
    survey = _api_call(session, "POST", f"{API}/surveys", headers, build_survey_body(config, name))
    survey_id = survey.get("id")
    if not survey_id:
        raise ApiError("API подтвердил создание формы, но не вернул её id. Проверьте кабинет Яндекс Форм.")
    survey_id = str(survey_id)
    urls = {"survey_id": survey_id,
            "edit_url": f"https://forms.yandex.ru/admin/{survey_id}",
            "fill_url": f"https://forms.yandex.ru/cloud/{survey_id}",
            "published": False, "question_count": 0, "conditions_count": 0,
            "org_header": next(k for k in ("X-Org-Id", "X-Cloud-Org-Id") if k in headers)}
    log(f"Черновик создан: {urls['edit_url']}")
    created: dict[str, dict] = {}
    try:
        for i, item in enumerate(payloads, 1):
            answer = _api_call(session, "POST", f"{API}/surveys/{survey_id}/questions", headers, item)
            if item.get("slug"):
                if not answer.get("id"):
                    raise ApiError(f"API не вернул id вопроса {item['slug']}.")
                created[item["slug"]] = answer
            urls["question_count"] = i
            log(f"Вопросы: {i}/{len(payloads)} — {item['label'][:70]}")
        for j, spec in enumerate(conds, 1):
            src = created[spec["source"]]
            target = created[spec["target"]]
            options = {it.get("label"): it for it in src.get("items", [])}
            items = []
            for answer in spec["answers"]:
                if answer not in options:
                    raise ApiError(f"API не вернул вариант {answer!r} в вопросе {spec['source']!r}.")
                opt = options[answer]
                value = opt.get("id", opt.get("slug"))
                if value is None:
                    raise ApiError(f"API не вернул id/slug варианта {answer!r}.")
                items.append({"type": "question", "condition": spec.get("condition", "eq"),
                              "question": src.get("slug", spec["source"]), "value": str(value)})
            _api_call(session, "POST", f"{API}/surveys/{survey_id}/questions/{target['id']}/conditions",
                      headers, {"operator": spec.get("operator", "and"), "items": items})
            urls["conditions_count"] = j
            log(f"Условия показа: {j}/{len(conds)}")
        if publish:
            # Only publish when every question and condition was successfully added.
            _api_call(session, "POST", f"{API}/surveys/{survey_id}/publish", headers)
            urls["published"] = True
            log("Форма опубликована.")
        else:
            log("Форма сохранена как черновик.")
    except (ApiError, KeyError) as exc:
        raise ApiError(f"Форма создана частично. Черновик: {urls['edit_url']}\nПричина: {exc}") from exc
    return urls
