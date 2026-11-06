import {test} from 'node:test';
import assert from 'node:assert/strict';
import {callApi,createForm,validateCredentials} from '../../browser-build/extension/api.mjs';
const credentials={auth_scheme:'OAuth',org_header:'X-Org-Id',org_id:'synthetic-org',token:'synthetic-test-token'};
const config={form:{name:'Synthetic',publish_by_default:true},questions:[{type:'radio',slug:'a',label:'A',options:['X','Y']},{type:'text',slug:'b',label:'B',format:'phone'}],conditions:[{source:'a',target:'b',answers:['Y']}]};
function mock(failAt){const calls=[];let id=10;return{calls,fetcher:async(url,options)=>{
  calls.push({url,...options});if(failAt&&url.includes(failAt))return new Response('private response must not leak',{status:422});
  if(options.method==='GET')return Response.json({results:[]});
  if(url.endsWith('/surveys'))return Response.json({id:'a'.repeat(24)});
  if(url.endsWith('/questions'))return Response.json({id:++id,slug:JSON.parse(options.body).slug,items:[{id:1,label:'X'},{id:2,label:'Y'}]});
  return Response.json({});
}};}
test('create draft in order, special validators and condition option IDs',async()=>{
  const m=mock(),progress=[];const r=await createForm(config,credentials,{...m,progress:async p=>progress.push(structuredClone(p))});
  assert.equal(r.published,false);assert.equal(r.question_count,2);assert.equal(r.conditions_count,1);
  assert.deepEqual(m.calls.map(x=>x.method),['GET','POST','POST','POST','POST']);
  assert.deepEqual(JSON.parse(m.calls[3].body).validators,[{type:'phone'}]);
  assert.equal(JSON.parse(m.calls[4].body).items[0].value,'2');
  assert.equal(m.calls[0].headers.Authorization,'OAuth synthetic-test-token');
  assert.equal(m.calls[0].redirect,'error');assert.equal(m.calls[0].credentials,'omit');
  assert.ok(progress.some(p=>p.result?.survey_id));
});
test('publish only when explicitly requested and after questions/conditions',async()=>{
  const m=mock();assert.equal((await createForm(config,credentials,{...m,publish:true})).published,true);assert.ok(m.calls.at(-1).url.endsWith('/publish'));
});
test('partial draft preserved, no retry, no publication after failure, no raw error',async()=>{
  const m=mock('/questions');await assert.rejects(createForm(config,credentials,{...m,publish:true}),e=>e.result.question_count===0&&!e.message.includes('private response'));
  assert.equal(m.calls.length,3);assert.ok(m.calls.every(x=>!x.url.endsWith('/publish')));
});
test('invalid credentials or config never contact API',async()=>{
  const m=mock();await assert.rejects(createForm(config,{...credentials,token:'bad\nheader'},m));
  await assert.rejects(createForm({form:{name:'Empty'},questions:[]},credentials,m));assert.equal(m.calls.length,0);
  assert.throws(()=>validateCredentials({...credentials,auth_scheme:'Bearer'}));
});
test('fixed endpoints and sanitized network errors',async()=>{
  const m=mock();await assert.rejects(callApi('https://evil.example','GET',credentials,undefined,m));assert.equal(m.calls.length,0);
  await assert.rejects(callApi('/users/me','GET',credentials,undefined,{fetcher:async()=>{throw new Error(credentials.token);}}),e=>!e.message.includes(credentials.token));
});
