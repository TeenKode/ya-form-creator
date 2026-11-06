import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,readdirSync} from 'node:fs';
const dir='browser-build/opera-submission/extension/';
test('store package has readable local code, minimal permissions and a separate store signing identity',()=>{
  const store=JSON.parse(readFileSync(dir+'manifest.json','utf8'));
  const dev=JSON.parse(readFileSync('extension/manifest.json','utf8'));
  assert.equal(store.key,undefined);assert.ok(dev.key);
  assert.equal(store.version,dev.version);assert.deepEqual(store.permissions,dev.permissions);
  assert.deepEqual(store.host_permissions,dev.host_permissions);
  assert.equal(store.homepage_url,'https://teenkode.github.io/ya-form-creator/');
  assert.ok(readFileSync(dir+'core.mjs','utf8').split('\n').length>500);
  for(const file of readdirSync(dir)){
    assert.ok(!/token|credential|survey|user_settings/.test(file));
    if(file.endsWith('.html'))assert.ok(!/<script[^>]+src=["']https?:/i.test(readFileSync(dir+file,'utf8')));
  }
  assert.ok(readFileSync('web/privacy.html','utf8').includes('English summary'));
});
