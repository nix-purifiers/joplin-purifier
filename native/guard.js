if(process.env.JOPLIN_PURIFIER_ENVIRONMENT){
 const fs=Qe('fs'),path=Qe('path');
 const root=fs.realpathSync(process.env.JOPLIN_PURIFIER_ENVIRONMENT);
 const manifest=JSON.parse(fs.readFileSync(path.join(root,'manifest.json'),'utf8'));
 const directories=Object.values({...manifest.selected,...manifest.builtin}).map(item=>fs.realpathSync(path.join(root,item.directory)));
 const Setting=Pn().default;
 const value=Setting.value;
 Setting.value=function(key,...args){
  if(key==='pluginDir')return path.join(root,'plugins');
  if(key==='plugins.devPluginPaths')return '';
  if(key==='startupDevPlugins')return [];
  return value.call(this,key,...args);
 };
 const Service=ly().default;
 const load=Service.prototype.loadPluginFromPath;
 Service.prototype.loadPluginFromPath=async function(filename,...args){
  const builtin=path.join(process.resourcesPath,'build/defaultPlugins');
  if(path.dirname(path.resolve(filename))===builtin&&filename.endsWith('.jpl')){
   const id=path.basename(filename,'.jpl');
   if(!manifest.builtin[id])throw new Error('Unlisted Joplin SDK plugin');
   filename=path.join(root,manifest.builtin[id].directory);
  }
  if(!directories.includes(fs.realpathSync(filename)))throw new Error('Unlocked Joplin plugin path was rejected');
  return load.call(this,filename,...args);
 };
 const frozen=async()=>{throw new Error('Joplin plugins are locked; run joplin-purifier lock --update');};
 for(const key of ['loadPluginFromPackage','installPlugin','installPluginFromRepo','updatePluginFromRepo','deletePluginFiles'])Service.prototype[key]=frozen;
 Service.prototype.loadAndRunDevPlugins=async()=>{};
 Service.prototype.uninstallPlugins=async function(settings){
  return Object.fromEntries(Object.entries(settings).map(([id,item])=>[id,{...item,deleted:false}]));
 };
}
