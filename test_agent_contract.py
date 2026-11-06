"""Synthetic contract cases for generated forms, not a live LLM benchmark."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

import engine
from check_agent_form import review_config, validate_schema, main as check_main
from field_formats import format_error
from form_preview import check_answers
from test_offline import FakeSession


def field(label, slug, kind="plain", required=True):
    return {"type": "text", "label": label, "slug": slug, "format": kind, "multiline": False, "required": required}


def contact_contract():
    # The brief deliberately distinguishes a numeric quantity from numeric IDs.
    return {"form": {"name": "Контракт полей", "publish_by_default": False}, "questions": [
        field("ФИО", "full_name", "full_name"),
        field("Телефон РФ", "phone", "phone"),
        field("Электронная почта", "email", "email"),
        field("Ссылка на сайт", "website", "url", False),
        field("ИНН", "tax_id", "inn", False),
        field("Стоимость", "amount", "decimal", False),
        field("Номер заказа", "order_id"),
        field("Номер паспорта", "document_id", required=False),
        field("СНИЛС", "snils", required=False),
        field("Почтовый индекс", "postal_code", required=False),
        field("Международный телефон", "international_phone", required=False),
        {"type": "integer", "slug": "count", "label": "Количество", "min": 0, "required": True},
        {"type": "date", "slug": "visit_date", "label": "Дата визита"},
    ]}


class SpecialFieldTests(unittest.TestCase):
    def test_native_formats_reach_api_with_required_and_length(self):
        for fmt in engine.TEXT_FORMATS:
            with self.subTest(fmt=fmt):
                question = {**field("Поле", "q", fmt), "min_length": 1, "max_length": 100}
                payload = engine.dry_run({"form": {"name": "T"}, "questions": [question]})["questions"][0]
                self.assertEqual(payload["type"], "string")
                self.assertFalse(payload["multiline"])
                self.assertIn({"type": "required"}, payload["validators"])
                self.assertIn({"type": "min", "value": 1}, payload["validators"])
                self.assertIn({"type": "max", "value": 100}, payload["validators"])
                actual = {v["type"] for v in payload["validators"]} - {"required", "min", "max"}
                self.assertEqual(actual, {fmt} if fmt in engine.API_TEXT_FORMATS else set())

    def test_default_multiline_remains_compatible(self):
        plain = {"type": "text", "label": "T", "slug": "q"}
        self.assertTrue(engine.build_question(plain)["multiline"])
        self.assertFalse(engine.build_question({**plain, "format": "email"})["multiline"])

    def test_invalid_formats_and_fake_constraints_rejected_before_network(self):
        invalid = [
            {**field("T", "q"), "format": "fio"}, {**field("T", "q"), "format": []},
            {**field("T", "q", "email"), "multiline": True},
            {"type": "integer", "label": "T", "slug": "q", "format": "phone"},
            {**field("T", "q", "decimal"), "min": 1},
        ]
        invalid += [{**field("T", "q"), key: value} for key, value in
                    (("unique", True), ("validators", [{"type": "email"}]), ("validation", "phone"), ("pattern", "x"), ("regex", "x"))]
        invalid += [{"type": name, "slug": "q", "label": "T"} for name in ("phone", "email", "fio", "number", "string")]
        credentials = {"auth_scheme": "OAuth", "org_header": "X-Org-Id", "token": "dummy", "org_id": "100000"}
        for question in invalid:
            with self.subTest(question=question):
                session = FakeSession()
                with self.assertRaises(engine.ConfigError):
                    engine.create_form({"form": {"name": "T"}, "questions": [question]}, credentials, session=session)
                self.assertEqual(session.requests, [])

    def test_fio_does_not_impose_three_words_or_alphabet(self):
        config = {"form": {"name": "T"}, "questions": [field("ФИО", "q", "full_name")]}
        for name in ("Ли", "Иван Иванов", "Анна-Мария О’Нил", "Élodie d'Arcy"):
            with self.subTest(name=name):
                self.assertEqual(check_answers(config, {"q": name}), [])
        self.assertTrue(check_answers(config, {"q": " "}))

    def test_format_preview_valid_and_invalid(self):
        cases = {
            "email": (["a+tag@example.org"], ["a@", "a b@example.org"]),
            "phone": (["+7 (999) 000-00-00", "89990000000"], ["+12025550123", "123", "номер"]),
            "url": (["https://example.org/path?q=1", "http://пример.рф"], ["example.org", "javascript:alert(1)", "https://a:99999"]),
            "decimal": (["0", "12,5", "-0.25"], ["NaN", "1e309", "12 рублей", "1,2.3"]),
            "inn": (["0000000000", "000000000000"], ["0000000001", "123", "000000000001"]),
        }
        for fmt, (good, bad) in cases.items():
            for value in good:
                with self.subTest(fmt=fmt, value=value):
                    self.assertIsNone(format_error(fmt, value))
            for value in bad:
                with self.subTest(fmt=fmt, value=value):
                    self.assertIsNotNone(format_error(fmt, value))

    def test_optional_empty_format_not_rejected_but_bad_answer_is(self):
        for fmt in engine.API_TEXT_FORMATS:
            config = {"form": {"name": "T"}, "questions": [field("Поле", "q", fmt, False)]}
            with self.subTest(fmt=fmt):
                self.assertEqual(check_answers(config, {"q": ""}), [])
                self.assertTrue(check_answers(config, {"q": "неверно"}))

    def test_identifiers_and_foreign_phones_preserve_string_values(self):
        config = {"form": {"name": "T"}, "questions": [field("Номер заказа", "order"), field("Международный телефон", "phone")]}
        answers = {"order": "000123-АБ", "phone": "+12025550123"}
        original = deepcopy(answers)
        self.assertEqual(check_answers(config, answers), [])
        self.assertEqual(answers, original)

    def test_full_fake_api_creation_sends_special_validators(self):
        session = FakeSession()
        result = engine.create_form(contact_contract(), {"auth_scheme": "OAuth", "org_header": "X-Org-Id", "token": "dummy", "org_id": "100000"}, session=session)
        self.assertFalse(result["published"])
        payloads = {body["slug"]: body for method, url, body in session.requests if method == "POST" and url.endswith("/questions")}
        for slug, fmt in (("phone", "phone"), ("email", "email"), ("tax_id", "inn"), ("website", "url"), ("amount", "decimal")):
            self.assertIn({"type": fmt}, payloads[slug]["validators"])
        self.assertEqual(payloads["order_id"]["type"], "string")
        self.assertEqual(payloads["count"]["type"], "integer")

    def test_semantic_check_catches_numeric_phone_and_wrong_fio_format(self):
        config = {"form": {"name": "T"}, "questions": [{"type": "integer", "slug": "phone", "label": "Телефон"}, field("ФИО", "name", "email")]}
        warnings = review_config(config)
        self.assertTrue(any(w.startswith("phone:") for w in warnings))
        self.assertTrue(any(w.startswith("name:") for w in warnings))

    def test_semantic_check_email_missing_format_and_initial(self):
        question = {**field("Электронная почта", "email"), "initial": "example@example.org"}
        warnings = review_config({"form": {"name": "T"}, "questions": [question]})
        self.assertEqual(len(warnings), 2)

    def test_correct_contact_contract_has_no_semantic_warnings(self):
        self.assertEqual(review_config(contact_contract()), [])

    def test_hidden_special_field_is_not_locally_required(self):
        config = {"form": {"name": "T"}, "questions": [{**field("Почта", "q", "email", False), "hidden": True}]}
        self.assertEqual(check_answers(config, {"q": "bad"}), [])


class SchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import jsonschema
        except ImportError:
            if os.getenv("YAFORM_REQUIRE_SCHEMA_TESTS"):
                raise RuntimeError("CI must install requirements-dev.txt")
            raise unittest.SkipTest("Install requirements-dev.txt for schema tests")
        cls.jsonschema = jsonschema

    def test_schema_is_valid_and_accepts_contract_and_all_legacy_types(self):
        from test_offline import synthetic_config
        schema = json.loads((Path(__file__).parent / "schema/form.schema.json").read_text(encoding="utf-8"))
        self.jsonschema.Draft202012Validator.check_schema(schema)
        validate_schema(contact_contract())
        validate_schema(synthetic_config())

    def test_schema_rejects_unknown_typo_and_native_type(self):
        for update in ({"foramt": "email"}, {"type": "email"}, {"unique": True}):
            config = contact_contract(); config["questions"][0].update(update)
            with self.subTest(update=update), self.assertRaises(engine.ConfigError):
                validate_schema(config)

    def test_exclusive_checkbox_and_special_field_share_contract(self):
        from test_exclusive import make_config
        config = make_config()
        config["questions"][0]["exclusive_options"] = ["Не использую"]
        config["questions"].append(field("Почта", "email", "email"))
        validate_schema(config)
        payloads = engine.dry_run(config)["questions"]
        self.assertEqual(payloads[0]["widget"], "radio")
        self.assertIn({"type": "email"}, payloads[-1]["validators"])

    def test_checker_cli_is_offline_and_has_distinct_statuses(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "agent.json"
            for config, expected in ((contact_contract(), 0),
                                     ({"form": {"name": "T"}, "questions": [{"type": "integer", "slug": "q", "label": "Телефон"}]}, 3),
                                     ({"form": {"name": "T"}, "questions": [field("T", "q", "unknown")]}, 2)):
                path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), patch.object(engine, "create_form", side_effect=AssertionError("must be offline")):
                    self.assertEqual(check_main(["--config", str(path)]), expected)

    def test_handoff_links_exist(self):
        root = Path(__file__).parent
        for filename in ("AGENTS.md", "START_HERE_AI.md", "AI_JSON_RULES.md", "docs/FIELD_GUIDE_RU.md", "docs/AGENT_CHECKS_RU.md", "schema/form.schema.json"):
            self.assertTrue((root / filename).is_file(), filename)


class FieldEditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            root = tk.Tk(); root.destroy()
        except tk.TclError as exc:
            raise unittest.SkipTest(str(exc))

    def test_special_format_survives_editor_and_can_be_cleared(self):
        from form_editor import QuestionDialog
        root = tk.Tk(); root.withdraw()
        try:
            with patch.object(tk.Toplevel, "wait_window"):
                dialog = QuestionDialog(root, field("Почта", "email", "email"))
            self.assertEqual(dialog.collect()["format"], "email")
            dialog.v_format.set(engine.TEXT_FORMATS["plain"]); dialog.update_text_format()
            self.assertNotIn("format", dialog.collect())
            dialog.destroy()
        finally:
            root.destroy()

    def test_preview_uses_single_line_and_keeps_leading_zero(self):
        from form_preview import PreviewWindow
        root = tk.Tk(); root.withdraw()
        try:
            preview = PreviewWindow(root, {"form": {"name": "T"}, "questions": [field("Номер заказа", "q")]})
            root.update()
            from tkinter import ttk
            def descendants(widget):
                for child in widget.winfo_children():
                    yield child; yield from descendants(child)
            entries = [w for w in descendants(preview) if isinstance(w, ttk.Entry)]
            self.assertEqual(len(entries), 1)
            entries[0].insert(0, "000123")
            self.assertEqual(preview.collect_answers()["q"], "000123")
            preview.destroy()
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
