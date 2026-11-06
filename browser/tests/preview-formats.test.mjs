import {test} from 'node:test';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {validInn} from '../../web/answer-validation.mjs';
import {dryRun} from '../core.mjs';
test('INN preview matches desktop checksums including mutated 10- and 12-digit values',()=>{
 const values=['1234567894','1234567890','123456789012','123456789047','0000000000','123','123456789a','１２３４５６７８９０'];
 const script='import json,sys; from field_formats import format_error; print(json.dumps([format_error("inn",s) is None for s in json.loads(sys.argv[1])]))';
 const expected=JSON.parse(execFileSync(process.env.PYTHON??'python',['-c',script,JSON.stringify(values)],{encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'}}));
 assert.deepEqual(values.map(validInn),expected);assert.equal(validInn('1234567890'),false);assert.equal(validInn('1234567894'),true);
});
test('required checkbox cannot impose max zero, optional zero remains representable',()=>{
 const config={form:{name:'Synthetic'},questions:[{type:'checkbox',slug:'q1',label:'Synthetic',options:['A','B'],required:true,max_choices:0}]};
 assert.throws(()=>dryRun(config));config.questions[0].required=false;assert.ok(dryRun(config).questions[0].validators.some(v=>v.type==='max'&&v.value===0));
});
