import {dryRun,VERSION} from './core.mjs';
import {callApi,createForm,validateAuth,validateCredentials} from './api.mjs';
import {listOrganizations} from './organizations.mjs';
const SITE='https://teenkode.github.io/ya-form-creator/';
const DEFAULT_CLIENT_ID='a7f96f176b4241449864e48e3c3c6966';
const epoch=crypto.randomUUID();let running=false;
const harden=()=>Promise.all([chrome.storage.local.setAccessLevel({accessLevel:'TRUSTED_CONTEXTS'}),chrome.storage.session.setAccessLevel({accessLevel:'TRUSTED_CONTEXTS'})]);
const ready=harden();
export function trustedSite(url){try{const u=new URL(url);return u.origin==='https://teenkode.github.io'&&u.pathname.startsWith('/ya-form-creator/');}catch{return false;}}
function internal(sender){try{return sender.id===chrome.runtime.id&&sender.url?.startsWith(chrome.runtime.getURL(''))&&['/options.html','/review.html'].includes(new URL(sender.url).pathname);}catch{return false;}}
async function credentials(){await ready;const s=await chrome.storage.session.get('credentials');return s.credentials??(await chrome.storage.local.get('credentials')).credentials;}
async function saveCredentials(data,remember,{keepCandidates=false}={}){validateAuth(data);if(data.org_id)validateCredentials(data);await ready;if(!keepCandidates)await chrome.storage.session.remove('organizationCandidates');await chrome.storage.session.set({credentials:data});if(remember)await chrome.storage.local.set({credentials:data});else await chrome.storage.local.remove('credentials');}
async function authStamp(c){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(c.auth_scheme+'\n'+c.token))),v=>v.toString(16).padStart(2,'0')).join('');}
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
    return safeStatus(job);
  }
  if(!own)throw new Error('Действие доступно только в окне расширения.');
  if(message.type==='settings'){
    const c=await credentials();const local=await chrome.storage.local.get(['credentials','clientId']);return {signedIn:!!c,configured:!!c?.org_id,org_id:c?.org_id??'',org_name:c?.org_name??'',org_header:c?.org_header??'X-Org-Id',auth_scheme:c?.auth_scheme??'OAuth',remember:!!local.credentials,clientId:local.clientId??DEFAULT_CLIENT_ID,redirect:chrome.identity.getRedirectURL('oauth')};
  }
  if(message.type==='save'){
    const old=await credentials(),c={auth_scheme:message.auth_scheme,org_header:message.org_header,org_id:message.org_id?.trim(),token:message.token?.trim()||old?.token,...(!message.token?.trim()&&old?.expires_at?{expires_at:old.expires_at}:{})};
    await saveCredentials(c,!!message.remember);return{saved:true};
  }
  if(message.type==='organizations'){
    const c=await credentials();validateAuth(c);await chrome.storage.session.remove('organizationCandidates');
    const items=await listOrganizations(c,message.org_header);const current=await credentials();if(!current||await authStamp(current)!==await authStamp(c))throw new Error('Аккаунт изменился. Повторите поиск.');
    await chrome.storage.session.set({organizationCandidates:{items,stamp:await authStamp(c),created_at:Date.now()}});return{items};
  }
  if(message.type==='select-org'){
    const c=await credentials();validateAuth(c);const cached=(await chrome.storage.session.get('organizationCandidates')).organizationCandidates;
    if(!cached||Date.now()-cached.created_at>600000||cached.stamp!==await authStamp(c))throw new Error('Повторите поиск организаций.');
    const item=cached.items.find(x=>x.id===message.id&&x.org_header===message.org_header);if(!item)throw new Error('Выберите организацию из списка.');
    const next={...c,org_id:item.id,org_name:item.name,org_header:item.org_header};await callApi('/users/me','GET',next);
    const current=await credentials();if(!current||await authStamp(current)!==await authStamp(c))throw new Error('Аккаунт изменился. Повторите вход.');
    await saveCredentials(next,!!message.remember,{keepCandidates:true});return{selected:true,name:item.name,id:item.id};
  }
  if(message.type==='forget'){await chrome.storage.local.remove('credentials');await chrome.storage.session.remove(['credentials','organizationCandidates']);return{forgotten:true};}
  if(message.type==='access'){await callApi('/users/me','GET',await credentials());return{connected:true};}
  if(message.type==='job'){
    const job=await readJob(message.id);if(!job)throw new Error('Операция не найдена.');return{...safeStatus(job),config:job.config,created_at:job.created_at};
  }
  if(message.type==='create'){
    const job=await readJob(message.id);if(!job||job.status!=='pending'||Date.now()-job.created_at>1800000)throw new Error('Подтверждение истекло или операция уже запускалась. Отправьте анкету с сайта заново.');
    if(message.confirm!==true)throw new Error('Подтвердите создание новой формы.');if(running)throw new Error('Другая форма ещё создаётся. Дождитесь завершения.');
    running=true;
    try{const c=await credentials();validateCredentials(c);job.status='running';job.epoch=epoch;await putJob(job);
      const result=await createForm(job.config,c,{publish:message.publish===true,progress:async update=>{Object.assign(job,update);await putJob(job);}});
      job.status='success';job.result=result;await putJob(job);return safeStatus(job);
    }catch(error){job.status='error';job.error=error.message;if(error.result)job.result=error.result;await putJob(job);return safeStatus(job);}finally{running=false;}
  }
  if(message.type==='oauth'){
    const clientId=message.clientId?.trim();if(!/^[a-f0-9]{32}$/i.test(clientId??''))throw new Error('Укажите ClientID OAuth-приложения (32 символа).');
    const redirect=chrome.identity.getRedirectURL('oauth'),state=crypto.randomUUID();
    const verifier=Array.from(crypto.getRandomValues(new Uint8Array(32)),v=>v.toString(16).padStart(2,'0')).join('');
    const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(verifier));const challenge=btoa(String.fromCharCode(...new Uint8Array(hash))).replaceAll('+','-').replaceAll('/','_').replaceAll('=','');
    const scope='forms:read forms:write'+(message.org_header==='X-Org-Id'?' directory:read_organization':'');
    const u=new URL('https://oauth.yandex.ru/authorize');u.search=new URLSearchParams({response_type:'code',client_id:clientId,redirect_uri:redirect,scope,state,code_challenge:challenge,code_challenge_method:'S256'});
    let callback;try{callback=await chrome.identity.launchWebAuthFlow({url:u.href,interactive:true});}catch{throw new Error('Вход отменён или Redirect URI не зарегистрирован для этого расширения.');}
    const returned=new URL(callback);if(returned.origin!==new URL(redirect).origin||returned.pathname!==new URL(redirect).pathname||returned.searchParams.get('state')!==state||!returned.searchParams.get('code'))throw new Error('Ответ авторизации не прошёл проверку.');
    let response;try{response=await fetch('https://oauth.yandex.ru/token',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({grant_type:'authorization_code',code:returned.searchParams.get('code'),client_id:clientId,code_verifier:verifier}),credentials:'omit',redirect:'error',signal:AbortSignal.timeout(20000)});}catch{throw new Error('Не удалось завершить обмен кода авторизации.');}
    if(!response.ok)throw new Error('Яндекс не выдал токен. Проверьте ClientID, разрешения и Redirect URI.');
    let token;try{token=await response.json();}catch{throw new Error('Яндекс вернул некорректный ответ авторизации.');}if(typeof token?.access_token!=='string')throw new Error('Ответ авторизации не содержит токена.');
    await saveCredentials({token:token.access_token,org_id:'',org_header:message.org_header,auth_scheme:'OAuth',...(token.expires_in?{expires_at:Date.now()+token.expires_in*1000}:{})},!!message.remember);
    await chrome.storage.local.set({clientId});return{connected:true};
  }
  throw new Error('Неизвестное действие.');
}
chrome.runtime.onMessage.addListener((message,sender,reply)=>{dispatch(message,sender).then(data=>reply({ok:true,data})).catch(error=>reply({ok:false,error:error.message}));return true;});
chrome.action.onClicked.addListener(()=>chrome.tabs.create({url:SITE}));
chrome.runtime.onInstalled.addListener(()=>harden());
