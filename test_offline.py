"""Offline unit tests; inputs are built in memory, no bundled survey files."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

import engine


def synthetic_config():
    """Minimal synthetic data constructed by tests, not distributed as a ready form."""
    return {
        "form": {"name": "Тестовая конфигурация", "publish_by_default": False},
        "questions": [
            {"type": "radio", "label": "Вариант", "slug": "choice", "required": True,
             "options": ["А", "Б", "Другое"],
             "other": {"option": "Другое", "label": "Поясните"}},
            {"type": "checkbox", "label": "Несколько вариантов", "slug": "multi", "options": ["А", "Б"]},
            {"type": "text", "label": "Комментарий", "slug": "commentary"},
            {"type": "matrix", "label": "Таблица", "slug": "matrix", "rows": ["1"], "columns": ["А", "Б"]},
            {"type": "boolean", "label": "Да или нет", "slug": "yesno"},
            {"type": "integer", "label": "Число", "slug": "number"},
            {"type": "date", "label": "Дата", "slug": "date"},
            {"type": "section", "label": "Раздел"},
            {"type": "comment", "label": "Информация"},
        ],
        "conditions": [{"target": "commentary", "source": "choice", "answers": ["Б"]}]
    }


class FakeResponse:
    def __init__(self, body=None, code=200):
        self.ok = code < 400
        self.status_code = code
        self.body = body if body is not None else {}
        self.text = json.dumps(self.body)

    def json(self):
        return self.body


class FakeSession:
    def __init__(self, fail_at=None):
        self.requests = []
        self.fail_at = fail_at
        self.counter = 10
        self.is_published = False

    def get(self, url, headers=None, timeout=None):
        self.requests.append(("GET", url, None))
        return FakeResponse({"results": []})

    def post(self, url, headers=None, timeout=None, json=None):
        self.requests.append(("POST", url, json))
        if self.fail_at and self.fail_at in url:
            return FakeResponse({"detail": "mock error"}, 422)
        if url.endswith("/surveys"):
            return FakeResponse({"id": "aaaaaaaaaaaaaaaaaaaaaaaa"})
        if url.endswith("/publish"):
            self.is_published = True
            return FakeResponse({})
        if url.endswith("/questions"):
            self.counter += 1
            return FakeResponse({"id": self.counter, "slug": json.get("slug"),
                                 "items": [{"id": i+1, "label": itm["label"]}
                                           for i, itm in enumerate(json.get("items", []))]})
        if url.endswith("/conditions"):
            return FakeResponse({"id": self.counter + 100})
        return FakeResponse({}, 404)


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.config = synthetic_config()
        self.creds = {"auth_scheme": "OAuth", "org_header": "X-Org-Id", "token": "dummy",
                      "org_id": "100000"}

    def test_all_types_generated(self):
        payloads, conditions = engine.expand_questions(self.config)
        self.assertEqual(len(payloads), 10)
        self.assertEqual(len(conditions), 2)
        self.assertTrue({"boolean", "date", "integer", "matrix", "enum", "string", "comment"}
                        <= {q["type"] for q in payloads})

    def test_fake_api_full_creation_published(self):
        fake = FakeSession()
        result = engine.create_form(self.config, self.creds, publish=True, session=fake)
        self.assertTrue(result["published"])
        self.assertEqual(result["question_count"], 10)
        self.assertEqual(result["conditions_count"], 2)
        self.assertTrue(fake.is_published)
        self.assertEqual(sum(u.endswith("/surveys") and op == "POST" for op, u, _ in fake.requests), 1)

    def test_failed_condition_does_not_publish(self):
        fake = FakeSession(fail_at="/conditions")
        with self.assertRaisesRegex(engine.ApiError, "частично"):
            engine.create_form(self.config, self.creds, publish=True, session=fake)
        self.assertFalse(fake.is_published)

    def test_unknown_condition_answer_rejected(self):
        bad = copy.deepcopy(self.config)
        bad["conditions"][0]["answers"] = ["Несуществующий вариант"]
        with self.assertRaisesRegex(engine.ConfigError, "отсутствуют"):
            engine.validate_config(bad)

    def test_duplicate_slug_rejected(self):
        bad = copy.deepcopy(self.config)
        bad["questions"][1]["slug"] = bad["questions"][0]["slug"]
        with self.assertRaisesRegex(engine.ConfigError, "повторяется"):
            engine.validate_config(bad)

    def test_auto_other_slug_collision_rejected(self):
        bad = copy.deepcopy(self.config)
        bad["questions"].append({"type": "text", "label": "Текст", "slug": "choice_other"})
        with self.assertRaisesRegex(engine.ConfigError, "уже занят"):
            engine.validate_config(bad)

    def test_backward_conditions_rejected(self):
        bad = copy.deepcopy(self.config)
        bad["conditions"] = [{"source": "multi", "target": "choice", "answers": ["А"]}]
        with self.assertRaisesRegex(engine.ConfigError, "раньше"):
            engine.validate_config(bad)

    def test_correct_quiz_json(self):
        config = {"form": {"name": "Тест"}, "questions": [
            {"type": "radio", "label": "Проверка", "slug": "q", "has_quiz": True,
             "options": [{"label": "А", "correct": False, "scores": 0},
                         {"label": "Б", "correct": True, "scores": 1}]}]}
        self.assertEqual(engine.dry_run(config)["questions"][0]["items"][1]["scores"], 1)

    def test_raw_api(self):
        raw = {"form": {"name": "Тест"}, "questions": [{"type": "api", "label": "Контакт", "slug": "email",
               "payload": {"type": "email", "label": "Контакт", "slug": "email", "validators": []}}]}
        self.assertEqual(engine.dry_run(raw)["questions"][0]["type"], "email")

    def test_portable_settings_separate_from_credentials(self):
        with tempfile.TemporaryDirectory() as d:
            fp = Path(d) / "user_settings.json"
            engine.save_settings({"window_geometry": "1024x768+40+50", "last_form_path": "C:/a.json",
                                  "token": "PRIVATE"}, fp)
            self.assertEqual(engine.load_settings(fp)["last_form_path"], "C:/a.json")
            self.assertNotIn("PRIVATE", fp.read_text(encoding="utf-8"))

    def test_credential_save_in_selected_directory(self):
        with tempfile.TemporaryDirectory() as d:
            fp = Path(d) / ".yandex_form_credentials.json"
            engine.save_credentials(self.creds, fp)
            self.assertEqual(engine.load_credentials(fp), self.creds)

    def test_exe_path_runtime(self):
        import sys
        from unittest.mock import patch
        with patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", "/Portable/YaFormCreator.exe"):
            self.assertEqual(engine.runtime_dir(), Path("/Portable"))

    def test_no_bundled_questionnaire(self):
        root = Path(__file__).parent
        self.assertFalse((root / "form_config.json").exists())
        self.assertFalse((root / "example_all_types.json").exists())

    def test_utf8_load(self):
        with tempfile.TemporaryDirectory() as d:
            fp = Path(d) / "тест.json"
            fp.write_text(json.dumps(self.config, ensure_ascii=False), encoding="utf-8-sig")
            self.assertEqual(engine.load_config(fp)["form"]["name"], self.config["form"]["name"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
