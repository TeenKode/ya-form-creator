import {test,expect,chromium} from '@playwright/test';
import {mkdtemp,rm,readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
const SITE='https://teenkode.github.io/ya-form-creator/',ID='ojjljnbbienealjljlfklnfdpfemmlli';
test('site + actual extension: local preview, settings, explicit draft creation',async()=>{
  const profile=await mkdtemp(path.join(tmpdir(),'yaform-e2e-')),extension=path.resolve('browser-build/extension');
  const context=await chromium.launchPersistentContext(profile,{channel:'chromium',headless:true,ignoreDefaultArgs:['--disable-extensions'],args:[`--disable-extensions-except=${extension}`,`--load-extension=${extension}`]});
  try{
    await context.route(SITE+'**',async route=>{const name=new URL(route.request().url()).pathname.slice('/ya-form-creator/'.length)||'index.html';const types={html:'text/html',css:'text/css',mjs:'application/javascript',png:'image/png'};await route.fulfill({body:await readFile(path.join('web-dist',name)),contentType:types[name.split('.').at(-1)]??'application/octet-stream'});});
    let worker=context.serviceWorkers()[0]??await context.waitForEvent('serviceworker');expect(worker.url()).toContain(ID);
    // All API responses are synthetic; no real requests, accounts or forms.
    await worker.evaluate(()=>{globalThis.__requests=[];let count=0;globalThis.fetch=async(url,opts)=>{globalThis.__requests.push({url,method:opts.method,body:opts.body});if(opts.method==='GET')return Response.json({results:[]});if(url.endsWith('/surveys'))return Response.json({id:'a'.repeat(24)});if(url.endsWith('/questions'))return Response.json({id:++count});return Response.json({});};});
    const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(SITE);
    await expect(page.locator('#extensionState')).toHaveText('Расширение подключено');
    await page.locator('#emptyAdd').click();await page.locator('#qLabel').fill('Телефон');await page.locator('#qFormat').selectOption('phone');await page.locator('#qRequired').check();await page.locator('#questionForm button[type=submit]').click();
    await expect(page.locator('#questionCount')).toHaveText('1');await expect(page.locator('#empty')).toBeHidden();
    await page.getByRole('button',{name:'Проверить ответы',exact:true}).click();await expect(page.locator('#answerResult')).toContainText('обязателен');
    await page.getByRole('textbox',{name:'Телефон',exact:true}).fill('+7 999 123-45-67');await page.getByRole('button',{name:'Проверить ответы',exact:true}).click();await expect(page.locator('#answerResult')).toContainText('пройдена');
    await page.reload();await expect(page.locator('#questionCount')).toHaveText('1');await expect(page.getByRole('textbox',{name:'Телефон',exact:true})).toHaveValue('');
    const settings=await context.newPage();await settings.goto(`chrome-extension://${ID}/options.html`);await expect(settings.locator('#clientId')).toHaveValue('a7f96f176b4241449864e48e3c3c6966');await expect(settings.locator('#redirect')).toHaveValue(`https://${ID}.chromiumapp.org/oauth`);
    await settings.locator('#org_id').fill('synthetic-org');await settings.locator('#token').fill('synthetic-test-token');await settings.getByRole('button',{name:'Сохранить подключение'}).click();await expect(settings.locator('#token')).toHaveValue('');await expect(settings.locator('#status')).toContainText('сохранено');
    // The site cannot ask for credentials or trigger create directly.
    expect(await page.evaluate(()=>typeof chrome?.runtime?.sendMessage)).toBe('undefined');
    const reviewPromise=context.waitForEvent('page');await page.locator('#send').click();const review=await reviewPromise;await review.waitForLoadState();await expect(review.locator('#name')).toHaveText('Новая анкета');await expect(review.locator('#create')).toBeDisabled();
    expect(await worker.evaluate(()=>globalThis.__requests.length)).toBe(0);await review.locator('#confirm').check();await review.locator('#create').click();await expect(review.locator('#status')).toContainText('Черновик создан');
    const requests=await worker.evaluate(()=>globalThis.__requests);expect(requests).toHaveLength(3);expect(requests.every(r=>!r.url.endsWith('/publish'))).toBe(true);expect(JSON.parse(requests[2].body).validators).toEqual([{type:'required'},{type:'phone'}]);
    await page.setViewportSize({width:390,height:844});await page.screenshot({path:'test-results/mobile.png',fullPage:true});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    await page.setViewportSize({width:1440,height:1000});await page.screenshot({path:'test-results/desktop.png',fullPage:true});expect(errors).toEqual([]);
  }finally{await context.close();await rm(profile,{recursive:true,force:true});}
});

test('local editor: add, edit, delete, special fields, conditional preview, mobile layout',async()=>{
  const browser=await chromium.launch({headless:true,...(process.env.YAFORM_UI_CHANNEL?{channel:process.env.YAFORM_UI_CHANNEL}:{})});const context=await browser.newContext();
  try{await context.route(SITE+'**',async route=>{const name=new URL(route.request().url()).pathname.slice('/ya-form-creator/'.length)||'index.html';const types={html:'text/html',css:'text/css',mjs:'application/javascript',png:'image/png'};await route.fulfill({body:await readFile(path.join('web-dist',name)),contentType:types[name.split('.').at(-1)]??'application/octet-stream'});});
    const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(SITE);await expect(page.locator('#extensionState')).toHaveText('Нужно расширение');await page.locator('#emptyAdd').click();await page.locator('#qLabel').fill('ФИО');await page.locator('#qFormat').selectOption('full_name');await page.locator('#questionForm button[type=submit]').click();
    await page.getByRole('button',{name:'Изменить вопрос 1',exact:true}).click();await page.locator('#qLabel').fill('Как вас зовут?');await page.locator('#questionForm button[type=submit]').click();await expect(page.locator('#blocks')).toContainText('Как вас зовут?');
    page.once('dialog',dialog=>dialog.accept());await page.getByRole('button',{name:'Удалить вопрос 1',exact:true}).click();await expect(page.locator('#empty')).toBeVisible();
    const config={form:{name:'Контактная анкета'},questions:[{type:'radio',slug:'choice',label:'Как связаться?',options:['По телефону','По почте']},{type:'text',format:'phone',slug:'phone',label:'Телефон',required:true},{type:'text',format:'email',slug:'email',label:'Почта',required:true}],conditions:[{source:'choice',target:'phone',answers:['По телефону']},{source:'choice',target:'email',answers:['По почте']}]};
    await page.locator('#jsonDetails summary').click();await page.locator('#json').fill(JSON.stringify(config));await page.locator('#applyJson').click();await expect(page.getByRole('textbox',{name:'Телефон',exact:true})).toBeHidden();await page.getByLabel('По телефону',{exact:true}).check();await expect(page.getByRole('textbox',{name:'Телефон',exact:true})).toBeVisible();await page.getByRole('textbox',{name:'Телефон',exact:true}).fill('abc');await page.getByRole('button',{name:'Проверить ответы',exact:true}).click();await expect(page.locator('#answerResult')).toContainText('телефон РФ');await page.getByLabel('По почте',{exact:true}).check();await expect(page.getByRole('textbox',{name:'Телефон',exact:true})).toBeHidden();await expect(page.getByRole('textbox',{name:'Почта',exact:true})).toBeVisible();
    await page.getByRole('textbox',{name:'Почта',exact:true}).fill('example@example.org');await page.getByRole('button',{name:'Проверить ответы',exact:true}).click();await expect(page.locator('#answerResult')).toContainText('пройдена');
    await page.locator('#jsonDetails summary').click();await page.setViewportSize({width:1440,height:1000});await page.screenshot({path:'test-results/editor-desktop.png',fullPage:true});await page.setViewportSize({width:390,height:844});await page.screenshot({path:'test-results/editor-mobile.png',fullPage:true});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);expect(errors).toEqual([]);
  }finally{await context.close();await browser.close();}
});
