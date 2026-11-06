const $=id=>document.getElementById(id);
async function send(message){const r=await chrome.runtime.sendMessage(message);if(!r?.ok)throw new Error(r?.error??'Расширение недоступно.');return r.data;}
function status(text,error=false){$('status').textContent=text;$('status').className=error?'error':'success';}
let state={};
function render(){
  $('organizationControls').hidden=!state.signedIn||state.configured;
  $('organizationIntro').textContent=state.configured?'Организация подключена.':state.signedIn?'Организация — это место, где будут храниться ваши формы.':'Сначала войдите в Яндекс на шаге 1.';
  $('loginState').textContent=state.signedIn?'Вы вошли в Яндекс.':'';$('oauth').textContent=state.signedIn?'Войти другим аккаунтом ↗':'Войти через Яндекс ↗';
  $('forget').hidden=!state.signedIn;$('doneStep').hidden=!state.configured;$('readOrganization').hidden=!state.setupPending;
  $('organizationName').textContent=state.org_id?'ID: '+state.org_id:'';
  for(const [id,active] of [['step1',!state.signedIn],['step2',state.signedIn&&!state.configured],['step3',state.configured]]){if(active)$(id).setAttribute('aria-current','step');else $(id).removeAttribute('aria-current');}
}
async function load(){state=await send({type:'settings'});for(const id of ['clientId','redirect'])$(id).value=state[id];$('remember').checked=state.remember;render();}
async function action(callback){const controls=[...document.querySelectorAll('button,input')];controls.forEach(b=>b.disabled=true);try{await callback();}catch(e){status(e.message,true);}finally{controls.forEach(b=>b.disabled=false);}}
$('oauth').addEventListener('click',()=>action(async()=>{status('Ожидаем вход в Яндекс…');await send({type:'oauth',clientId:$('clientId').value,remember:$('remember').checked});$('candidate').hidden=true;$('org_id').value='';await load();status('Шаг 1 готов. Теперь выберите организацию.');$('organizationStep').scrollIntoView({behavior:'smooth',block:'start'});}));
$('openOrganization').addEventListener('click',()=>action(async()=>{await send({type:'organization-open'});state.setupPending=true;render();status('Выберите или создайте организацию в открывшейся вкладке Яндекса, затем вернитесь сюда.');}));
$('readOrganization').addEventListener('click',()=>action(async()=>{$('candidate').hidden=true;$('org_id').value='';status('Проверяем выбранную вкладку…');try{const r=await send({type:'organization-read'});$('org_id').value=r.id;$('candidate').hidden=false;status('Организация найдена. Сверьте ID и нажмите «Проверить и подключить».');}catch(e){$('manualOrg').open=true;throw e;}}));
$('manualEntry').addEventListener('click',()=>{$('candidate').hidden=false;$('org_id').focus();});
$('connectForm').addEventListener('submit',e=>{e.preventDefault();action(async()=>{status('Проверяем доступ к Формам…');await send({type:'organization-connect',id:$('org_id').value,remember:$('remember').checked});await load();status('Подключение завершено. Можно создавать формы.');$('doneStep').scrollIntoView({behavior:'smooth',block:'start'});});});
$('changeOrganization').addEventListener('click',()=>{state.configured=false;$('candidate').hidden=true;$('org_id').value='';render();status('Текущее подключение сохранится, пока вы не подключите другую организацию.');});
$('forget').addEventListener('click',()=>action(async()=>{await send({type:'forget'});$('org_id').value='';$('candidate').hidden=true;await load();status('Вы вышли из аккаунта.');}));
load().catch(e=>status(e.message,true));
