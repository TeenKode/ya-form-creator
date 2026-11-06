import {validateAuth} from './api.mjs';

const SOURCES={
  'X-Org-Id':{url:'https://api360.yandex.net/directory/v1/org',scheme:'OAuth'},
  'X-Cloud-Org-Id':{url:'https://organization-manager.api.cloud.yandex.net/organization-manager/v1/organizations',scheme:'Bearer'}
};

// Only names and IDs leave this module; no contact details from the directory.
export async function listOrganizations(credentials,orgHeader,{fetcher=fetch}={}){
  validateAuth(credentials);
  const source=SOURCES[orgHeader];if(!source)throw new Error('Выберите тип организации.');
  if(credentials.auth_scheme!==source.scheme)throw new Error(orgHeader==='X-Cloud-Org-Id'?'Для поиска организаций Cloud подключите пользовательский IAM-токен или укажите ID вручную.':'Для поиска организаций Яндекс 360 войдите через Яндекс.');
  const found=new Map(),seenPages=new Set();let pageToken='';
  for(let page=0;page<10;page++){
    const url=new URL(source.url);url.searchParams.set('pageSize','100');if(pageToken)url.searchParams.set('pageToken',pageToken);
    let response;try{response=await fetcher(url.href,{method:'GET',headers:{Authorization:`${source.scheme} ${credentials.token}`},credentials:'omit',redirect:'error',cache:'no-store',signal:AbortSignal.timeout(15000)});}catch{throw new Error('Не удалось загрузить организации. Попробуйте ещё раз или укажите ID вручную.');}
    if(!response.ok){if(response.status===401)throw new Error('Войдите заново: срок доступа мог истечь.');if(response.status===403)throw new Error('Яндекс не разрешил получить список организаций. Войдите заново или укажите ID вручную. Доступ может зависеть от вашей роли в организации.');throw new Error('Не удалось загрузить организации. Попробуйте позже или укажите ID вручную.');}
    let body;try{body=await response.json();}catch{throw new Error('Яндекс вернул непонятный список организаций. Укажите ID вручную.');}
    if(!body||!Array.isArray(body.organizations))throw new Error('Яндекс не вернул список организаций. Укажите ID вручную.');
    for(const item of body.organizations){
      const raw=item?.id,id=typeof raw==='string'?raw:Number.isSafeInteger(raw)&&raw>0?String(raw):'';
      if(!id||!/^[A-Za-z0-9_-]{1,128}$/.test(id))throw new Error('Не удалось прочитать ID организации. Укажите его вручную.');
      const name=orgHeader==='X-Cloud-Org-Id'?(item.title||item.name):item.name;
      found.set(id,{id,name:typeof name==='string'&&name.trim()?name.trim().slice(0,500):'Организация '+id,org_header:orgHeader});
    }
    const next=body.nextPageToken;if(next===undefined||next==='')return [...found.values()];
    if(typeof next!=='string'||next.length>2000||seenPages.has(next))throw new Error('Не удалось получить полный список организаций. Укажите ID вручную.');
    seenPages.add(next);pageToken=next;
  }
  throw new Error('Список организаций слишком большой. Укажите нужный ID вручную.');
}
