// Shared, dependency-free contract for the website and the extension.
export const VERSION = '1.5.1';
export const TYPES = {radio:'Один вариант',checkbox:'Несколько вариантов',dropdown:'Выпадающий список',scale:'Шкала',stars:'Звёзды',onerow:'В одну строку',text:'Текст',matrix:'Матрица',boolean:'Да / нет',integer:'Целое число',date:'Дата',section:'Раздел',comment:'Текстовый блок',api:'Расширенный API'};
export const FORMATS = {plain:'Обычный текст',full_name:'ФИО / имя',phone:'Телефон РФ',email:'Электронная почта',url:'Ссылка',inn:'ИНН',decimal:'Дробное число'};
const ENUM = ['radio','checkbox','dropdown','scale','stars','onerow'];
const SOURCES = ['radio','checkbox','dropdown'];
const SPECIAL = ['phone','email','url','inn','decimal'];
const AUTO = ['не использую','не пользуюсь','не применяю','никогда','ничего','ничего из перечисленного','ничего не мешает','нет необходимости','затрудняюсь ответить','не знаю','никакие','ни один из перечисленных','none of the above','i do not use','not applicable'];
const GATE = 'Выбрать варианты из списка';
const copy = v => structuredClone(v);
const obj = v => v !== null && typeof v === 'object' && !Array.isArray(v);
const nonempty = v => typeof v === 'string' && v.trim().length > 0;
const slugOK = v => typeof v === 'string' && /^[A-Za-z][A-Za-z0-9_-]*$/.test(v);
const fail = message => { throw new Error(message); };
export const optionLabel = v => typeof v === 'string' ? v : v.label;
export function exclusiveOptions(q) {
  if(q.type !== 'checkbox') return [];
  return q.exclusive_options ?? (q.options ?? []).map(optionLabel).filter(s=>AUTO.includes(s.trim().replace(/[.!?]+$/,'').toLowerCase()));
}
function labels(items, minimum, where) {
  if(!Array.isArray(items) || items.length < minimum) fail(`${where}: минимум ${minimum} элементов.`);
  const values = items.map(v=>typeof v==='string'?v:obj(v)?v.label:null);
  if(values.some(v=>!nonempty(v)) || new Set(values).size !== values.length) fail(`${where}: подписи должны быть непустыми и уникальными.`);
  return values;
}
function bounds(q, fields, where) {
  for(const key of fields) if(key in q && (!Number.isSafeInteger(q[key]) || q[key]<0)) fail(`${where}.${key}: нужно неотрицательное целое число.`);
  if(fields[0] in q && fields[1] in q && q[fields[0]]>q[fields[1]]) fail(`${where}: минимум больше максимума.`);
}
function validDate(s) {
  if(typeof s!=='string' || !/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(s) || s.slice(0,4)==='0000') return false;
  const d=new Date(s+'T00:00:00Z'); return !Number.isNaN(+d) && d.toISOString().slice(0,10)===s;
}
export function validateConfig(config, {allowEmpty=false}={}) {
  if(!obj(config)||!obj(config.form)||!nonempty(config.form.name)) fail('form.name: укажите название анкеты.');
  const {form,questions}=config;
  for(const k of ['allow_multiple_answers','need_auth','publish_by_default']) if(k in form && typeof form[k]!=='boolean') fail(`form.${k}: ожидается true или false.`);
  for(const k of ['submit_text','success_title','success_subtitle']) if(k in form && typeof form[k]!=='string') fail(`form.${k}: ожидается текст.`);
  if(!Array.isArray(questions)||(!allowEmpty&&!questions.length)) fail('Добавьте хотя бы один вопрос.');
  if(questions.length>150) fail('Веб-версия поддерживает до 150 исходных элементов за одну операцию.');
  const slugs=new Set(), indices=new Map(), options=new Map(), sourceTypes=new Map(), others=[];
  questions.forEach((q,i)=>{
    const where=`Вопрос ${i+1}`;
    if(!obj(q)||!Object.hasOwn(TYPES,q.type)||!nonempty(q.label)) fail(`${where}: укажите поддерживаемый тип и текст.`);
    if('format' in q && (q.type!=='text'||!Object.hasOwn(FORMATS,q.format))) fail(`${where}: неизвестный формат текстового поля.`);
    if(q.format && q.format!=='plain' && q.multiline===true) fail(`${where}: специальный формат должен быть однострочным.`);
    for(const k of ['unique','validation','validators','pattern','regex']) if(k in q) fail(`${where}.${k}: неподдерживаемое ограничение. Используйте text.format или api.payload.`);
    for(const k of ['required','hidden','multiline','header','has_quiz','show_first','show_suggest']) if(k in q && typeof q[k]!=='boolean') fail(`${where}.${k}: ожидается true или false.`);
    for(const k of ['comment','placeholder']) if(k in q && typeof q[k]!=='string') fail(`${where}.${k}: ожидается текст.`);
    if('widget' in q && !['radio','checkbox','dropdown','stars','onerow'].includes(q.widget)) fail(`${where}: неизвестный widget.`);
    if(q.hidden && q.required) fail(`${where}: скрытый вопрос не может быть обязательным.`);
    if(q.type!=='checkbox' && 'exclusive_options' in q) fail(`${where}: exclusive_options доступен только для checkbox.`);
    if(['section','comment'].includes(q.type)) {if('other' in q) fail(`${where}: other недоступен для блока.`); return;}
    if(!slugOK(q.slug)||slugs.has(q.slug)) fail(`${where}: нужен уникальный код из латиницы, цифр, _ или -, начиная с буквы.`);
    slugs.add(q.slug);indices.set(q.slug,i);
    if(ENUM.includes(q.type)) {
      const values=labels(q.options,2,where+'.options');options.set(q.slug,values);sourceTypes.set(q.slug,q.type);
      for(const opt of q.options) if(obj(opt)) {
        for(const k of ['correct','hidden']) if(k in opt && typeof opt[k]!=='boolean') fail(`${where}: ${k} должен быть boolean.`);
        if('scores' in opt && (typeof opt.scores!=='number'||!Number.isFinite(opt.scores))) fail(`${where}: scores должен быть конечным числом.`);
      }
      if(q.type==='checkbox') {
        if('exclusive_options' in q && (!Array.isArray(q.exclusive_options)||q.exclusive_options.some(s=>!nonempty(s)||!values.includes(s))||new Set(q.exclusive_options).size!==q.exclusive_options.length)) fail(`${where}: неверные исключающие ответы.`);
        const exclusions=exclusiveOptions(q), remaining=values.length-exclusions.length;
        bounds(q,['min_choices','max_choices'],where);
        if(q.min_choices>values.length||q.max_choices>values.length) fail(`${where}: ограничение выбора больше числа вариантов.`);
        if(exclusions.length && (remaining<2||q.hidden||q.has_quiz||q.options.some(o=>obj(o)&&('correct'in o||'scores'in o))||q.max_choices>remaining)) fail(`${where}: исключающие ответы несовместимы с настройками; нужны минимум два обычных варианта.`);
      }
    } else if(q.type==='text') {
      if('min'in q||'max'in q) fail(`${where}: для текста используйте min_length/max_length.`);
      bounds(q,['min_length','max_length'],where);
    } else if(q.type==='matrix') {labels(q.rows,1,where+'.rows');labels(q.columns,2,where+'.columns');}
    else if(q.type==='integer') {
      for(const k of ['min','max']) if(k in q&&!Number.isSafeInteger(q[k])) fail(`${where}: ${k} — целое в безопасном диапазоне JavaScript.`);
      if(q.min>q.max) fail(`${where}: min больше max.`);
    } else if(q.type==='date') {
      for(const k of ['min','max']) if(k in q&&!validDate(q[k])) fail(`${where}: дата ${k} должна быть YYYY-MM-DD.`);
      if(q.min>q.max) fail(`${where}: min позже max.`);
    } else if(q.type==='api') {
      if(!obj(q.payload)||!nonempty(q.payload.type)||(q.payload.slug??q.slug)!==q.slug) fail(`${where}: неверный api.payload.`);
      const v=q.payload.validators??[];
      if(!Array.isArray(v)||v.some(x=>!obj(x)||!nonempty(x.type))) fail(`${where}: неверный payload.validators.`);
    }
    if(q.other!==undefined&&q.other!==null) {
      if(!SOURCES.includes(q.type)||!obj(q.other)) fail(`${where}: other доступен для выбора ответа.`);
      for(const k of ['required','multiline']) if(k in q.other&&typeof q.other[k]!=='boolean') fail(`${where}: other.${k} — boolean.`);
      for(const k of ['label','placeholder']) if(k in q.other&&!nonempty(q.other[k])) fail(`${where}: other.${k} — непустой текст.`);
      const option=q.other.option??'Другое',slug=q.other.slug??q.slug+'_other';
      if(!options.get(q.slug).includes(option)||exclusiveOptions(q).includes(option)||!slugOK(slug)) fail(`${where}: неверное поле «Другое».`);
      others.push({target:slug,source:q.slug,answers:[option]});
    }
  });
  for(const o of others){if(slugs.has(o.target))fail(`Код ${o.target} уже занят.`);slugs.add(o.target);indices.set(o.target,indices.get(o.source));}
  for(const q of questions)if(exclusiveOptions(q).length){const s=q.slug+'_choice';if(slugs.has(s))fail(`Код ${s} занят служебным переключателем.`);slugs.add(s);}
  const conditions=config.conditions??[];
  if(!Array.isArray(conditions)||conditions.length>300) fail('conditions: нужен массив не более 300 правил.');
  for(const c of [...conditions,...others]) {
    if(!obj(c)||!slugs.has(c.source)||!slugs.has(c.target)||!SOURCES.includes(sourceTypes.get(c.source)))fail('Условие ссылается на неизвестный вопрос или неподдерживаемый источник.');
    if(!indices.has(c.target)||!(indices.get(c.source)<indices.get(c.target)||(others.some(o=>o.target===c.target)&&indices.get(c.source)===indices.get(c.target))))fail('Источник условия должен идти раньше зависимого вопроса.');
    if(!Array.isArray(c.answers)||!c.answers.length||c.answers.some(s=>!nonempty(s)||!options.get(c.source).includes(s)))fail('В условии указан неизвестный вариант ответа.');
    if(!['and','or'].includes(c.operator??'and')||!['eq','neq'].includes(c.condition??'eq'))fail('Неверный оператор условия.');
  }
  return config;
}
export function resolveExclusive(config) {
  validateConfig(config);const result=copy(config), info=new Map(), qs=[];
  for(const q of result.questions){const exclusions=exclusiveOptions(q);if(!exclusions.length){qs.push(q);continue;}
    if(q.options.map(optionLabel).includes(GATE))fail('Служебный вариант уже используется в вопросе.');
    const gate=q.slug+'_choice';info.set(q.slug,{gate,exclusions});
    const g={type:'radio',slug:gate,label:q.label,options:[GATE,...exclusions],required:!!q.required};if(q.comment)g.comment=q.comment;
    delete q.exclusive_options;q.options=q.options.filter(o=>!exclusions.includes(optionLabel(o)));q.label='Уточните ответ: '+q.label;delete q.comment;q.required=true;qs.push(g,q);
  }
  if(!info.size)return result;
  result.questions=qs;result.conditions=(result.conditions??[]).map(c=>{
    if(info.has(c.target))c.target=info.get(c.target).gate;
    if(info.has(c.source)){const {gate,exclusions}=info.get(c.source), selected=c.answers.filter(s=>exclusions.includes(s));
      if(selected.length){if(selected.length!==c.answers.length)fail('Нельзя смешивать обычные и исключающие ответы в одном условии.');if((c.operator??'and')==='and'&&selected.length>1&&(c.condition??'eq')==='eq')fail('Несколько исключающих ответов одновременно невозможны.');c.source=gate;}
      else if(c.condition==='neq')fail('Условие neq неоднозначно для исключающих вариантов.');
    }return c;
  });
  for(const [slug,{gate}]of info)result.conditions.push({target:slug,source:gate,answers:[GATE]});
  validateConfig(result);return result;
}
export function validatorsFor(q){const v=q.required?[{type:'required'}]:[];if(ENUM.includes(q.type)&&q.type!=='checkbox')v.push({type:'single'});if(q.type==='text'&&SPECIAL.includes(q.format))v.push({type:q.format});
  const map={checkbox:[['min_choices','min'],['max_choices','max']],text:[['min_length','min'],['max_length','max']],integer:[['min','min'],['max','max']],date:[['min','min'],['max','max']]};for(const [key,type]of map[q.type]??[])if(key in q)v.push({type,value:q[key]});return v;}
