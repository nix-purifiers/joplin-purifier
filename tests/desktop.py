"""Native development-path positive/negative controls on private desktops."""

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

source = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(source / "native"))
from joplin_purifier_session import private_environment

cli = Path(sys.argv[1]).resolve() / "bin/joplin-purifier"
xvfb = Path(sys.argv[2]).resolve()
resources = Path(sys.argv[3]).resolve()

with tempfile.TemporaryDirectory(prefix="joplin-desktop-test-") as temporary:
    root = Path(temporary)
    project = root / "project"
    shutil.copytree(
        source / "examples/minimal",
        project,
        ignore=shutil.ignore_patterns(".joplin-purifier", "output"),
    )
    captured = subprocess.run(
        [cli, "--project", project, "prefetch"],
        check=True,
        capture_output=True,
        text=True,
    )
    environment = Path(captured.stdout.strip())
    sdk = environment / "sdk"
    built = subprocess.run(
        [cli, "--project", project, "build"],
        check=True,
        capture_output=True,
        text=True,
    )
    markdown = Path(built.stdout.strip()) / "combined.md"
    plugin = root / "ambient"
    plugin.mkdir()
    (plugin / "manifest.json").write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "id": "org.nix-purifiers.ambient",
                "app_min_version": "3.0",
                "version": "1.0.0",
                "name": "Ambient Probe",
                "description": "Native loading control",
                "author": "test",
            }
        )
    )
    (plugin / "index.js").write_text(
        "const api=joplin;api.plugins.register({onStart:async()=>{}});"
    )
    script = root / "probe.cjs"
    script.write_text("""
const assert=require('assert'),fs=require('fs');
module.exports=async({pluginService,Folder,Note,interop})=>{
 const end=Date.now()+60000;
 while(!pluginService.allPluginsStarted){
  if(Date.now()>end)throw Error('Native startup timed out');
  await new Promise(r=>setTimeout(r,50));
 }
 const plugin=pluginService.plugins['org.nix-purifiers.ambient'];
 if(process.env.EXPECT_AMBIENT==='yes')assert(plugin?.running,JSON.stringify({ids:Object.keys(pluginService.plugins),paths:require('fs').readdirSync(process.env.TEST_PROFILE)}));
 else assert(!plugin);
 if(process.env.EXPECT_AMBIENT==='yes'){
  assert(!pluginService.plugins['io.github.jackgruber.combine-notes']);
  const folder=await Folder.save({title:'Independent Consumer'});
  await interop.import({format:'md',path:process.env.PROBE_INPUT,destinationFolderId:folder.id});
  const notes=await Note.modelSelectAll('SELECT title,body FROM notes WHERE parent_id = ?',[folder.id]);
  assert.equal(notes.length,1);
  assert(notes[0].body.includes('42')&&notes[0].body.includes('Second body'));
 }
 fs.writeFileSync(process.env.PROBE_RESULT,'passed');
};
""")
    for locked in [False, True]:
        launch = root / ("locked" if locked else "original")
        launch.mkdir()
        env, bus = private_environment(
            launch, os.environ.copy(), resources / "fonts.conf"
        )
        for key in list(env):
            if key.startswith("JOPLIN_PURIFIER_"):
                env.pop(key)
        env.update(
            JOPLIN_PURIFIER_SCRIPT=str(script),
            JOPLIN_PURIFIER_STATUS=str(launch / "status"),
            JOPLIN_PURIFIER_ERROR=str(launch / "error"),
            PROBE_RESULT=str(launch / "result"),
            PROBE_INPUT=str(markdown),
            EXPECT_AMBIENT="no" if locked else "yes",
            TEST_PROFILE=str(launch / "profile"),
        )
        if locked:
            env["JOPLIN_PURIFIER_ENVIRONMENT"] = str(environment)
        with (launch / "application.log").open("w") as log:
            # session() inherits stdout; capture the child through a small worker.
            worker = root / "worker.py"
            worker.write_text(
                "import json,sys;sys.path.insert(0,sys.argv[1]);"
                "from joplin_purifier_session import session;"
                "v=json.load(open(sys.argv[2]));"
                "raise SystemExit(session(**v))"
            )
            request = launch / "request.json"
            request.write_text(
                json.dumps(
                    {
                        "arguments": [
                            str(sdk / "bin/joplin-desktop"),
                            "--ozone-platform=x11",
                            "--disable-gpu",
                            "--profile",
                            str(launch / "profile"),
                            "--dev-plugins",
                            str(plugin),
                        ],
                        "env": env,
                        "bus": str(bus),
                        "xvfb": str(xvfb),
                        "dbus": str(resources),
                    }
                )
            )
            result = subprocess.run(
                [sys.executable, worker, source / "native", request],
                check=False,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=150,
            )
        assert result.returncode == 0, (launch / "application.log").read_text()
        assert (launch / "status").read_text() == "0", (
            (launch / "error").read_text()
            + "\n"
            + "\n".join(
                p.read_text(errors="replace")[-16000:]
                for p in (launch / "profile").glob("log*.txt")
            )
        )
        assert (launch / "result").read_text() == "passed"

    hold = root / "hold.cjs"
    ready, stop = root / "ready", root / "stop"
    hold.write_text("""
const fs=require('fs');
module.exports=async()=>{
 fs.writeFileSync(process.env.TEST_READY,'ready');
 while(!fs.existsSync(process.env.TEST_STOP))await new Promise(r=>setTimeout(r,50));
};
""")
    job = json.loads(request.read_text())
    job["env"].update(
        JOPLIN_PURIFIER_SCRIPT=str(hold), TEST_READY=str(ready), TEST_STOP=str(stop)
    )
    request.write_text(json.dumps(job))
    command = [sys.executable, worker, source / "native", request]
    with (root / "held.log").open("w") as log:
        first = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 100
            while not ready.exists():
                assert first.poll() is None and time.monotonic() < deadline, (
                    root / "held.log"
                ).read_text()
                time.sleep(0.05)
            lock = launch / "profile/lock"
            assert lock.exists()
            second_env, second_bus = private_environment(
                root / "second-launch", job["env"], resources / "fonts.conf"
            )
            second_job = job | {"env": second_env, "bus": str(second_bus)}
            second_request = root / "second-request.json"
            second_request.write_text(json.dumps(second_job))
            second = subprocess.run(
                [sys.executable, worker, source / "native", second_request],
                check=False,
                capture_output=True,
                text=True,
                timeout=45,
            )
            assert second.returncode == 1, second.stdout + second.stderr
            assert "profile already in use" in second.stdout + second.stderr
            assert first.poll() is None and lock.exists()
            stop.write_text("stop")
            assert first.wait(timeout=45) == 0, (root / "held.log").read_text()
        finally:
            if first.poll() is None:
                stop.write_text("stop")
                children = Path(f"/proc/{first.pid}/task/{first.pid}/children")
                if children.exists():
                    for child in children.read_text().split():
                        try:
                            os.killpg(int(child), signal.SIGTERM)
                        except ProcessLookupError:
                            pass
                first.terminate()
                first.wait(timeout=10)
print(
    "Native development paths, independent Markdown import and profile exclusion pass"
)
