import {redirectURL,launchAuthFlow} from './oauth.mjs';
import {dryRun,VERSION} from './core.mjs';
import {callApi,createForm,validateAuth,validateCredentials} from './api.mjs';
const SITE='https://teenkode.github.io/ya-form-creator/';
const DEFAULT_CLIENT_ID='a7f96f176b4241449864e48e3c3c6966';
const epoch=crypto.randomUUID();let running=false,authQueue=Promise.resolve();
function authMutation(fn){const task=authQueue.then(fn);authQueue=task.catch(()=>{});return task;}
const harden=()=>Promise.all([chrome.storage.local.setAccessLevel({accessLevel:'TRUSTED_CONTEXTS'}),chrome.storage.session.setAccessLevel({accessLevel:'TRUSTED_CONTEXTS'})]);
const ready=harden();
export function trustedSite(url){try{const u=new URL(url);return u.origin==='https://teenkode.github.io'&&u.pathname.startsWith('/ya-form-creator/');}catch{return false;}}
function internal(sender){try{return sender.id===chrome.runtime.id&&sender.url?.startsWith(chrome.runtime.getURL(''))&&['/options.html','/review.html'].includes(new URL(sender.url).pathname);}catch{return false;}}
async function credentials(){await ready;const s=await chrome.storage.session.get('credentials');return s.credentials??(await chrome.storage.local.get('credentials')).credentials;}
async function saveCredentials(data,remember){validateAuth(data);if(data.org_id)validateCredentials(data);await ready;await chrome.storage.session.remove('organizationCandidates');await chrome.storage.session.set({credentials:data});if(remember)await chrome.storage.local.set({credentials:data});else await chrome.storage.local.remove('credentials');}
async function authStamp(c){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(c.auth_scheme+'\n'+c.token+'\n'+(c.auth_session??'')))),v=>v.toString(16).padStart(2,'0')).join('');}
async function connectionStamp(c){return authStamp({...c,token:c.token+'\n'+c.org_header+'\n'+c.org_id});}
async function currentAuthAttempt(id){if((await chrome.storage.session.get('authAttempt')).authAttempt!==id)throw new Error('Этот вход отменён. При необходимости начните вход заново.');}
const organizationId=value=>typeof value==='string'&&/^bpf[a-z0-9]{17}$/.test(value);
const providerURL=value=>{try{const u=new URL(value);return u.protocol==='https:'&&['center.yandex.cloud','org.yandex.cloud'].includes(u.hostname)&&!u.port&&!u.username&&!u.password;}catch{return false;}};
async function activeAuth(){const c=await credentials();validateAuth(c);if(c.auth_scheme!=='OAuth'||c.org_header!=='X-Cloud-Org-Id')throw new Error('Войдите через Яндекс заново, чтобы подключить Identity Hub.');return c;}
async function connectOrganization(c,id,remember){
  if(!organizationId(id))throw new Error('Скопируйте ID организации под её названием в Cloud Center. Он начинается с bpf и содержит 20 символов.');
  const next={...c,org_id:id,org_name:'',org_header:'X-Cloud-Org-Id'};
  await callApi('/users/me','GET',next);
  return authMutation(async()=>{const current=await activeAuth();if(await authStamp(current)!==await authStamp(c))throw new Error('Аккаунт изменился. Повторите подключение.');
    await saveCredentials(next,remember);await chrome.storage.session.remove('organizationSetup');return{connected:true,id};});
}
async function readJob(id){if(typeof id!=='string'||!/^[a-f0-9-]{36}$/.test(id))throw new Error('Неизвестная операция.');return(await chrome.storage.session.get('job:'+id))['job:'+id];}
async function putJob(job){await chrome.storage.session.set({['job:'+job.id]:job});}
function safeStatus(job){return {id:job.id,status:job.status,phase:job.phase,done:job.done,total:job.total,error:job.error,result:job.result};}
async function dispatch(message,sender){
  await ready;
  const site=sender.id===chrome.runtime.id&&sender.tab?.id!==undefined&&sender.frameId===0&&trustedSite(sender.url);
  const own=internal(sender);
  if(!site&&!own)throw new Error('Этот источник не подключён к расширению.');
  if(!message||typeof message.type!=='string')throw new Error('Неверное сообщение.');
  if(message.type==='ping')return{version:VERSION};
  if(message.type==='options'){await chrome.runtime.openOptionsPage();return{opened:true};}
  if(message.type==='prepare'){
    if(!site)throw new Error('Откройте анкету на сайте.');
    const raw=JSON.stringify(message.config);if(new TextEncoder().encode(raw).length>750000)throw new Error('Файл слишком большой: максимум 750 КБ JSON.');
    const plan=dryRun(message.config);if(plan.questions.length>200)throw new Error('Слишком много элементов после развёртки.');
    const existing=await chrome.storage.session.get(null),jobs=Object.entries(existing).filter(([key])=>key.startsWith('job:'));
    const expired=jobs.filter(([,job])=>Date.now()-job.created_at>86400000).map(([key])=>key);if(expired.length)await chrome.storage.session.remove(expired);
    if(jobs.length-expired.length>=20)throw new Error('Открыто много операций. Перезапустите браузер после их завершения.');
    const job={id:crypto.randomUUID(),config:message.config,tabId:sender.tab.id,origin:SITE,status:'pending',created_at:Date.now()};await putJob(job);
    try{await chrome.tabs.create({url:chrome.runtime.getURL('review.html?job='+job.id)});}catch{await chrome.storage.session.remove('job:'+job.id);throw new Error('Не удалось открыть подтверждение.');}
    return{id:job.id,status:'pending'};
  }
  if(message.type==='status'){
    const job=await readJob(message.id);if(!job||(site&&job.tabId!==sender.tab.id))throw new Error('Операция недоступна этой вкладке.');
    if(job.status==='running'&&job.epoch!==epoch){job.status='interrupted';job.error='Фоновый процесс был перезапущен. Проверьте черновик перед новой попыткой.';await putJob(job);}
    return {...safeStatus(job),...(own?{organization_id:job.organization_id}:{})};
  }
  if(!own)throw new Error('Действие доступно только в окне расширения.');
  if(message.type==='settings'){
    let c;try{c=await activeAuth();}catch{}const local=await chrome.storage.local.get(['credentials','clientId']);
    const setup=(await chrome.storage.session.get('organizationSetup')).organizationSetup;
    return {signedIn:!!c,configured:!!c?.org_id,connection_id:c?.org_id?await connectionStamp(c):null,org_id:c?.org_id??'',org_name:'',remember:!!c&&!!local.credentials,setupPending:!!c&&!!setup&&Date.now()-setup.created_at<3600000,clientId:local.clientId??DEFAULT_CLIENT_ID,redirect:redirectURL(chrome.identity,chrome.runtime.id)};
  }
  if(message.type==='organization-open'){
    const c=await activeAuth();const tab=await chrome.tabs.create({url:'https://center.yandex.cloud/'});
    await chrome.storage.session.set({organizationSetup:{tabId:tab.id,stamp:await authStamp(c),created_at:Date.now()}});return{opened:true};
  }
  if(message.type==='organization-read'){
    const c=await activeAuth(),setup=(await chrome.storage.session.get('organizationSetup')).organizationSetup;
    if(!setup||Date.now()-setup.created_at>3600000||setup.stamp!==await authStamp(c))throw new Error('Нажмите «Открыть Identity Hub» и выберите организацию заново.');
    let tab;try{tab=await chrome.tabs.get(setup.tabId);}catch{throw new Error('Вкладка Яндекса закрыта. Откройте Identity Hub заново.');}
    if(!providerURL(tab.url))throw new Error('Завершите вход и откройте главную страницу организации в Cloud Center.');
    let result;try{result=await chrome.tabs.sendMessage(setup.tabId,{type:'read-identity-organization'},{frameId:0});}catch{throw new Error('Обновите вкладку Cloud Center или вставьте ID организации ниже.');}
    if(!organizationId(result?.id))throw new Error('Не удалось однозначно определить организацию. Откройте её главную страницу или скопируйте ID под названием и вставьте ниже.');
    // Page contents are only a candidate; the next step verifies access against Forms.
    return{id:result.id};
  }
  if(message.type==='organization-connect')return connectOrganization(await activeAuth(),message.id?.trim(),!!message.remember);
  if(message.type==='forget')return authMutation(async()=>{await chrome.storage.local.remove('credentials');await chrome.storage.session.remove(['credentials','organizationCandidates','organizationSetup','authAttempt']);return{forgotten:true};});
  if(message.type==='access'){await callApi('/users/me','GET',await activeAuth());return{connected:true};}
  if(message.type==='job'){
    const job=await readJob(message.id);if(!job)throw new Error('Операция не найдена.');return{...safeStatus(job),config:job.config,created_at:job.created_at,organization_id:job.organization_id};
  }
  if(message.type==='create'){
    const job=await readJob(message.id);if(!job||job.status!=='pending'||Date.now()-job.created_at>1800000)throw new Error('Подтверждение истекло или операция уже запускалась. Отправьте анкету с сайта заново.');
    if(message.confirm!==true)throw new Error('Подтвердите создание новой формы.');if(running)throw new Error('Другая форма ещё создаётся. Дождитесь завершения.');
    running=true;
    try{const c=await activeAuth();validateCredentials(c);if(message.connection_id!==await connectionStamp(c))throw new Error('Подключение изменилось. Сверьте организацию и подтвердите создание заново.');job.organization_id=c.org_id;job.status='running';job.epoch=epoch;await putJob(job);
      const result=await createForm(job.config,c,{publish:message.publish===true,progress:async update=>{Object.assign(job,update);await putJob(job);}});
      job.status='success';job.result=result;await putJob(job);return {...safeStatus(job),organization_id:job.organization_id};
    }catch(error){if(job.status==='pending')throw error;job.status='error';job.error=error.message;if(error.result)job.result=error.result;await putJob(job);return {...safeStatus(job),organization_id:job.organization_id};}finally{running=false;}
  }
  if(message.type==='oauth'){
    const clientId=message.clientId?.trim();if(!/^[a-f0-9]{32}$/i.test(clientId??''))throw new Error('Укажите ClientID OAuth-приложения (32 символа).');
    const attempt=crypto.randomUUID();await authMutation(()=>chrome.storage.session.set({authAttempt:attempt}));
    const redirect=redirectURL(chrome.identity,chrome.runtime.id),state=crypto.randomUUID();
    const verifier=Array.from(crypto.getRandomValues(new Uint8Array(32)),v=>v.toString(16).padStart(2,'0')).join('');
    const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(verifier));const challenge=btoa(String.fromCharCode(...new Uint8Array(hash))).replaceAll('+','-').replaceAll('/','_').replaceAll('=','');
    const scope='forms:read forms:write';
    const u=new URL('https://oauth.yandex.ru/authorize');u.search=new URLSearchParams({response_type:'code',client_id:clientId,redirect_uri:redirect,scope,state,force_confirm:'yes',code_challenge:challenge,code_challenge_method:'S256'});
    let callback;try{callback=await launchAuthFlow(chrome.identity,chrome.runtime,{url:u.href,interactive:true});}catch{throw new Error('Вход отменён или Redirect URI не зарегистрирован для этого расширения.');}
    await currentAuthAttempt(attempt);const returned=new URL(callback);if(returned.origin!==new URL(redirect).origin||returned.pathname!==new URL(redirect).pathname||returned.searchParams.get('state')!==state||!returned.searchParams.get('code'))throw new Error('Ответ авторизации не прошёл проверку.');
    let response;try{response=await fetch('https://oauth.yandex.ru/token',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({grant_type:'authorization_code',code:returned.searchParams.get('code'),client_id:clientId,code_verifier:verifier}),credentials:'omit',redirect:'error',signal:AbortSignal.timeout(20000)});}catch{throw new Error('Не удалось завершить обмен кода авторизации.');}
    if(!response.ok)throw new Error('Яндекс не выдал токен. Проверьте ClientID, разрешения и Redirect URI.');
    let token;try{token=await response.json();}catch{throw new Error('Яндекс вернул некорректный ответ авторизации.');}if(typeof token?.access_token!=='string')throw new Error('Ответ авторизации не содержит токена.');
    return authMutation(async()=>{await currentAuthAttempt(attempt);await saveCredentials({auth_session:crypto.randomUUID(),token:token.access_token,org_id:'',org_header:'X-Cloud-Org-Id',auth_scheme:'OAuth',...(token.expires_in?{expires_at:Date.now()+token.expires_in*1000}:{})},!!message.remember);
      await chrome.storage.session.remove('organizationSetup');await chrome.storage.local.set({clientId});return{connected:true};});
  }
  throw new Error('Неизвестное действие.');
}
chrome.runtime.onMessage.addListener((message,sender,reply)=>{dispatch(message,sender).then(data=>reply({ok:true,data})).catch(error=>reply({ok:false,error:error.message}));return true;});
chrome.action.onClicked.addListener(()=>chrome.tabs.create({url:SITE}));
chrome.runtime.onInstalled.addListener(()=>harden());