export function buildQuestion(q){const common={label:q.label};for(const k of ['comment','placeholder','hidden'])if(k in q&&q[k]!==null&&q[k]!=='')common[k]=q[k];
  if(['section','comment'].includes(q.type)){delete common.placeholder;return {...common,type:'comment',header:q.header??(q.type==='section')};}
  if(q.type==='api'){const p={...copy(q.payload),...common,slug:q.slug};if(q.required){p.validators??=[];if(!p.validators.some(v=>v.type==='required'))p.validators.push({type:'required'});}return p;}
  common.slug=q.slug;const validators=validatorsFor(q);
  if(ENUM.includes(q.type)){const p={...common,type:'enum',widget:q.widget??({scale:'onerow'}[q.type]??q.type),items:q.options.map(o=>typeof o==='string'?{label:o}:copy(o)),validators};if(q.has_quiz)p.has_quiz=true;for(const k of ['show_first','show_suggest','modify_choices'])if(k in q)p[k]=q[k];return p;}
  if(q.type==='text')return {...common,type:'string',multiline:q.multiline??((q.format??'plain')==='plain'),validators};
  if(q.type==='matrix')return {...common,type:'matrix',rows:q.rows.map((v,i)=>({slug:`${q.slug}_r${i+1}`,label:optionLabel(v)})),columns:q.columns.map((v,i)=>({slug:`${q.slug}_c${i+1}`,label:optionLabel(v)})),validators};
  const p={...common,type:q.type,validators};if('initial'in q)p.initial=q.initial;return p;
}
export function expandQuestions(config){const effective=resolveExclusive(config),questions=[],conditions=copy(effective.conditions??[]);for(const q of effective.questions){questions.push(buildQuestion(q));if(q.other){const o=q.other,slug=o.slug??q.slug+'_other';questions.push({type:'string',label:o.label??'Укажите свой вариант',slug,multiline:o.multiline??false,placeholder:o.placeholder??'Введите свой вариант',validators:(o.required??true)?[{type:'required'}]:[]});conditions.push({target:slug,source:q.slug,answers:[o.option??'Другое'],operator:'and'});}}return {questions,conditions,effective};}
export function dryRun(config){const {questions,conditions}=expandQuestions(config),f=config.form;return {survey:{name:f.name,allow_multiple_answers:f.allow_multiple_answers??true,need_auth:f.need_auth??false,texts:{submit:f.submit_text??'Отправить',title:f.success_title??'Спасибо за ответы!',subtitle:f.success_subtitle??''}},questions,conditions};}
export function visibleSlugs(config,answers){const visible=new Set();const rules=[...(config.conditions??[])];for(const q of config.questions)if(q.other)rules.push({target:q.other.slug??q.slug+'_other',source:q.slug,answers:[q.other.option??'Другое']});
  function show(slug){return rules.filter(c=>c.target===slug).every(c=>{if(!visible.has(c.source))return false;const raw=answers[c.source],chosen=Array.isArray(raw)?raw:(raw?[raw]:[]);if(!chosen.length)return false;const checks=c.answers.map(s=>chosen.includes(s)===((c.condition??'eq')==='eq'));return(c.operator??'and')==='and'?checks.every(Boolean):checks.some(Boolean);});}
  for(const q of config.questions){if(q.hidden||['section','comment'].includes(q.type))continue;if(show(q.slug))visible.add(q.slug);if(q.other){const s=q.other.slug??q.slug+'_other';if(visible.has(q.slug)&&show(s))visible.add(s);}}return visible;}
