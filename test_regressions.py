"""Regressions found during review: malformed input, data safety, API failures."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import engine
from dialogs import replace_question
from form_preview import visible_slugs, check_answers
from test_offline import synthetic_config, FakeSession, FakeResponse


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.config = synthetic_config()
        self.creds = {"auth_scheme": "OAuth", "org_header": "X-Org-Id", "token": "very-secret-token", "org_id": "100000"}

    def test_unhashable_input_is_config_error(self):
        for field, value in (("type", []), ("hidden", "yes"), ("comment", {}), ("widget", [])):
            with self.subTest(field=field):
                config = deepcopy(self.config); config["questions"][0][field] = value
                with self.assertRaises(engine.ConfigError):
                    engine.validate_config(config)
        for field in ("source", "target", "condition", "operator"):
            with self.subTest(field=field):
                config = deepcopy(self.config); config["conditions"][0][field] = []
                with self.assertRaises(engine.ConfigError):
                    engine.validate_config(config)

    def test_invalid_other_rejected(self):
        for field, value in (("option", []), ("required", "false"), ("multiline", 1), ("label", {})):
            with self.subTest(field=field):
                config = deepcopy(self.config); config["questions"][0]["other"][field] = value
                with self.assertRaises(engine.ConfigError):
                    engine.validate_config(config)

    def test_api_validators_must_be_objects(self):
        for validators in (None, {}, ["required"], [None], [{"type": ""}]):
            config = {"form": {"name": "T"}, "questions": [{"type": "api", "label": "T", "slug": "q", "payload": {"type": "string", "validators": validators}}]}
            with self.subTest(validators=validators), self.assertRaises(engine.ConfigError):
                engine.dry_run(config)

    def test_date_requires_canonical_format(self):
        for value in ("20260102", "2026-W01-1", "2026-02-30", 20260101):
            config = {"form": {"name": "T"}, "questions": [{"type": "date", "label": "T", "slug": "q", "min": value}]}
            with self.subTest(value=value), self.assertRaises(engine.ConfigError):
                engine.validate_config(config)

    def test_single_choice_has_server_validator(self):
        for kind in engine.ENUM_TYPES:
            payload = engine.build_question({"type": kind, "label": "T", "slug": "q", "options": ["A", "B"]})
            self.assertEqual({"type": "single"} in payload["validators"], kind != "checkbox")

    def test_empty_draft_roundtrip_but_cannot_create(self):
        config = {"form": {"name": "Заготовка"}, "questions": []}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "draft.json"; path.write_text(json.dumps(config), encoding="utf-8")
            self.assertEqual(engine.load_config(path, allow_empty=True), config)
            with self.assertRaises(engine.ConfigError):
                engine.load_config(path)
        fake = FakeSession()
        with self.assertRaises(engine.ConfigError):
            engine.create_form(config, self.creds, session=fake)
        self.assertEqual(fake.requests, [])

    def test_bad_encoding_reports_config_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"; path.write_bytes(b'\xff\xfe\x80')
            with self.assertRaises(engine.ConfigError):
                engine.load_config(path)

    def test_hidden_source_and_other_do_not_appear(self):
        self.config["questions"][0].update(hidden=True, required=False)
        answers = {"choice": "Другое", "choice_other": "x"}
        visible = visible_slugs(self.config, answers)
        self.assertFalse({"choice", "choice_other", "commentary"} & visible)

    def test_zero_is_valid_required_number(self):
        config = {"form": {"name": "T"}, "questions": [{"type": "integer", "label": "T", "slug": "q", "required": True}]}
        self.assertEqual(check_answers(config, {"q": 0}), [])

    def test_rename_updates_direct_and_other_references(self):
        self.config["conditions"].append({"source": "multi", "target": "choice_other", "answers": ["А"]})
        question = deepcopy(self.config["questions"][0]); question["slug"] = "renamed"
        result = replace_question(self.config, 0, question)
        self.assertEqual(result["conditions"][0]["source"], "renamed")
        self.assertEqual(result["conditions"][1]["target"], "renamed_other")
        self.assertEqual(self.config["questions"][0]["slug"], "choice")

    def test_invalid_credentials_make_no_requests(self):
        for updates in ({"token": "a\nb"}, {"token": " "}, {"org_id": "русский"}, {"auth_scheme": "Bearer"}):
            fake = FakeSession()
            with self.subTest(updates=updates), self.assertRaises(engine.ConfigError):
                engine.create_form(self.config, {**self.creds, **updates}, session=fake)
            self.assertEqual(fake.requests, [])

    def test_http_error_redacts_token_and_does_not_switch_org(self):
        fake = FakeSession()
        def denied(url, headers=None, timeout=None):
            fake.requests.append(("GET", url, headers))
            return FakeResponse({"detail": headers["Authorization"]}, 403)
        fake.get = denied
        with self.assertRaises(engine.ApiError) as cm:
            engine.create_form(self.config, self.creds, session=fake)
        self.assertNotIn(self.creds["token"], str(cm.exception))
        self.assertIn("forms:write", str(cm.exception))
        self.assertEqual(len(fake.requests), 1)

    def test_network_error_redacts_token(self):
        fake = FakeSession()
        def failed(*args, **kwargs):
            raise OSError("failed " + self.creds["token"])
        fake.get = failed
        with self.assertRaises(engine.ApiError) as cm:
            engine.create_form(self.config, self.creds, session=fake)
        self.assertNotIn(self.creds["token"], str(cm.exception))

    def test_malformed_question_response_preserves_draft_url(self):
        fake = FakeSession(); original = fake.post
        def malformed(url, **kwargs):
            if url.endswith("/questions"):
                return FakeResponse([])
            return original(url, **kwargs)
        fake.post = malformed
        with self.assertRaises(engine.ApiError) as cm:
            engine.create_form(self.config, self.creds, publish=True, session=fake)
        self.assertIn("Черновик:", str(cm.exception))
        self.assertFalse(fake.is_published)

    def test_long_forward_chain_does_not_recurse(self):
        config = {"form": {"name": "T"}, "questions": [{"type": "radio", "label": "T", "slug": f"q{i}", "options": ["A", "B"]} for i in range(1100)],
                  "conditions": [{"source": f"q{i}", "target": f"q{i+1}", "answers": ["A"]} for i in range(1099)]}
        engine.validate_config(config)


class EditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tkinter as tk
        try:
            root = tk.Tk(); root.destroy()
        except tk.TclError as exc:
            raise unittest.SkipTest(f"Display unavailable: {exc}")

    def setUp(self):
        import form_editor
        self.editor = form_editor
        self.settings_patch = patch.object(engine, "load_settings", return_value={})
        self.settings_patch.start()
        self.app = form_editor.App(); self.app.withdraw()

    def tearDown(self):
        self.app.destroy(); self.settings_patch.stop()

    def test_invalid_move_leaves_document_unchanged(self):
        self.app.config_data = synthetic_config(); self.app.refresh(0)
        original = deepcopy(self.app.config_data)
        # Move the source question after its dependent question.
        self.app.config_data["conditions"] = [{"source": "choice", "target": "multi", "answers": ["А"]}]
        original = deepcopy(self.app.config_data)
        with patch.object(self.editor.messagebox, "showerror") as error:
            self.app.move(1)
        self.assertEqual(self.app.config_data, original)
        self.assertFalse(self.app.dirty); error.assert_called_once()

    def test_question_rename_is_validated_and_relinked(self):
        self.app.config_data = synthetic_config(); self.app.refresh(0)
        question = deepcopy(self.app.config_data["questions"][0]); question["slug"] = "renamed"
        self.app.replace_question(0, question)
        engine.validate_config(self.app.config_data)
        self.assertEqual(self.app.config_data["conditions"][0]["source"], "renamed")

    def test_slug_allocation_reserves_other_field(self):
        self.app.config_data = {"form": {"name": "T"}, "questions": [{"type": "text", "label": "T", "slug": "q1_other"}]}
        self.assertEqual(self.app.next_slug(), "q2")

    def test_save_empty_draft_and_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "draft.json"
            with patch.object(engine, "save_settings"):
                self.assertTrue(self.app._write(path))
                self.app.open_path(path)
            self.assertEqual(self.app.config_data["questions"], [])
            self.assertFalse(self.app.dirty)

    def test_unsaved_save_discard_cancel(self):
        self.app.dirty = True
        for answer, saved, expected in ((None, True, False), (False, False, True), (True, False, False), (True, True, True)):
            with self.subTest(answer=answer, saved=saved), patch.object(self.editor.messagebox, "askyesnocancel", return_value=answer), patch.object(self.app, "save", return_value=saved):
                self.assertEqual(self.app.unsaved(), expected)

    def test_question_dialog_russian_types_and_api_slug(self):
        import tkinter as tk
        with patch.object(tk.Toplevel, "wait_window"):
            dialog = self.editor.QuestionDialog(self.app, {"type": "api", "label": "API", "slug": "old", "payload": {"type": "string", "slug": "old"}})
        try:
            self.assertEqual(dialog.v_type.get(), self.editor.LABELS["api"])
            dialog.v_slug.set("new")
            self.assertEqual(dialog.collect()["payload"]["slug"], "new")
        finally:
            dialog.destroy()

    def test_condition_builder_adds_rule(self):
        import tkinter as tk
        from dialogs import ConditionsDialog
        with patch.object(tk.Toplevel, "wait_window"):
            dialog = ConditionsDialog(self.app, synthetic_config())
        dialog.target.set(dialog.names["commentary"]); dialog.update_sources()
        dialog.source.set(dialog.names["choice"]); dialog.update_answers(); dialog.answers.selection_set(1)
        dialog.add(); dialog.save()
        self.assertEqual(dialog.result[-1], {"target": "commentary", "source": "choice", "answers": ["Б"], "operator": "or", "condition": "eq"})


if __name__ == "__main__":
    unittest.main()
