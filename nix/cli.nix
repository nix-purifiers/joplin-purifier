{
  lib,
  runCommand,
  writeText,
  makeWrapper,
  python3,
  original,
  lockedSdk,
  electron,
  xvfb-run,
  dbus,
  sdk,
  fontConfig,
  nix,
  gh,
  cacert,
  nixpkgsSrc,
  purifierSrc,
}:
let
  integration = lib.fileset.toSource {
    root = ../.;
    fileset = lib.fileset.unions [
      (lib.fileset.fileFilter (file: file.hasExt "py") ../joplin_purifier)
      (lib.fileset.fileFilter (
        file:
        builtins.any file.hasExt [
          "py"
          "cjs"
          "js"
        ]
      ) ../native)
      (lib.fileset.fileFilter (file: file.hasExt "nix") ./.)
    ];
  };
  bootstrap = writeText "joplin-purifier-main.py" "import os,runpy,sys; sys.path.insert(0, ${builtins.toJSON integration}); sys.argv[0]=os.environ['JOPLIN_PURIFIER_COMMAND']; runpy.run_module('joplin_purifier.main',run_name='__main__')";
  realize = writeText "joplin-purifier-realize.nix" ''
    { lockPath, projectPath, target ? "environment" }:
    let
      pkgs = import (builtins.storePath "${nixpkgsSrc}") {};
      scope = import ${integration}/nix/scope.nix {
        inherit pkgs;
        nixpkgsSrc = builtins.storePath "${nixpkgsSrc}";
        purifierSrc = builtins.storePath "${purifierSrc}";
      };
      lockFile = builtins.toPath lockPath;
      src = if target == "environment" then builtins.toPath projectPath else builtins.path {
        path = builtins.toPath projectPath;
        name = "joplin-project";
        filter = path: type: !(builtins.elem (baseNameOf path) [ ".git" ".joplin-purifier" "__pycache__" "result" "output" ]);
      };
      build = scope.buildJoplinProject { inherit src lockFile; };
    in if target == "environment" then scope.environment { lock = scope.readLock { inherit src lockFile; }; }
       else if target == "project" then build.packages.project
       else if target == "release" then build.release
       else throw "Unknown JOPLIN purifier target"
  '';
in
runCommand "joplin-purifier" { nativeBuildInputs = [ makeWrapper ]; } ''
  mkdir -p "$out/bin"
  for name in joplin-purifier joplin-desktop; do
    makeWrapper ${python3}/bin/python "$out/bin/$name" \
      --add-flags ${bootstrap} \
      --set JOPLIN_PURIFIER_COMMAND "$name" \
      --set JOPLIN_PURIFIER_NATIVE ${integration}/native \
      --set JOPLIN_PURIFIER_ORIGINAL ${original} \
      --set JOPLIN_PURIFIER_SDK_PATH ${lockedSdk} \
      --set JOPLIN_PURIFIER_ELECTRON ${electron} \
      --set JOPLIN_PURIFIER_PYTHON ${python3}/bin/python3 \
      --set JOPLIN_PURIFIER_XVFB ${xvfb-run} \
      --set JOPLIN_PURIFIER_DBUS ${lib.getBin dbus} \
      --set JOPLIN_PURIFIER_SDK ${sdk} \
      --set JOPLIN_PURIFIER_FONTS ${fontConfig} \
      --set JOPLIN_PURIFIER_REALIZE ${realize} \
      --set-default JOPLIN_PURIFIER_GH ${gh}/bin/gh \
      --set-default SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --set-default NIX_SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --prefix PATH : ${
        lib.makeBinPath [
          nix
          gh
        ]
      }
  done
''
