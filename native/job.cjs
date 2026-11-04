const fs=require('fs'),path=require('path'),crypto=require('crypto'),assert=require('assert'),cp=require('child_process');
module.exports=async(native)=>{
 const request=JSON.parse(fs.readFileSync(process.env.JOPLIN_PURIFIER_REQUEST,'utf8'));
 const root=process.env.JOPLIN_PURIFIER_HELPER_STATE;
 const sdk=process.env.JOPLIN_PURIFIER_ORIGINAL;
 const version=JSON.parse(fs.readFileSync(path.join(sdk,'share/joplin-desktop/resources/app.asar/package.json'),'utf8')).version;
 if(version!=='3.7.21')throw new Error('This native bundle provider supports Joplin 3.7.21');
 for(const name of ['cache','plugins','temp'])fs.mkdirSync(path.join(root,name),{recursive:true});
 const Setting=native.settings.default;
 for(const [key,value] of Object.entries({appId:'net.cozic.joplin-desktop',appType:native.settings.AppType.Desktop,profileDir:root,cacheDir:root+'/cache',pluginDir:root+'/plugins',tempDir:root+'/temp'}))Setting.setConstant(key,value);
 native.shimInit.shimInit({appVersion:()=>version});
 const proxy=process.env.HTTPS_PROXY||process.env.HTTP_PROXY;
 native.shimInit.setupProxySettings({proxyEnabled:!!proxy,proxyUrl:proxy||'',proxyTimeout:60,maxConcurrentConnections:5});
 const service=native.plugins.default.instance();service.initialize(version,null,null,null);
 const validate=filename=>cp.execFileSync(process.env.JOPLIN_PURIFIER_PYTHON,[path.join(__dirname,'validate_archive.py'),filename]);
 const sha256=filename=>crypto.createHash('sha256').update(fs.readFileSync(filename)).digest('hex');
 if(request.action==='capture'){
  if(!request.plugins.length)return {entries:[],metadata:{},repository:{}};
  const repo=new native.repository.default('https://github.com/joplin/plugins',root+'/temp',{version,type:native.settings.AppType.Desktop},native.repository.InstallMode.Default);
  await repo.initialize();const manifests=await repo.manifests();
  const entries=[],metadata={},repository={};
  for(const id of request.plugins){
   const record=manifests.find(m=>m.id===id);
   if(!record||!await repo.pluginCanBeUpdated(id,'0.0.0'))throw new Error('No compatible native repository plugin: '+id);
   const filename=await repo.downloadPlugin(id);validate(filename);
   const bytesSha256=sha256(filename);
   if(record._publish_hash&&record._publish_hash!=='sha256:'+bytesSha256)throw new Error('Native published hash differs from downloaded plugin');
   await service.installPlugin(filename,false);
   const plugin=await service.loadPluginFromPath(root+'/plugins/'+id+'.jpl');
   assert.equal(plugin.id,id);assert.equal(plugin.manifest.version,record.version);
   entries.push({path:id+'.jpl',id,url:repo.assetFileUrl(id),bytesSha256});
   metadata[id]=plugin.manifest;repository[id]=record;
  }
  return {entries,metadata,repository};
 }
 if(request.action!=='install')throw new Error('Unknown native helper action');
 const output=request.output;
 const manifest={selected:{},builtin:{}};
 const entries=request.entries.map(entry=>({...entry,path:request.archives[entry.path],manifest:request.metadata[entry.id]}));
 const defaults=path.join(sdk,'share/joplin-desktop/resources/build/defaultPlugins');
 for(const name of fs.readdirSync(defaults).filter(n=>n.endsWith('.jpl')).sort())entries.push({id:name.slice(0,-4),path:path.join(defaults,name),kind:'builtin'});
 for(const entry of entries){
  validate(entry.path);
  await service.installPlugin(entry.path,false);
  const plugin=await service.loadPluginFromPath(root+'/plugins/'+entry.id+'.jpl');
  assert.equal(plugin.id,entry.id);
  const nativeManifest=JSON.parse(JSON.stringify(plugin.manifest));
  if(entry.manifest)assert.deepStrictEqual(nativeManifest,entry.manifest);
  const kind=entry.kind||'selected';const relative=(kind==='builtin'?'builtin':'plugins')+'/'+entry.id;
  fs.mkdirSync(path.dirname(path.join(output,relative)),{recursive:true});
  fs.cpSync(plugin.baseDir,path.join(output,relative),{recursive:true,dereference:false});
  manifest[kind][entry.id]={directory:relative,manifest:nativeManifest};
 }
 fs.mkdirSync(path.join(output,'plugins'),{recursive:true});
 fs.writeFileSync(path.join(output,'manifest.json'),JSON.stringify(manifest,null,2));
 return {selected:Object.keys(manifest.selected),builtin:Object.keys(manifest.builtin)};
};
