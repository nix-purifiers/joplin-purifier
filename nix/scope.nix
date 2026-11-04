{
  pkgs,
  nixpkgsSrc,
  purifierSrc,
}:
pkgs.lib.makeScope pkgs.newScope (scope: {
  original = pkgs.joplin-desktop;
  lockedSdk = scope.callPackage ./sdk.nix { };
  purifier = import (purifierSrc + "/nix/lib") { inherit (pkgs) lib; };
  readLock = import ./read-lock.nix { inherit (pkgs) lib; };
  environment = scope.callPackage ./environment.nix { };
  cli = scope.callPackage ./cli.nix { inherit nixpkgsSrc purifierSrc; };
  buildJoplinProject = scope.callPackage ./build-project.nix { };
  fontConfig = pkgs.makeFontsConf {
    fontDirectories = [
      pkgs.dejavu_fonts
      pkgs.noto-fonts
    ];
  };
  sdk = builtins.hashString "sha256" (
    builtins.toJSON {
      nixpkgs = toString nixpkgsSrc;
      native = builtins.listToAttrs (
        map
          (path: {
            name = pkgs.lib.removePrefix (toString ../native + "/") (toString path);
            value = builtins.hashFile "sha256" path;
          })
          (
            builtins.filter (
              path:
              builtins.any (ext: pkgs.lib.hasSuffix ext (toString path)) [
                ".py"
                ".cjs"
                ".js"
              ]
            ) (pkgs.lib.filesystem.listFilesRecursive ../native)
          )
      );
      providers = pkgs.lib.genAttrs [ "scope.nix" "environment.nix" "sdk.nix" ] (
        name: builtins.hashFile "sha256" ((./. + ("/" + name)))
      );
    }
  );
})
