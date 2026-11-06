import {dryRun,TYPES} from './core.mjs';
const $=id=>document.getElementById(id),id=new URL(location.href).searchParams.get('job');let active=false,current;
async function send(message){const r=await chrome.runtime.sendMessage(message);if(!r?.ok)throw new Error(r?.error??'Расширение недоступно.');return r.data;}
function show(text,error=false){$('status').textContent=text;$('status').className=error?'error':'success';}
async function account(){const s=await send({type:'settings'});$('account').textContent=s.configured?`${s.org_name||s.org_id} · Identity Hub`:'Подключите Яндекс и укажите организацию.';}
function draw(job){current=job;active=job.status==='running';$('confirmation').hidden=job.status!=='pending';$('progress').hidden=!active;if(active){$('progress').max=job.total||1;$('progress').value=job.done||0;show(`Создание: ${job.done??0} из ${job.total??'…'} элементов. Дождитесь результата.`);}
  if(job.status==='error'||job.status==='interrupted')show(job.error,true);
  if(job.status==='success')show(job.result.published?'Форма создана и опубликована.':'Черновик создан. Проверьте его в Яндексе перед публикацией.');
  if(job.result){$('result').hidden=false;$('resultTitle').textContent=job.status==='success'?'Готово':'Частичный черновик';$('links').replaceChildren();for(const [title,key]of [['Открыть редактирование','edit_url'],['Открыть заполнение','fill_url']]){const p=document.createElement('p'),a=document.createElement('a');a.textContent=title+' ↗';a.href=job.result[key];a.target='_blank';a.rel='noreferrer';p.append(a);$('links').append(p);}}
}
async function load(){const job=await send({type:'job',id}),plan=dryRun(job.config);$('name').textContent=job.config.form.name;$('counts').textContent=`Вопросов и блоков: ${job.config.questions.length}`;$('json').textContent=JSON.stringify(job.config,null,2);for(const q of job.config.questions){const li=document.createElement('li');li.textContent=q.label+' · '+TYPES[q.type];$('questions').append(li);}draw(job);await account();}
$('confirm').addEventListener('change',()=>$('create').disabled=!$('confirm').checked);
$('publish').addEventListener('change',()=>$('create').textContent=$('publish').checked?'Создать и опубликовать →':'Создать черновик в Яндексе →');
$('options').addEventListener('click',()=>send({type:'options'}));window.addEventListener('focus',()=>account().catch(e=>show(e.message,true)));
$('create').addEventListener('click',async()=>{if(active||!$('confirm').checked)return;$('create').disabled=true;active=true;show('Проверяем доступ и создаём новую форму…');try{draw(await send({type:'create',id,confirm:true,publish:$('publish').checked}));}catch(e){show(e.message,true);}finally{active=false;}});
setInterval(async()=>{if(active)try{draw(await send({type:'status',id}));}catch(e){show(e.message,true);}},1200);
load().catch(e=>show(e.message,true));
