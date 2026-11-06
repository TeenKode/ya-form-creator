// Run after build_browser.py. Formatting is development-time only; no remote code.
import {cp,mkdir,readFile,readdir,rm,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';
import {format} from 'prettier';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const output=path.join(root,'browser-build','opera-submission');
const extension=path.join(output,'extension');
// Only this fixed generated directory can be replaced.
await rm(output,{recursive:true,force:true});await mkdir(output,{recursive:true});
await cp(path.join(root,'browser-build','extension'),extension,{recursive:true});
for(const name of await readdir(extension)){
  const parser=name.endsWith('.mjs')||name.endsWith('.js')?'babel':name.endsWith('.css')?'css':name.endsWith('.html')?'html':null;
  if(parser)await writeFile(path.join(extension,name),await format(await readFile(path.join(extension,name),'utf8'),{parser}));
}
const manifest=JSON.parse(await readFile(path.join(extension,'manifest.json'),'utf8'));
// The marketplace assigns its own signing identity. Never assume the dev ID survives.
delete manifest.key;
manifest.homepage_url='https://teenkode.github.io/ya-form-creator/';
await writeFile(path.join(extension,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
await cp(path.join(root,'docs','opera-store'),path.join(output,'listing'),{recursive:true});
await cp(path.join(extension,'icons','icon128.png'),path.join(output,'icon128.png'));
const screenshots=path.join(output,'screenshots');await mkdir(screenshots);
for(const name of ['store-connect.png','store-review.png','store-confirm.png']){
  try{await cp(path.join(root,'test-results',name),path.join(screenshots,name));}
  catch(e){if(e.code!=='ENOENT')throw e;console.log('Screenshot not yet available: '+name+' (created by CI).');}
}
const zipName=`yaform-opera-${manifest.version}.zip`;
execFileSync('python',['-c',
  'from pathlib import Path; import sys,zipfile; source=Path(sys.argv[1]); z=zipfile.ZipFile(sys.argv[2],"w",zipfile.ZIP_DEFLATED); [(z.write(p,p.relative_to(source).as_posix())) for p in sorted(source.rglob("*")) if p.is_file()]; z.close()',
  extension,path.join(output,zipName)],{stdio:'inherit'});
console.log('Built '+path.relative(root,output)+'/'+zipName);
