// No credentials and no arbitrary fetch API are exposed to the web page.
(() => {
  const CHANNEL='yaform-bridge-v1';
  window.addEventListener('message',event=>{
    if(event.source!==window||event.origin!==location.origin||event.data?.channel!==CHANNEL||event.data.direction!=='request')return;
    const {id,type,config,jobId}=event.data;
    if(typeof id!=='string'||id.length>80||!['ping','options','prepare','status'].includes(type))return;
    chrome.runtime.sendMessage({type,...(type==='prepare'?{config}:{}),...(type==='status'?{id:jobId}:{})},response=>{
      const error=chrome.runtime.lastError;
      window.postMessage({channel:CHANNEL,direction:'response',id,...(error?{ok:false,error:'Расширение обновлено. Перезагрузите страницу.'}:response)},location.origin);
    });
  });
})();
