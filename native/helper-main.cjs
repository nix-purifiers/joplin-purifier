const {app,BrowserWindow}=require('electron');
const fs=require('fs'),path=require('path');
app.disableHardwareAcceleration();
app.whenReady().then(async()=>{
 const window=new BrowserWindow({show:false,webPreferences:{nodeIntegration:true,contextIsolation:false,sandbox:false}});
 const sdk=process.env.JOPLIN_PURIFIER_ORIGINAL;
 const remote=require(path.join(sdk,'share/joplin-desktop/resources/app.asar/node_modules/@electron/remote/main'));
 remote.initialize();remote.enable(window.webContents);
 await window.loadURL('data:text/html,<html><body></body></html>');
 try{
  await window.webContents.executeJavaScript(`(async()=>{
   const native=require(${JSON.stringify(path.join(__dirname,'native.cjs'))});
   const result=await require(${JSON.stringify(path.join(__dirname,'job.cjs'))})(native);
   require('fs').writeFileSync(process.env.JOPLIN_PURIFIER_RESPONSE,JSON.stringify(result,null,2));
  })()`);
 }catch(error){console.error(error.stack);app.exit(1);return;}
 app.quit();
}).catch(error=>{console.error(error.stack);app.exit(1);});
