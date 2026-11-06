"""Tests for the interactive preview, without any stored customer questionnaire."""
from __future__ import annotations

import os
import unittest
from copy import deepcopy

import form_preview
from test_offline import synthetic_config


def preview_config():
    cfg = synthetic_config()
    cfg['questions'].insert(2, {'type': 'section', 'label': 'Следующий раздел'})
    cfg['questions'].extend([
        {'type': 'dropdown', 'slug': 'dropdown', 'label': 'Список', 'options': ['Да', 'Нет']},
        {'type': 'scale', 'slug': 'scale', 'label': 'Шкала', 'options': ['1', '2', '3']},
        {'type': 'text', 'slug': 'short', 'label': 'Короткий текст', 'multiline': False,
         'min_length': 3, 'required': True},
    ])
    return cfg


class PreviewLogicTests(unittest.TestCase):
    def setUp(self):
        self.config = preview_config()

    def test_other_and_condition_use_selection(self):
        a = {'choice': 'Б'}
        self.assertIn('commentary', form_preview.visible_slugs(self.config, a))
        self.assertNotIn('choice_other', form_preview.visible_slugs(self.config, a))
        a['choice'] = 'Другое'
        visible = form_preview.visible_slugs(self.config, a)
        self.assertIn('choice_other', visible)
        self.assertNotIn('commentary', visible)
        a['choice'] = ''
        self.assertNotIn('choice_other', form_preview.visible_slugs(self.config, a))

    def test_checkbox_multi_answer_condition(self):
        cfg = deepcopy(self.config)
        cfg['conditions'].append({'target':'short', 'source':'multi', 'answers':['А', 'Б'], 'operator':'and'})
        self.assertNotIn('short', form_preview.visible_slugs(cfg, {'multi': ['А']}))
        self.assertIn('short', form_preview.visible_slugs(cfg, {'multi': ['А','Б']}))

    def test_hidden_source_cannot_satisfy_neq(self):
        cfg = deepcopy(self.config)
        cfg['conditions'] = [
            {'target': 'multi', 'source': 'choice', 'answers': ['А']},
            {'target': 'short', 'source': 'multi', 'answers': ['Б'], 'condition': 'neq'},
        ]
        self.assertNotIn('short', form_preview.visible_slugs(cfg, {'choice': 'Б', 'multi': ['А']}))
        self.assertIn('short', form_preview.visible_slugs(cfg, {'choice': 'А', 'multi': ['А']}))

    def test_ignored_hidden_required(self):
        cfg = deepcopy(self.config)
        q = next(q for q in cfg['questions'] if q.get('slug')=='commentary')
        q['required'] = True
        self.assertFalse(any('Комментарий' in e for e in form_preview.check_answers(cfg, {'choice':'А'})))
        self.assertTrue(any('Комментарий' in e for e in form_preview.check_answers(cfg, {'choice':'Б'})))

    def test_checkbox_limits(self):
        cfg = deepcopy(self.config)
        q = next(q for q in cfg['questions'] if q.get('slug')=='multi')
        q.update(min_choices=2, max_choices=2)
        self.assertTrue(any('не менее' in e for e in form_preview.check_answers(cfg, {'multi':['А']})))
        self.assertFalse(any('не менее' in e for e in form_preview.check_answers(cfg, {'multi':['А','Б']})))

    def test_other_required_only_when_selected(self):
        a = {'choice':'А'}
        self.assertFalse(any('Поясните' in e for e in form_preview.check_answers(self.config,a)))
        a['choice']='Другое'
        self.assertTrue(any('Поясните' in e for e in form_preview.check_answers(self.config,a)))
        a['choice_other']='Ответ'
        self.assertFalse(any('Поясните' in e for e in form_preview.check_answers(self.config,a)))

    def test_integer_date_and_text_validation(self):
        a = {'number':'x', 'date':'2024-22-07', 'short':'A'}
        errors = form_preview.check_answers(self.config,a)
        self.assertTrue(any('целое число' in e for e in errors))
        self.assertTrue(any('YYYY-MM-DD' in e for e in errors))
        self.assertTrue(any('короткий ответ' in e for e in errors))

    def test_option_labels_dict_and_string(self):
        self.assertEqual(form_preview.option_labels({'options': ['А', {'label':'Б','correct':True}]}), ['А','Б'])


class PreviewGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tkinter as tk
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
        except tk.TclError as exc:
            raise unittest.SkipTest(f'GUI unavailable: {exc}')

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'root'):
            cls.root.destroy()

    @staticmethod
    def descendants(widget):
        result = []
        for item in widget.winfo_children():
            result.append(item)
            result.extend(PreviewGuiTests.descendants(item))
        return result

    def test_radio_and_checkbox_render_native_controls(self):
        from tkinter import ttk
        win = form_preview.PreviewWindow(self.root, preview_config())
        self.root.update()
        radio_widgets = self.descendants(win.blocks['choice'])
        checkbox_widgets = self.descendants(win.blocks['multi'])
        self.assertEqual(len([w for w in radio_widgets if isinstance(w, ttk.Radiobutton)]), 3)
        self.assertEqual(len([w for w in radio_widgets if isinstance(w, ttk.Checkbutton)]), 0)
        self.assertEqual(len([w for w in checkbox_widgets if isinstance(w, ttk.Checkbutton)]), 2)
        self.assertEqual(len([w for w in checkbox_widgets if isinstance(w, ttk.Radiobutton)]), 0)
        win.destroy()

    def test_dynamic_other_and_reset(self):
        from tkinter import ttk
        win = form_preview.PreviewWindow(self.root, preview_config())
        self.root.update()
        self.assertFalse(win.blocks['choice_other'].winfo_ismapped())
        radio = next(w for w in self.descendants(win.blocks['choice']) if isinstance(w, ttk.Radiobutton)
                     and w.cget('text') == 'Другое')
        radio.invoke()
        self.root.update()
        self.assertTrue(win.blocks['choice_other'].winfo_ismapped())
        win.clear_answers()
        self.root.update()
        self.assertFalse(win.blocks['choice_other'].winfo_ismapped())
        self.assertEqual(win.collect_answers()['choice'], '')
        win.destroy()


if __name__ == '__main__':
    unittest.main(verbosity=2)