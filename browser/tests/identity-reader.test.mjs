import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const source=readFileSync('extension/identity-reader.js','utf8');
function read(text,{hostname='center.yandex.cloud',sender='self',type='read-identity-organization'}={}){let listener,result;vm.runInNewContext(source,{chrome:{runtime:{id:'self',onMessage:{addListener:fn=>listener=fn}}},location:{protocol:'https:',hostname},document:{body:{innerText:text}}});listener({type},{id:sender},v=>result=v);return result;}
test('cabinet reader returns only a single visible ID, never guesses among organizations',()=>{
  const id='bpf00000000000000001';assert.equal(read('Organization '+id).id,id);assert.equal(read(id+' '+id).id,id);
  for(const text of ['',id+' bpf00000000000000002','bpfshort','xx'+id,id+'x'])assert.equal(read(text).id,null);
});
test('cabinet reader ignores foreign senders, other hosts and unrelated commands',()=>{
  const id='bpf00000000000000001';for(const options of [{sender:'foreign'},{hostname:'evil.example'},{type:'settings'}])assert.equal(read(id,options),undefined);
});
