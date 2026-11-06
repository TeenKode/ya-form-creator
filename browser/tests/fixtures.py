"""Synthetic contract cases; no user questionnaire or credentials."""
import copy
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import engine
from test_offline import synthetic_config

cases = [synthetic_config()]
cases.append({'form': {'name': 'Formats'}, 'questions': [
    {'type': 'text', 'label': fmt, 'slug': 'q' + str(i), 'format': fmt,
     'multiline': False, 'required': True, 'min_length': 1, 'max_length': 100}
    for i, fmt in enumerate(('plain', 'full_name', 'phone', 'email', 'url', 'inn', 'decimal'))]})
cases.append({'form': {'name': 'Exclusive'}, 'questions': [
    {'type': 'checkbox', 'slug': 'multi', 'label': 'Synthetic', 'required': True,
     'options': ['A', 'B', 'Нет необходимости', 'Другое'],
     'other': {'option': 'Другое'}},
    {'type': 'text', 'slug': 'follow', 'label': 'Follow'}],
    'conditions': [{'source': 'multi', 'target': 'follow', 'answers': ['Нет необходимости']}]})
cases.append({'form': {'name': 'Advanced', 'need_auth': True, 'allow_multiple_answers': False,
                       'submit_text': 'Finish', 'success_title': 'Done', 'success_subtitle': 'Thanks'},
              'questions': [
    {'type': 'dropdown', 'label': 'Quiz', 'slug': 'quiz', 'has_quiz': True,
     'options': [{'label': 'A', 'correct': True, 'score': 2}, {'label': 'B', 'correct': False}]},
    {'type': 'integer', 'slug': 'num', 'label': 'Count', 'min': -5, 'max': 10, 'initial': 0},
    {'type': 'date', 'slug': 'day', 'label': 'Date', 'min': '2024-01-01', 'max': '2030-12-31'},
    {'type': 'boolean', 'slug': 'flag', 'label': 'Flag', 'initial': False},
    {'type': 'api', 'slug': 'advanced', 'label': 'Advanced', 'required': True,
     'payload': {'type': 'string', 'validators': [{'type': 'email'}]}}]})
for kind in ('scale', 'stars', 'onerow', 'radio', 'checkbox', 'dropdown'):
    cases.append({'form': {'name': kind}, 'questions': [
        {'type': kind, 'slug': 'choice', 'label': kind, 'options': ['A', 'B'], 'required': True}]})
for case in cases:
    engine.validate_config(case)
json.dump([{'config': c, 'plan': engine.dry_run(copy.deepcopy(c))} for c in cases], sys.stdout, ensure_ascii=False)
