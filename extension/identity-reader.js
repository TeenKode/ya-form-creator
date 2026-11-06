// Reads only an organization identifier visible in the user-selected cabinet tab.
chrome.runtime.onMessage.addListener((message,sender,reply)=>{
  if(sender.id!==chrome.runtime.id||message?.type!=='read-identity-organization')return;
  if(location.protocol!=='https:'||!['center.yandex.cloud','org.yandex.cloud'].includes(location.hostname))return;
  const ids=[...new Set((document.body?.innerText??'').match(/\bbpf[a-z0-9]{17}\b/g)??[])];
  reply({id:ids.length===1?ids[0]:null});
});
