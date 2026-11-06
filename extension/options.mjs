const $=id=>document.getElementById(id);
async function send(message){const r=await chrome.runtime.sendMessage(message);if(!r?.ok)throw new Error(r?.error??'Расширение недоступно.');return r.data;}
function status(text,error=false){$('status').textContent=text;$('status').className=error?'error':'success';}
async function action(callback){document.querySelectorAll('button').forEach(b=>b.disabled=true);try{await callback();}catch(e){status(e.message,true);}finally{document.querySelectorAll('button').forEach(b=>b.disabled=false);}}
function data(){return{org_id:$('org_id').value,org_header:$('org_header').value,auth_scheme:$('auth_scheme').value,token:$('token').value,remember:$('remember').checked};}
async function load(){const s=await send({type:'settings'});for(const id of ['org_id','org_header','auth_scheme','clientId','redirect'])$(id).value=s[id];$('remember').checked=s.remember;status(s.configured?'Подключение сохранено. Можно проверить доступ или вернуться к анкете.':'Укажите организацию и подключите аккаунт.');}
$('settings').addEventListener('submit',e=>{e.preventDefault();action(async()=>{await send({type:'save',...data()});$('token').value='';status('Подключение сохранено. Токен остаётся внутри расширения.');});});
$('reveal').addEventListener('change',()=>$('token').type=$('reveal').checked?'text':'password');
$('access').addEventListener('click',()=>action(async()=>{await send({type:'access'});status('Доступ к организации подтверждён.');}));
$('forget').addEventListener('click',()=>action(async()=>{await send({type:'forget'});$('token').value='';status('Локальные копии токена удалены. Для отзыва доступа используйте настройки Яндекс ID.');}));
$('oauth').addEventListener('click',()=>action(async()=>{if(!$('org_id').value.trim())throw new Error('Сначала укажите ID организации.');status('Ожидаем подтверждение в окне Яндекса…');await send({type:'oauth',...data(),clientId:$('clientId').value});$('token').value='';$('auth_scheme').value='OAuth';status('Вход выполнен. Можно вернуться к анкете.');}));
load().catch(e=>status(e.message,true));
