// Update this minimum when a site feature requires a newer extension.
// Site-only patch releases need not force a compatible extension update.
export const MIN_EXTENSION_VERSION='1.5.0';
export const SUPPORTED_EXTENSION_MAJOR=1;

function parseVersion(value){
  if(typeof value!=='string'||!/^(0|[1-9][0-9]{0,4})(\.(0|[1-9][0-9]{0,4})){0,3}$/.test(value))return null;
  const parts=value.split('.').map(Number);if(parts.some(n=>n>65535))return null;
  while(parts.length<4)parts.push(0);return parts;
}

export function assessExtension(version){
  const parts=parseVersion(version);if(!parts)return{state:'unknown',compatible:false};
  const minimum=parseVersion(MIN_EXTENSION_VERSION);
  for(let i=0;i<4;i++){
    if(parts[i]<minimum[i])return{state:'outdated',compatible:false,version};
    if(parts[i]>minimum[i])break;
  }
  if(parts[0]>SUPPORTED_EXTENSION_MAJOR)return{state:'site-outdated',compatible:false,version};
  return{state:'ready',compatible:true,version};
}
