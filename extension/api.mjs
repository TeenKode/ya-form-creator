import {dryRun} from './core.mjs';
export const API = 'https://api.forms.yandex.net/v1';
export function validateAuth(c){
  if(!c||c.auth_scheme!=='OAuth'||c.org_header!=='X-Cloud-Org-Id')throw new Error('Войдите через Яндекс, чтобы подключить Identity Hub.');
  if(typeof c.token!=='string'||!c.token||!/^[\x21-\x7e]+$/.test(c.token))throw new Error('Войдите через Яндекс заново.');
  if(c.expires_at&&c.expires_at<Date.now())throw new Error('Срок токена истёк. Войдите через Яндекс заново.');
}
export function validateCredentials(c){validateAuth(c);if(typeof c.org_id!=='string'||!c.org_id||!/^[\x21-\x7e]+$/.test(c.org_id))throw new Error('Выберите организацию или укажите её ID.');}
export async function callApi(path,method,credentials,payload,{fetcher=fetch,signal}={}){
  validateCredentials(credentials);
  if(!/^\/(users\/me|surveys(?:\/[a-f0-9]{24}(?:\/questions(?:\/[0-9]+\/conditions)?|\/publish)?)?)$/.test(path))throw new Error('Неподдерживаемое действие API.');
  let response;
  try{response=await fetcher(API+path,{method,headers:{Authorization:`${credentials.auth_scheme} ${credentials.token}`,'Content-Type':'application/json',[credentials.org_header]:credentials.org_id},...(payload===undefined?{}:{body:JSON.stringify(payload)}),redirect:'error',credentials:'omit',cache:'no-store',signal:signal??AbortSignal.timeout(20000)});}
  catch{throw new Error('Сбой сети или таймаут. Запрос мог быть принят: проверьте кабинет Яндекса перед повтором.');}
  if(!response.ok){const hints={401:'Токен недействителен или истёк.',403:'Проверьте права forms:read, forms:write и доступ к организации.',429:'Превышен лимит запросов. Подождите перед повтором.'};throw new Error(`Яндекс API: HTTP ${response.status}. ${hints[response.status]??'Данные не приняты. Проверьте анкету и настройки организации.'}`);}
  const text=await response.text();if(!text.trim())return {};
  let value;try{value=JSON.parse(text);}catch{throw new Error('API вернул некорректный JSON.');}
  if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('API вернул неожиданный формат.');return value;
}
export async function createForm(config,credentials,{publish=false,fetcher=fetch,progress=async()=>{}}={}){
  const plan=dryRun(config);validateCredentials(credentials);
  if(plan.questions.length>200||plan.conditions.length>300)throw new Error('После развёртки слишком много элементов для одной операции расширения (максимум 200 вопросов и 300 условий). Используйте настольную версию.');
  const deadline=Date.now()+230000;let result=null;
  const call=async(path,method,payload)=>{if(Date.now()>deadline)throw new Error('Истекло время одной операции расширения. Проверьте частичный черновик; автоматического повтора нет.');return callApi(path,method,credentials,payload,{fetcher});};
  await progress({phase:'access',done:0,total:plan.questions.length+plan.conditions.length});
  await call('/surveys','GET');
  try{
    const survey=await call('/surveys','POST',plan.survey);
    if(typeof survey.id!=='string'||!/^[a-f0-9]{24}$/i.test(survey.id))throw new Error('Создание подтверждено, но API не вернул корректный ID. Проверьте кабинет Форм.');
    const id=survey.id.toLowerCase();result={survey_id:id,edit_url:`https://forms.yandex.ru/admin/${id}`,fill_url:`https://forms.yandex.ru/cloud/${id}`,published:false,question_count:0,conditions_count:0};
    await progress({phase:'questions',done:0,total:plan.questions.length+plan.conditions.length,result});
    const created=new Map();
    for(const item of plan.questions){const answer=await call(`/surveys/${id}/questions`,'POST',item);
      if(item.slug){if(!Number.isSafeInteger(answer.id)||answer.id<=0)throw new Error('API не вернул ID вопроса.');created.set(item.slug,answer);}
      result.question_count++;await progress({phase:'questions',done:result.question_count,total:plan.questions.length+plan.conditions.length,result});
    }
    for(const rule of plan.conditions){const source=created.get(rule.source),target=created.get(rule.target);if(!source||!target)throw new Error('Не найдены созданные вопросы для условия.');
      const options=new Map((source.items??[]).map(item=>[item.label,item]));
      const items=rule.answers.map(label=>{const opt=options.get(label),value=opt?.id??opt?.slug;if(value===undefined||value===null)throw new Error('API не вернул вариант ответа для условия.');return{type:'question',condition:rule.condition??'eq',question:source.slug??rule.source,value:String(value)};});
      await call(`/surveys/${id}/questions/${target.id}/conditions`,'POST',{operator:rule.operator??'and',items});result.conditions_count++;
      await progress({phase:'conditions',done:result.question_count+result.conditions_count,total:plan.questions.length+plan.conditions.length,result});
    }
    if(publish){await call(`/surveys/${id}/publish`,'POST');result.published=true;}
    return result;
  }catch(error){if(result){const partial=new Error('Создание остановлено. Черновик сохранён частично. '+error.message);partial.result=result;throw partial;}throw error;}
}
