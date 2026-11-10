{
  lib,
  purifier,
  runCommand,
  python3,
  lockedSdk,
  xvfb-run,
  dbus,
  environment,
  readLock,
  fontConfig,
  gnutar,
  gzip,
}:
{
  src,
  lockFile ? src + "/joplin-purifier.lock.json",
  script ? "build.cjs",
  fetchers ? { },
  doCheck ? false,
  checkCommand ? "",
  resourceRoots ? { },
  resourceDependencies ? [ ],
}:
let
  lock = readLock { inherit src lockFile; };
  profile = environment { inherit lock fetchers; };
  driver = lib.fileset.toSource {
    root = ../native;
    fileset = lib.fileset.unions [
      ../native/joplin_purifier_run_project.py
      ../native/joplin_purifier_session.py
    ];
  };
  projectSource = lib.cleanSourceWith {
    inherit src;
    filter =
      path: type:
      !(builtins.elem (baseNameOf path) [
        ".git"
        ".joplin-purifier"
        "__pycache__"
        "result"
        "output"
      ]);
  };
  builtProject = runCommand "joplin-project" { } ''
    export JOPLIN_PURIFIER_ENVIRONMENT=${profile} JOPLIN_PURIFIER_SDK_PATH=${lockedSdk}
    export JOPLIN_PURIFIER_FONTS=${fontConfig}
    export JOPLIN_PURIFIER_XVFB=${xvfb-run} JOPLIN_PURIFIER_DBUS=${lib.getBin dbus}
    export JOPLIN_PURIFIER_OUTPUT="$out" JOPLIN_PURIFIER_STATE="$TMPDIR/joplin-run"
    mkdir -p "$out"
    cp -r ${projectSource} project
    chmod -R u+w project
    cd project
    export JOPLIN_PURIFIER_PROJECT="$PWD" JOPLIN_PURIFIER_SCRIPT="$PWD/"${lib.escapeShellArg script}
    ${python3}/bin/python ${driver}/joplin_purifier_run_project.py
    ${lib.optionalString doCheck checkCommand}
  '';
  projections = lib.optionalAttrs (resourceRoots != { }) (
    purifier.resourceProjections {
      producer = builtProject;
      roots = resourceRoots;
      dependencies = resourceDependencies;
      inherit runCommand python3;
    }
  );
  project = builtProject // {
    inherit projections;
  };
  release =
    runCommand "joplin-project-release"
      {
        nativeBuildInputs = [
          gnutar
          gzip
        ];
      }
      ''
        mkdir -p "$out"
        tar --sort=name --mtime=@1 --owner=0 --group=0 --numeric-owner -cf - -C ${project} . | gzip -n > "$out/joplin-project.tar.gz"
      '';
in
{
  packages = {
    default = project;
    inherit project;
    environment = profile;
  };
  tests = project;
  inherit release projections;
  fetches = lock.entries;
}
