{
  inputs = {
    nixpkgs.url = "nixpkgs/nixpkgs-unstable";
    systems.url = "github:nix-systems/default";
    flake-parts.url = "github:hercules-ci/flake-parts";
    flake-parts.inputs.nixpkgs-lib.follows = "nixpkgs";
  };

  outputs =
    inputs@{ flake-parts, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = import inputs.systems;

      # Unbuilt package function, for `kodi.withPackages (p: [ (p.callPackage ...) ])`.
      flake.kodiAddons.default = ./nix/package.nix;

      perSystem =
        {
          pkgs,
          self',
          ...
        }:
        {
          # Built against the default `kodi`. For another variant (kodi-wayland,
          # kodi-gbm, ...) call `kodiAddons.default` with that variant's
          # packages.callPackage, so the add-on matches the Kodi it runs in.
          packages.default = pkgs.kodiPackages.callPackage ./nix/package.nix { };

          checks.unit-tests = pkgs.runCommand "playbackspeed-defaults-tests" { } ''
            cd ${./.}
            PYTHONDONTWRITEBYTECODE=1 ${pkgs.python3.interpreter} -m unittest discover -s tests
            touch $out
          '';

          # Undefined names and unused imports. Most of the add-on only runs
          # inside Kodi, so this is the only check that sees all of it.
          checks.pyflakes = pkgs.runCommand "playbackspeed-defaults-pyflakes" { } ''
            ${pkgs.python3Packages.pyflakes}/bin/pyflakes ${./service.playbackspeed.defaults} ${./tests}
            touch $out
          '';

          # Team Kodi's static checker for repository submissions; not in nixpkgs.
          packages.kodi-addon-checker = pkgs.python3Packages.buildPythonApplication rec {
            pname = "kodi-addon-checker";
            version = "0.0.36";
            pyproject = true;
            src = pkgs.fetchPypi {
              pname = "kodi_addon_checker";
              inherit version;
              hash = "sha256-Z7YdzKIkxlc8XkQjJFza9KItdKofLYuafrvtrC6YLWA=";
            };
            build-system = [ pkgs.python3Packages.setuptools ];
            dependencies = with pkgs.python3Packages; [
              packaging
              pillow
              polib
              requests
              radon
              urllib3
              xmlschema
            ];
            pythonImportsCheck = [ "kodi_addon_checker" ];
          };

          devShells.default = pkgs.mkShell {
            packages = [
              pkgs.python3
              pkgs.python3Packages.pyflakes
              self'.packages.kodi-addon-checker
            ];
            # kodi-addon-checker byte-compiles every file and then flags the
            # __pycache__ it left behind.
            PYTHONDONTWRITEBYTECODE = "1";
          };

          formatter = pkgs.nixfmt;
        };
    };
}
