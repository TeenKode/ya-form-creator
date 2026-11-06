import {test} from 'node:test';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {dryRun,validateConfig,resolveExclusive,visibleSlugs} from '../core.mjs';
const fixtures=JSON.parse(execFileSync(process.env.PYTHON??'python',['browser/tests/fixtures.py'],{encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'}}));
for(const {config,plan}of fixtures)test('Python/JS payload parity: '+config.form.name,()=>assert.deepEqual(dryRun(config),plan));
test('exclusive choice and Other visibility',()=>{
  const c=resolveExclusive(fixtures[2].config);
  assert.deepEqual([...visibleSlugs(c,{})],['multi_choice']);
  assert.deepEqual([...visibleSlugs(c,{multi_choice:'Нет необходимости'})],['multi_choice','follow']);
  assert.deepEqual([...visibleSlugs(c,{multi_choice:'Выбрать варианты из списка',multi:['Другое']})],['multi_choice','multi','multi_other']);
});
const invalid=[
  {type:'fio'}, {type:'phone'}, {type:'number'}, {type:'text',unique:true},
  {type:'text',pattern:'.*'}, {type:'text',format:'phone',multiline:true},
  {type:'integer',min:2,max:1}, {type:'date',min:'2025-02-29'},
  {type:'checkbox',options:['A','A']}, {type:'text',slug:'1bad'}
];
for(const delta of invalid)test('reject invalid contract '+JSON.stringify(delta),()=>assert.throws(()=>validateConfig({form:{name:'Test'},questions:[{type:'text',slug:'field',label:'Synthetic',...delta}]})));
test('reject forward dependency and duplicate service slugs',()=>{
  const c=structuredClone(fixtures[0].config);c.conditions=[{source:'choice',target:'choice',answers:['A']}];assert.throws(()=>dryRun(c));
  const d=structuredClone(fixtures[0].config);d.questions.push({type:'text',slug:'choice_other',label:'Collision'});assert.throws(()=>dryRun(d));
});
