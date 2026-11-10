const fs=require('fs'),path=require('path'),os=require('os'),assert=require('assert');
module.exports=async({app,Setting,Note,Folder,pluginService,commands,interop})=>{
 const id='io.github.jackgruber.combine-notes';
 const answer=JSON.parse(fs.readFileSync(path.join(__dirname,'answer.json'),'utf8')).answer;
 const deadline=Date.now()+60000;
 while(!pluginService.pluginById(id)?.running||!pluginService.allPluginsStarted){
  if(Date.now()>deadline)throw new Error('Native plugin did not start');
  await new Promise(r=>setTimeout(r,50));
 }
 const plugin=pluginService.pluginById(id);
 assert.equal(plugin.manifest.version,'1.2.3');
 const prefix='plugin-'+id+'.';
 for(const [key,value] of Object.entries({preserveSourceNoteTitles:true,preserveMetadataSourceUrl:false,preserveMetadataCreatedDate:false,preserveMetadataUpdatedDate:false,preserveMetadataLocation:false,addCombineDate:false,deleteCombinedNotes:false,combinedNoteTitle:'custom',combinedNoteTitleCustom:'Purifier Combined'}))Setting.setValue(prefix+key,value);
 const folder=await Folder.save({title:'Purifier Fixture'});
 const first=await Note.save({title:'First',body:String(answer),parent_id:folder.id});
 const second=await Note.save({title:'Second',body:'Second body',parent_id:folder.id});
 app.switchCurrentFolder(folder);
 await app.refreshNotes(app.store().getState());
 app.store().dispatch({type:'NOTE_SELECT',ids:[first.id,second.id]});
 assert.deepEqual(app.store().getState().selectedNoteIds,[first.id,second.id]);
 await commands.execute('CombineNotes');
 const selected=app.store().getState().selectedNoteIds;
 assert.equal(selected.length,1);
 assert(![first.id,second.id].includes(selected[0]));
 const combined=await Note.load(selected[0]);
 assert(combined.body.includes(String(answer))&&combined.body.includes('Second body'));
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'joplin-export-'));
 await interop.export({format:'md',path:temp,sourceNoteIds:[combined.id]});
 const files=[];const walk=d=>{for(const f of fs.readdirSync(d,{withFileTypes:true})){const p=path.join(d,f.name);if(f.isDirectory())walk(p);else if(p.endsWith('.md'))files.push(p)}};walk(temp);
 assert.equal(files.length,1);
 const output=process.env.JOPLIN_PURIFIER_OUTPUT||path.join(__dirname,'output');fs.mkdirSync(output,{recursive:true});
 fs.copyFileSync(files[0],path.join(output,'combined.md'));
 fs.rmSync(temp,{recursive:true,force:true});
};
