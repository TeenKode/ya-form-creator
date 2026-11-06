"""Regressions for mutually exclusive answers; no bundled customer forms."""
from __future__ import annotations

import copy
import unittest

import engine
import form_preview
from test_offline import FakeSession


def make_config():
    return {
        "form": {"name": "Синтетическая форма"},
        "questions": [
            {"type": "checkbox", "slug": "tools", "label": "Отметьте варианты",
             "required": True, "options": ["Первый", "Второй", "Не использую", "Другое"],
             "other": {"option": "Другое", "label": "Уточните"}},
            {"type": "text", "slug": "details", "label": "Пояснение"}
        ],
        "conditions": [{"target": "details", "source": "tools", "answers": ["Первый"]}]
    }


class ExclusivityTests(unittest.TestCase):
    def test_auto_detect_negative_and_uncertain(self):
        q = {"type": "checkbox", "options": ["Первый", "Не использую", "Затрудняюсь ответить", "Второй"]}
        self.assertEqual(engine.exclusive_options(q), ["Не использую", "Затрудняюсь ответить"])
        self.assertEqual(engine.exclusive_options({"type": "checkbox", "options": ["Плохо", "Ничего не мешает", "Нет необходимости", "Хорошо"]}),
                         ["Ничего не мешает", "Нет необходимости"])

    def test_gates_real_api_questions(self):
        config = make_config()
        effective = engine.resolve_exclusive_config(config)
        self.assertEqual([q["slug"] for q in effective["questions"]],
                         ["tools_choice", "tools", "details"])
        gate, choices = effective["questions"][:2]
        self.assertEqual(gate["type"], "radio")
        self.assertEqual(gate["options"], ["Выбрать варианты из списка", "Не использую"])
        self.assertEqual(choices["options"], ["Первый", "Второй", "Другое"])
        self.assertTrue(choices["required"])
        self.assertTrue(gate["required"])
        self.assertIn({"target": "tools", "source": "tools_choice",
                       "answers": ["Выбрать варианты из списка"]}, effective["conditions"])
        payloads, conds = engine.expand_questions(config)
        self.assertEqual(payloads[0]["widget"], "radio")
        self.assertEqual(payloads[1]["widget"], "checkbox")
        self.assertEqual(len(payloads), 4)  # gate, list, conditional other, details
        self.assertEqual(len(conds), 3)
        self.assertEqual(config, make_config())  # no in-place mutation

    def test_preview_visibility_matching_live_branch(self):
        cfg = engine.resolve_exclusive_config(make_config())
        self.assertNotIn("tools", form_preview.visible_slugs(cfg, {}))
        self.assertNotIn("tools", form_preview.visible_slugs(cfg, {"tools_choice": "Не использую"}))
        self.assertIn("tools", form_preview.visible_slugs(cfg, {"tools_choice": "Выбрать варианты из списка"}))
        self.assertIn("tools_other", form_preview.visible_slugs(cfg, {
            "tools_choice": "Выбрать варианты из списка", "tools": ["Другое"]}))
        self.assertNotIn("tools_other", form_preview.visible_slugs(cfg, {
            "tools_choice": "Не использую", "tools": ["Другое"]}))

    def test_preview_detects_legacy_contradiction(self):
        cfg = make_config()
        errors = form_preview.check_answers(cfg, {"tools": ["Первый", "Не использую"]})
        self.assertTrue(any("исключающий" in x for x in errors))
        self.assertFalse(any("исключающий" in x for x in form_preview.check_answers(
            cfg, {"tools": ["Первый", "Второй"]})))

    def test_explicit_exclusive_and_disable_default(self):
        cfg = make_config()
        cfg["questions"][0]["options"] = ["Первый", "Второй", "Ничего особенного"]
        cfg["questions"][0].pop("other", None)
        cfg["questions"][0]["exclusive_options"] = ["Ничего особенного"]
        self.assertEqual(engine.exclusive_options(cfg["questions"][0]), ["Ничего особенного"])
        engine.validate_config(cfg)
        cfg["questions"][0]["exclusive_options"] = []
        self.assertNotIn("tools_choice", [q.get("slug") for q in engine.resolve_exclusive_config(cfg)["questions"]])

    def test_exclusive_bad_references_are_rejected(self):
        cfg = make_config()
        cfg["questions"][0]["exclusive_options"] = ["Не существует"]
        with self.assertRaisesRegex(engine.ConfigError, "отсутствуют"):
            engine.validate_config(cfg)
        cfg = make_config()
        cfg["questions"][0]["exclusive_options"] = ["Первый", "Второй", "Не использую"]
        with self.assertRaisesRegex(engine.ConfigError, "минимум два"):
            engine.validate_config(cfg)

    def test_slug_collision(self):
        cfg = make_config()
        cfg["questions"].append({"type": "text", "slug": "tools_choice", "label": "Коллизия"})
        with self.assertRaisesRegex(engine.ConfigError, "уже занят"):
            engine.validate_config(cfg)

    def test_optional_gate_optional_without_selection(self):
        cfg = make_config()
        cfg["questions"][0]["required"] = False
        resolved = engine.resolve_exclusive_config(cfg)
        self.assertFalse(resolved["questions"][0]["required"])
        self.assertTrue(resolved["questions"][1]["required"])
        self.assertFalse(form_preview.check_answers(resolved, {}))
        errors = form_preview.check_answers(resolved, {"tools_choice": "Выбрать варианты из списка"})
        self.assertTrue(any("Уточните ответ" in x for x in errors))

    def test_incoming_and_outgoing_condition_mapping(self):
        cfg = make_config()
        cfg["questions"].insert(0, {"type": "radio", "slug": "start", "label": "Первый вопрос", "options": ["Да", "Нет"]})
        cfg["conditions"] = [
            {"target": "tools", "source": "start", "answers": ["Да"]},
            {"target": "details", "source": "tools", "answers": ["Не использую"]},
        ]
        resolved = engine.resolve_exclusive_config(cfg)
        self.assertIn({"target": "tools_choice", "source": "start", "answers": ["Да"]}, resolved["conditions"])
        self.assertIn({"target": "details", "source": "tools_choice", "answers": ["Не использую"]}, resolved["conditions"])
        self.assertIn("details", form_preview.visible_slugs(resolved, {
            "start": "Да", "tools_choice": "Не использую"}))
        self.assertNotIn("tools", form_preview.visible_slugs(resolved, {
            "start": "Да", "tools_choice": "Не использую"}))

    def test_ambiguous_mixed_condition_rejected_before_api(self):
        cfg = make_config()
        cfg["conditions"][0]["answers"] = ["Не использую", "Первый"]
        cfg["conditions"][0]["operator"] = "or"
        with self.assertRaisesRegex(engine.ConfigError, "смешивать"):
            engine.expand_questions(cfg)

    def test_api_posts_gate_and_conditions(self):
        cfg = make_config()
        creds = {"auth_scheme": "OAuth", "org_header": "X-Org-Id", "token": "test", "org_id": "123"}
        fake = FakeSession()
        response = engine.create_form(cfg, creds, session=fake, publish=True)
        self.assertTrue(response["published"])
        self.assertEqual(response["question_count"], 4)
        posts = [payload for op, u, payload in fake.requests if op == "POST" and u.endswith("/questions")]
        self.assertEqual(posts[0]["widget"], "radio")
        self.assertEqual(posts[1]["widget"], "checkbox")
        self.assertNotIn("Не использую", [opt["label"] for opt in posts[1]["items"]])
        self.assertEqual(response["conditions_count"], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
