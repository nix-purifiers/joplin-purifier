{
  lib,
  runCommand,
  original,
  asar,
  python3,
}:
let
  driver = lib.fileset.toSource {
    root = ../native;
    fileset = lib.fileset.unions [
      ../native/patch_sdk.py
      ../native/guard.js
    ];
  };
in
runCommand "joplin-locked-sdk"
  {
    nativeBuildInputs = [
      asar
      python3
    ];
  }
  ''
    cp -r ${original}/. "$out"
    chmod -R u+w "$out"
    asar extract ${original}/share/joplin-desktop/resources/app.asar app-tree
    cp ${driver}/guard.js guard.js
    cp ${driver}/patch_sdk.py patch_sdk.py
    python patch_sdk.py
    rm "$out/share/joplin-desktop/resources/app.asar"
    rm -r "$out/share/joplin-desktop/resources/app.asar.unpacked"
    asar pack app-tree "$out/share/joplin-desktop/resources/app.asar" --unpack-dir node_modules
    substituteInPlace "$out/bin/joplin-desktop" --replace-fail ${original} "$out"
  ''
