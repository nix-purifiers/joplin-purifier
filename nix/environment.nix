{
  lib,
  runCommand,
  writeText,
  fetchurl,
  fetchgit,
  python3,
  original,
  lockedSdk,
  purifier,
  sdk,
  electron,
  fontConfig,
  xvfb-run,
  dbus,
}:
{
  lock,
  fetchers ? { },
}:
let
  checked = purifier.checkLock lock;
  archives = purifier.tree (
    {
      name = "joplin-plugin-archives";
      entries = checked.entries;
      inherit
        runCommand
        writeText
        fetchurl
        fetchgit
        python3
        ;
    }
    // fetchers
  );
  request = writeText "joplin-native-install.json" (
    builtins.toJSON {
      action = "install";
      entries = checked.entries;
      metadata = checked.data.native.metadata;
      archives = builtins.listToAttrs (
        map (entry: {
          name = entry.path;
          value = "${archives}/${entry.path}";
        }) checked.entries
      );
    }
  );
  driver = lib.fileset.toSource {
    root = ../native;
    fileset = lib.fileset.unions [
      ../native/joplin_purifier_helper.py
      ../native/joplin_purifier_session.py
      ../native/native.cjs
      ../native/helper-main.cjs
      ../native/job.cjs
      ../native/validate_archive.py
    ];
  };
  manifest = writeText "joplin-lock.json" (builtins.toJSON checked.data);
in
assert lib.assertMsg (
  checked.data.sdk == sdk
) "Joplin SDK changed; run joplin-purifier lock --update";
runCommand "joplin-locked-plugins" { } ''
  mkdir -p "$out"
  export JOPLIN_PURIFIER_ORIGINAL=${original} JOPLIN_PURIFIER_PYTHON=${python3}/bin/python3
  export JOPLIN_PURIFIER_ELECTRON=${electron} JOPLIN_PURIFIER_FONTS=${fontConfig}
  export JOPLIN_PURIFIER_XVFB=${xvfb-run} JOPLIN_PURIFIER_DBUS=${lib.getBin dbus}
  ${python3}/bin/python3 -c 'import json,sys;from pathlib import Path;p=Path(sys.argv[1]);v=json.loads(p.read_text());v["output"]=sys.argv[2];Path(sys.argv[3]).write_text(json.dumps(v))' ${request} "$out" "$TMPDIR/request.json"
  ${python3}/bin/python3 ${driver}/joplin_purifier_helper.py "$TMPDIR/session" "$TMPDIR/request.json" "$TMPDIR/response.json" > "$TMPDIR/helper.log" 2>&1 || { cat "$TMPDIR/helper.log"; exit 1; }
  ln -s ${archives} "$out/archives"
  ln -s ${lockedSdk} "$out/sdk"
  ln -s ${manifest} "$out/lock.json"
''
