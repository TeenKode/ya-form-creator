import {test} from 'node:test';
import assert from 'node:assert/strict';
import {redirectURL,launchAuthFlow} from '../../extension/oauth.mjs';
const id='ojjljnbbienealjljlfklnfdpfemmlli';
test('redirect uses the browser helper or a fixed extension-specific Chromium origin',()=>{
  assert.equal(redirectURL({},id),`https://${id}.chromiumapp.org/oauth`);
  assert.equal(redirectURL({getRedirectURL:path=>'native:'+path},id),'native:oauth');
  assert.throws(()=>redirectURL({},'https://evil.example'));
});
test('OAuth supports callback-only Opera and Promise implementations',async()=>{
  const options={url:'https://oauth.yandex.ru/authorize',interactive:true};
  assert.equal(await launchAuthFlow({launchWebAuthFlow:(o,cb)=>{assert.equal(o,options);cb('callback');}}, {},options),'callback');
  assert.equal(await launchAuthFlow({launchWebAuthFlow:async()=>'promise'}, {},options),'promise');
  await assert.rejects(launchAuthFlow({launchWebAuthFlow:(o,cb)=>cb(undefined)},{lastError:{message:'private'}},options));
  await assert.rejects(launchAuthFlow({}, {},options));
});
