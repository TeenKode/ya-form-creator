"""Offline tests for explainable cross-question logic suggestions.

Synthetic questions are assembled in memory: no ready questionnaires shipped.
"""
from __future__ import annotations

from copy import deepcopy
import unittest

import engine
import logic_analyzer as logic


def make_form():
    return {
        "form": {"name": "Синтетическая проверка"},
        "questions": [
            {"type": "radio", "slug": "usage", "label": "Как часто используете ИИ?",
             "options": ["Ежедневно", "Редко", "Не использую"], "required": True},
            {"type": "checkbox", "slug": "tools", "label": "Какие инструменты ИИ используете?",
             "options": ["Сервис А", "Сервис Б", "Не использую"], "required": True},
            {"type": "checkbox", "slug": "tasks", "label": "Для каких задач используете ИИ?",
             "options": ["Подготовка", "Обработка", "Нет необходимости"]},
            {"type": "radio", "slug": "benefit", "label": "Как оцениваете пользу ИИ?",
             "options": ["Высокая", "Средняя", "Нет пользы"]},
            {"type": "checkbox", "slug": "barriers", "label": "Что мешает вам активнее использовать ИИ?",
             "options": ["Время", "Доступ", "Ничего не мешает"]},
            {"type": "radio", "slug": "training", "label": "Хотели бы пройти обучение по ИИ?",
             "options": ["Да", "Нет"]},
        ],
    }


class LogicAnalyzerTests(unittest.TestCase):
    def test_ai_followup_flags_three_but_not_obstacles_or_training(self):
        issues = logic.analyze_logic(make_form())
        targets = {issue["target"] for issue in issues}
        self.assertEqual(targets, {"tools", "tasks", "benefit"})
        self.assertTrue(all(issue["source"] == "usage" for issue in issues))
        self.assertTrue(all(issue["suggestion"]["answers"] == ["Не использую"] for issue in issues))

    def test_one_click_fixes_all_and_preserves_other(self):
        source = make_form()
        untouched = deepcopy(source)
        fixed = logic.apply_suggestions(source, logic.analyze_logic(source))
        self.assertEqual(source, untouched)
        self.assertEqual(len(fixed["conditions"]), 3)
        self.assertEqual(logic.analyze_logic(fixed), [])
        self.assertEqual(logic.apply_suggestions(fixed, []), fixed)
        engine.expand_questions(fixed)

    def test_fix_single_selected_target(self):
        cfg = make_form()
        fixed = logic.apply_suggestions(cfg, logic.analyze_logic(cfg), {"tools"})
        self.assertEqual(len(fixed["conditions"]), 1)
        self.assertEqual(fixed["conditions"][0]["target"], "tools")
        self.assertEqual({issue["target"] for issue in logic.analyze_logic(fixed)}, {"tasks", "benefit"})

    def test_existing_valid_rule_no_duplicate(self):
        cfg = make_form()
        cfg["conditions"] = [{"target": "tools", "source": "usage",
                              "answers": ["Не использую"], "condition": "neq"}]
        self.assertNotIn("tools", {issue["target"] for issue in logic.analyze_logic(cfg)})

    def test_wrong_existing_rule_warns_without_auto_changes(self):
        cfg = make_form()
        cfg["conditions"] = [{"target": "tools", "source": "usage",
                              "answers": ["Не использую"], "condition": "eq"}]
        issue = next(i for i in logic.analyze_logic(cfg) if i["target"] == "tools")
        self.assertEqual(issue["kind"], "conflicting_condition")
        self.assertIsNone(issue["suggestion"])
        fixed = logic.apply_suggestions(cfg, [issue], {"tools"})
        self.assertEqual(fixed["conditions"], cfg["conditions"])

    def test_other_existing_dependency_warns_without_override(self):
        cfg = make_form()
        cfg["conditions"] = [{"target": "tools", "source": "usage",
                              "answers": ["Ежедневно"], "condition": "eq"}]
        self.assertFalse(any(i["target"] == "tools" for i in logic.analyze_logic(cfg)))
        cfg["questions"].insert(1, {"type": "radio", "label": "Согласие", "slug": "consent",
                                     "options": ["Да", "Нет"]})
        cfg["conditions"] = [{"target": "tools", "source": "consent", "answers": ["Да"]}]
        issue = next(i for i in logic.analyze_logic(cfg) if i["target"] == "tools")
        self.assertEqual(issue["kind"], "complex_condition")
        self.assertIsNone(issue["suggestion"])

    def test_yes_no_gate(self):
        cfg = {"form": {"name": "Проверка"}, "questions": [
            {"type": "radio", "slug": "gate", "label": "Пользуетесь ли вы приложением?",
             "options": ["Да", "Нет"]},
            {"type": "text", "slug": "features",
             "label": "Какие функции приложения понравились?"}
        ]}
        issues = logic.analyze_logic(cfg)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["suggestion"]["answers"], ["Нет"])

    def test_negative_not_gate_when_unrelated(self):
        cfg = {"form": {"name": "Проверка"}, "questions": [
            {"type": "radio", "slug": "weather", "label": "Как часто видите снег?",
             "options": ["Часто", "Никогда"]},
            {"type": "text", "slug": "tools",
             "label": "Какие инструменты ИИ используете?"}
        ]}
        self.assertEqual(logic.analyze_logic(cfg), [])

    def test_skip_opt_in_questions_even_with_matching_topic(self):
        cfg = make_form()
        cfg["questions"] = [cfg["questions"][0],
            {"type": "radio", "slug": "interest",
             "label": "Планируете ли использовать ИИ?",
             "options": ["Да", "Нет"]},
            {"type": "text", "slug": "obstacles",
             "label": "Почему не используете ИИ?"}]
        self.assertEqual(logic.analyze_logic(cfg), [])

    def test_ignore_hidden_fields_and_remain_silent_for_empty(self):
        cfg = make_form()
        cfg["questions"][1]["hidden"] = True
        cfg["questions"][1]["required"] = False
        issues = logic.analyze_logic(cfg)
        self.assertFalse(any(i["target"] == "tools" for i in issues))
        self.assertEqual(logic.analyze_logic(
            {"form": {"name": "Пусто"}, "questions": []}), [])

    def test_multiple_negative_alternatives(self):
        cfg = make_form()
        cfg["questions"][0]["options"].append("Никогда")
        issues = logic.analyze_logic(cfg)
        for issue in issues:
            self.assertEqual(issue["suggestion"]["answers"], ["Не использую", "Никогда"])
        resolved = logic.apply_suggestions(cfg, issues)
        engine.expand_questions(resolved)

    def test_does_not_replace_user_rules_or_mutate_unrelated_data(self):
        cfg = make_form()
        cfg["questions"][0]["comment"] = "Сохраняйте анонимность"
        old = deepcopy(cfg)
        issues = logic.analyze_logic(cfg)
        result = logic.apply_suggestions(cfg, issues)
        self.assertEqual(cfg, old)
        self.assertEqual(result["questions"][0]["comment"], old["questions"][0]["comment"])
        self.assertEqual(len(result["questions"]), len(old["questions"]))

    def test_ui_import_without_network_or_cloud_ai(self):
        import logic_dialog
        self.assertTrue(hasattr(logic_dialog, "LogicReviewDialog"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
