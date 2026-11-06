import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseConfigText} from '../../web/import-config.mjs';
import {dryRun} from '../core.mjs';
const short=readFileSync('AI_SHORT_RU.md','utf8');
test('short standalone handoff stays bounded and its only JSON example passes the engine',()=>{
  assert.ok(short.length<4200);
  const example=JSON.parse(short.match(/```json\n([\s\S]*?)\n```/)[1]);
  assert.equal(dryRun(example).questions.length,2);
  assert.equal(example.form.publish_by_default,false);
  for(const name of ['full_name','phone','email','url','inn','decimal'])assert.ok(short.includes(name));
  assert.ok(!short.includes('JSON Schema'));assert.ok(!short.includes('pip install'));
});
test('imports plain JSON, a BOM, and one fenced chat reply without changing form content',()=>{
  const c={form:{name:'Synthetic'},questions:[{type:'text',slug:'id',label:'Номер заказа',multiline:false}]};const raw=JSON.stringify(c);
  for(const value of [raw,'\uFEFF'+raw,'```json\n'+raw+'\n```','Вот файл:\n```JSON\n'+raw+'\n```\nГотово.','```\n'+raw+'\n```'])assert.deepEqual(parseConfigText(value),c);
});
test('refuses incomplete, ambiguous or executable-looking input and keeps semantic validation',()=>{
  for(const value of ['{"form":','```json\n{}\n```\n```json\n{}\n```','```javascript\n{}\n```','// comment\n{}','prefix {} suffix'])assert.throws(()=>parseConfigText(value));
  const c=parseConfigText('```json\n{"form":{"name":"X"},"questions":[{"type":"fio","slug":"q1","label":"Имя"}]}\n```');
  assert.throws(()=>dryRun(c));
});
