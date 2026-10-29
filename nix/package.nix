# Call with the callPackage of the Kodi package set you run, e.g.
# `kodi-wayland.packages.callPackage ./nix/package.nix { }`, or inside
# `kodi.withPackages (p: [ (p.callPackage ./nix/package.nix { }) ])`.
{
  lib,
  buildKodiAddon,
}:

let
  addonDir = ../service.playbackspeed.defaults;
  # addon.xml is the single source of truth for the version.
  version = lib.head (
    builtins.match ".*<addon [^>]*version=\"([^\"]+)\".*" (builtins.readFile (addonDir + "/addon.xml"))
  );
in
buildKodiAddon {
  pname = "playbackspeed-defaults";
  namespace = "service.playbackspeed.defaults";
  inherit version;

  src = lib.fileset.toSource {
    root = addonDir;
    fileset = addonDir;
  };

  meta = {
    description = "Kodi add-on that sets the default playback speed per series, library or globally";
    license = lib.licenses.mit;
    platforms = lib.platforms.all;
  };
}
