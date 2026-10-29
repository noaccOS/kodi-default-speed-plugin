# Playback Speed Defaults (Kodi add-on)

`service.playbackspeed.defaults` sets the playback speed when a video starts, using the most
specific default available:

1. **Series default** (One Piece, Game of Thrones, …)
2. **Library default** (e.g. separate *Anime* and *TV Shows* libraries in Jellyfin)
3. **Global default**

A level without a default falls through to the next, so a library with no default of its own uses
the global default.

Changing the speed while an episode plays affects only that episode. The next video starts at its
default again.

Works on Kodi 21 (Omega) and Kodi 22 (Piers). It needs `xbmc.python` ABI 3.0.0, which both still
provide.

## Requirements

- **Sync playback to display** (Settings → Player → Videos) must be on, or Kodi ignores speed
  changes. By default the add-on turns it on for you (setting *Automatically enable "Sync playback
  to display"*).
- **Speeds above 1.5x** need `maxtempo` in `userdata/advancedsettings.xml`:

  ```xml
  <advancedsettings>
    <video>
      <maxtempo>2.1</maxtempo>
    </video>
  </advancedsettings>
  ```

  `2.1` is the value that gives **2.0x on both versions**. Kodi 21 treats the limit as exclusive and
  accepts up to 2.1 (`2.0` there would stop at 1.95x). Kodi 22 treats the limit as inclusive and caps
  it at 2.0. The add-on reads this file and only offers speeds Kodi will accept. If a saved default is
  above the limit, the fastest allowed speed is used and a notification says so.

## Installing on NixOS

The flake exports the package function as `kodiAddons.default` (same shape as the add-ons in
nixpkgs' `pkgs/applications/video/kodi/addons`). Call it with the package set of the Kodi variant
you run, so it is built for that Kodi:

```nix
# flake.nix of your config
inputs.playbackspeed-defaults.url = "git+file:///home/noaccos/src/kodi-default-speed-plugin";

# wherever Kodi is installed
services.xserver.desktopManager.kodi.package = pkgs.kodi.withPackages (p: [
  p.jellyfin
  (p.callPackage inputs.playbackspeed-defaults.kodiAddons.default { })
]);
```

Swap `pkgs.kodi` for `kodi-wayland` / `kodi-gbm` as needed. `packages.<system>.default` is the same
add-on built against plain `pkgs.kodi`. Kodi installs add-ons from the Nix store disabled, so enable
it once under Add-ons → My add-ons → Services. Settings and the JSON files stay in
`userdata/addon_data` as usual. `maxtempo` still goes in `advancedsettings.xml` yourself (or via
home-manager).

## Using it

| What | How |
| --- | --- |
| Global default | Add-on settings |
| Library defaults (e.g. your Jellyfin *Anime* library) | Add-on settings → Libraries → *Manage library defaults…* |
| Series default from the library | Context menu on a TV show, season or episode → *Default playback speed…* |
| List, edit or remove series defaults | Add-on settings → Series → *Manage series defaults…* |
| Change speed for the current episode | Run the add-on while a video plays (or bind a key, below). Pick a speed, then optionally *also save it* as the series, library or global default |
| Keep a manual change for the whole series | Change speed any way you like (this menu or Kodi's own tempo keys). On stop the add-on offers to save it as the series default (can be turned off) |

### Keymap for the in-playback menu

`userdata/keymaps/playbackspeed.xml`:

```xml
<keymap>
  <FullscreenVideo>
    <keyboard>
      <s mod="ctrl">RunScript(service.playbackspeed.defaults,menu)</s>
    </keyboard>
  </FullscreenVideo>
</keymap>
```

## Library defaults

Kodi has no notion of "libraries" beyond content types, so a library is matched in one of two ways:

- **Library tag.** Jellyfin for Kodi adds the Jellyfin library name as a tag to every TV show and
  movie it syncs (`jellyfin_kodi/objects/tvshows.py`, `movies.py`). Playback from the Kodi library
  keeps the Kodi library id, so the add-on can read the show's tags in both add-on and native/direct
  path mode. Any other tag works the same way.
- **Kodi source.** The playing file's path starts with the source's path. For plain Kodi sources
  (and Jellyfin in direct-path mode).

*Manage library defaults…* lists all library tags and video sources to pick from. If a video matches
several libraries, tags win over sources, then alphabetical order.

Limitation: videos browsed and played through the Jellyfin add-on's own menus (not the Kodi
library) carry no Kodi library id, so their library tag can't be looked up. Series and global
defaults still apply to them.

## Design notes

- The speed is set with `PlayerControl(Tempo(x))` (absolute, available since Kodi 19). It does not
  step with `TempoUp`/`TempoDown` from an assumed 1.0x. The service re-reads `Player.PlaySpeed`
  until Kodi reports the new speed, because Kodi ignores the request while paused or before the
  player is ready.
- Series defaults live in `addon_data/service.playbackspeed.defaults/series.json`, keyed by the
  show title (case and whitespace insensitive) rather than a library id. They survive library
  rebuilds and also work for episodes from plugins that set a show title. The downside: two shows
  with exactly the same title share a default.
- Player callbacks only set flags. JSON-RPC lookups, retries and dialogs run in the service loop, so
  Kodi's callback delivery is never blocked.

## Development

```sh
nix develop --command python3 -m unittest discover -s tests
nix flake check  # unit tests in the sandbox
nix build        # the packaged add-on, under result/share/kodi/addons

# Team Kodi's repository checker (addon.xml schema, dependency versions, language files, …)
nix develop --command kodi-addon-checker --branch omega service.playbackspeed.defaults  # Kodi 21
nix develop --command kodi-addon-checker --branch piers service.playbackspeed.defaults  # Kodi 22
```

The checker downloads Kodi's repository index for the chosen branch, so it needs network access.

The tests cover the pure modules (`limits`, `resolver`, `store`). The Kodi glue (`service`, `ui`,
`media`, `tempo`, `kodiutils`) has to be tested inside Kodi. To install, zip the
`service.playbackspeed.defaults` directory and use *Install from zip file*.
