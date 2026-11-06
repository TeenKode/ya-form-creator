import {test} from 'node:test';
import assert from 'node:assert/strict';
import {listOrganizations} from '../../browser-build/extension/organizations.mjs';
const oauth={token:'synthetic-token',auth_scheme:'OAuth',org_header:'X-Org-Id',org_id:''};
test('360 organization discovery needs no ID, paginates and omits contacts',async()=>{
  const calls=[];const items=await listOrganizations(oauth,'X-Org-Id',{fetcher:async(url,options)=>{calls.push({url,options});return Response.json(calls.length===1?{organizations:[{id:123,name:'Первое имя',email:'private@example.test'}],nextPageToken:'next/+&'}:{organizations:[{id:123,name:'Новое имя'},{id:456,name:'Вторая'}]});}});
  assert.deepEqual(items,[{id:'123',name:'Новое имя',org_header:'X-Org-Id'},{id:'456',name:'Вторая',org_header:'X-Org-Id'}]);
  assert.equal(new URL(calls[1].url).searchParams.get('pageToken'),'next/+&');assert.equal(calls[0].options.headers.Authorization,'OAuth synthetic-token');
  assert.equal(calls[0].options.redirect,'error');assert.equal(calls[0].options.credentials,'omit');assert.ok(!JSON.stringify(items).includes('private'));
});
test('Cloud accepts an IAM token and uses display title',async()=>{
  const items=await listOrganizations({...oauth,auth_scheme:'Bearer',org_header:'X-Cloud-Org-Id'},'X-Cloud-Org-Id',{fetcher:async(url,options)=>{assert.equal(new URL(url).hostname,'organization-manager.api.cloud.yandex.net');assert.equal(options.headers.Authorization,'Bearer synthetic-token');return Response.json({organizations:[{id:'bpfsynthetic123',name:'internal-name',title:'Моя организация'}]});}});
  assert.deepEqual(items,[{id:'bpfsynthetic123',name:'Моя организация',org_header:'X-Cloud-Org-Id'}]);
  await assert.rejects(listOrganizations(oauth,'X-Cloud-Org-Id'),/IAM/);
});
test('missing permission and network errors are sanitized',async()=>{
  await assert.rejects(listOrganizations(oauth,'X-Org-Id',{fetcher:async()=>new Response('private token data',{status:403})}),e=>e.message.includes('вручную')&&!e.message.includes('private'));
  await assert.rejects(listOrganizations(oauth,'X-Org-Id',{fetcher:async()=>{throw new Error(oauth.token);}}),e=>!e.message.includes(oauth.token));
});
test('reject malformed responses, unsafe numeric IDs and pagination loops',async()=>{
  for(const body of [{}, {organizations:[{id:9007199254740992}]}, {organizations:[{id:'bad id'}]}])await assert.rejects(listOrganizations(oauth,'X-Org-Id',{fetcher:async()=>Response.json(body)}));
  let calls=0;await assert.rejects(listOrganizations(oauth,'X-Org-Id',{fetcher:async()=>{calls++;return Response.json({organizations:[],nextPageToken:'same'});}}));assert.equal(calls,2);
});
