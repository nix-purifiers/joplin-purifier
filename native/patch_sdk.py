from pathlib import Path

p = Path("app-tree/main-html.bundle.js")
s = p.read_text()
marker = "let s=await(0,g5u.default)().start((0,Gae.default)().processArgv());"
assert s.count(marker) == 1
hook = """if(process.env.JOPLIN_PURIFIER_SCRIPT){setTimeout(async()=>{
let scriptStatus=0;try{
 const context={app:(0,g5u.default)(),Setting:wOe.default,Note:b5u.default,Folder:y5u.default,
 pluginService:ly().default.instance(),commands:Gi().default.instance(),interop:NL().default.instance()};
 const result=await Qe(process.env.JOPLIN_PURIFIER_SCRIPT)(context);
 if(Number.isInteger(result))scriptStatus=result;
 await wOe.default.saveAll();
}catch(error){scriptStatus=Number.isInteger(error.exitCode)?error.exitCode:1;Qe('fs').writeFileSync(process.env.JOPLIN_PURIFIER_ERROR,String(error.stack||error));}
Qe('fs').writeFileSync(process.env.JOPLIN_PURIFIER_STATUS,String(scriptStatus));
(0,Gae.default)().electronApp().quit();
},0);}"""
p.write_text(s.replace(marker, marker + hook))

guard = Path(__file__).with_name("guard.js").read_text()
s = p.read_text()
assert s.count("N5u();})();") == 1
s = s.replace("N5u();})();", guard + "N5u();})();")
assert s.count("builtIn:i.builtIn") == 1
s = s.replace(
    "builtIn:i.builtIn", "builtIn:i.builtIn||!!process.env.JOPLIN_PURIFIER_ENVIRONMENT"
)
assert s.count('(0,_E._)("Built-in")') == 1
s = s.replace(
    '(0,_E._)("Built-in")',
    '(process.env.JOPLIN_PURIFIER_ENVIRONMENT?"Locked":(0,_E._)("Built-in"))',
)
p.write_text(s)
p = Path("app-tree/main.bundle.js")
s = p.read_text()
marker = "if(await this.profileLocker_.lock())return!1;"
assert s.count(marker) == 1
s = s.replace(
    marker,
    marker
    + 'if(process.env.JOPLIN_PURIFIER_ENVIRONMENT){console.error("Joplin profile already in use; close the existing instance before a locked launch");this.electronApp_.exit(1);return!0;}',
)
marker = "if(this.isEndToEndTesting_)return!1;"
assert s.count(marker) == 1
s = s.replace(
    marker,
    "if(this.isEndToEndTesting_&&!process.env.JOPLIN_PURIFIER_ENVIRONMENT)return!1;",
)
p.write_text(s)
