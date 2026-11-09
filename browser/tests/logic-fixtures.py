"""Synthetic parity cases for the browser logic analyzer; never shipped in builds."""
import json
import sys
from copy import deepcopy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from test_logic import make_form
from logic_analyzer import analyze_logic, apply_suggestions

cases = [make_form()]
for condition in ('eq', 'neq'):
    c = make_form()
    c['conditions'] = [{'target':'tools','source':'usage','answers':['Не использую'],'condition':condition}]
    cases.append(c)
c = make_form()
c['questions'].insert(1, {'type':'radio','slug':'consent','label':'Согласие','options':['Да','Нет']})
c['conditions'] = [{'target':'tools','source':'consent','answers':['Да']}]
cases.append(c)
c = make_form()
c['questions'][0]['options'].append('Никогда')
cases.append(c)
c = make_form()
c['questions'][1]['hidden'] = True
c['questions'][1]['required'] = False
c['questions'][1]['options'] = ['Сервис А','Сервис Б']
cases.append(c)
cases.append({'form':{'name':'Empty'},'questions':[]})
cases.append({'form':{'name':'App'},'questions':[
    {'type':'radio','slug':'usage','label':'Пользуетесь ли вы приложением?','options':['Да','Нет']},
    {'type':'text','slug':'features','label':'Какие функции приложения понравились?'}]})
c = make_form()
c['questions'].insert(1, {'type':'section','label':'Раздел'})
c['questions'][0]['label'] = '  КАК ЧАСТО используете ИИ?  '
c['questions'][0]['options'][-1] = 'НЕ ИСПОЛЬЗУЮ!'
cases.append(c)
print(json.dumps([{'config':c,'issues':analyze_logic(c),'applied':apply_suggestions(c, [])} for c in cases], ensure_ascii=False))
