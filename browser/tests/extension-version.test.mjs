import {test} from 'node:test';
import assert from 'node:assert/strict';
import {assessExtension,MIN_EXTENSION_VERSION} from '../../web/extension-version.mjs';

test('compatible versions use numeric components and accept the minimum',()=>{
  assert.equal(assessExtension(MIN_EXTENSION_VERSION).compatible,true);
  for(const version of ['1.5','1.5.0.1','1.5.1','1.5.10','1.10.0','1.65535.0'])assert.equal(assessExtension(version).state,'ready',version);
});
test('old versions are blocked',()=>{
  for(const version of ['0.9.0','1','1.3.0','1.4.99','1.4.999.999'])assert.equal(assessExtension(version).state,'outdated',version);
});
test('future major versions require a newer site rather than a downgrade',()=>assert.deepEqual(assessExtension('2.0.0'),{state:'site-outdated',compatible:false,version:'2.0.0'}));
test('missing or malformed versions fail closed',()=>{
  for(const version of [undefined,null,{},[],1.5,'','v1.5.0','1.5.0-beta','1.05.0',' 1.5.0','1.65536.0','1.5.0.0.1','<img src=x>'])assert.deepEqual(assessExtension(version),{state:'unknown',compatible:false});
});
