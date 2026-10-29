import json
import os

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from .defaults import parse_setting_defaults
from .limits import TempoLimits, parse_max_tempo
from .resolver import LIBRARY_TAG, LibraryRule, Preferences
from .store import SpeedStore

ADDON_ID = "service.playbackspeed.defaults"

# Home window property the script sets when the user already chose what to do
# with a manual speed change, so the service does not ask again on stop.
PROP_DECIDED = ADDON_ID + ".decided"

def addon():
    # A fresh instance each time, so settings changed in the GUI are picked up.
    return xbmcaddon.Addon(ADDON_ID)


_setting_defaults = None
_warned_unreadable_settings = False


def setting_defaults():
    global _setting_defaults
    if _setting_defaults is None:
        path = os.path.join(xbmcvfs.translatePath(addon().getAddonInfo("path")),
                            "resources", "settings.xml")
        with open(path, "r", encoding="utf-8") as f:
            _setting_defaults = parse_setting_defaults(f.read())
    return _setting_defaults


def _warn_unreadable_settings(error):
    # Logged directly: log() reads a setting itself.
    global _warned_unreadable_settings
    if _warned_unreadable_settings:
        return
    _warned_unreadable_settings = True
    xbmc.log("[{}] Kodi could not load this add-on's settings ({}), using the defaults. If "
             "userdata/addon_data/{}/settings.xml is empty or corrupt, delete it."
             .format(ADDON_ID, error, ADDON_ID), xbmc.LOGWARNING)


class Settings:
    """The add-on's settings, falling back to the defaults when Kodi cannot load them.

    Kodi refuses every read when the user's settings.xml exists but does not parse (e.g. an
    empty file left by an unclean shutdown), instead of using the defaults as it does when the
    file is missing.
    """

    def __init__(self):
        self._settings = addon().getSettings()

    def _get(self, getter, setting_id):
        try:
            return getter(setting_id)
        except (TypeError, RuntimeError) as error:
            _warn_unreadable_settings(error)
            return setting_defaults()[setting_id]

    def getBool(self, setting_id):
        return self._get(self._settings.getBool, setting_id)

    def getNumber(self, setting_id):
        return self._get(self._settings.getNumber, setting_id)

    def setNumber(self, setting_id, value):
        """Returns False when Kodi refused to store the value."""
        try:
            self._settings.setNumber(setting_id, value)
            return True
        except (TypeError, RuntimeError) as error:
            _warn_unreadable_settings(error)
            return False


def settings():
    # Fresh each time, like addon(), so changes made in the GUI are picked up.
    return Settings()


def localize(string_id, *args):
    text = addon().getLocalizedString(string_id)
    return text.format(*args) if args else text


def log(msg, level=xbmc.LOGDEBUG):
    if level == xbmc.LOGDEBUG and settings().getBool("debug"):
        level = xbmc.LOGINFO
    xbmc.log("[{}] {}".format(ADDON_ID, msg), level)


def notify(msg, icon=xbmcgui.NOTIFICATION_INFO, ms=3000):
    xbmcgui.Dialog().notification(addon().getAddonInfo("name"), msg, icon, ms)


def rpc(method, **params):
    request = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    response = json.loads(xbmc.executeJSONRPC(json.dumps(request)))
    if "error" in response:
        log("JSON-RPC {} failed: {}".format(method, response["error"]), xbmc.LOGWARNING)
        return None
    return response.get("result")


def format_speed(speed):
    return localize(32040).format(speed)


def kodi_major():
    version = xbmc.getInfoLabel("System.BuildVersion")
    try:
        return int(version.split(".", 1)[0])
    except ValueError:
        return 21


def tempo_limits():
    path = xbmcvfs.translatePath("special://masterprofile/advancedsettings.xml")
    try:
        with open(path, "r", encoding="utf-8") as f:
            max_tempo = parse_max_tempo(f.read())
    except OSError:
        max_tempo = None
    return TempoLimits(kodi_major(), max_tempo)


def _store(filename):
    profile = xbmcvfs.translatePath(addon().getAddonInfo("profile"))
    return SpeedStore(os.path.join(profile, filename))


def series_store():
    return _store("series.json")


def library_store():
    """Library defaults, named "<kind>:<match>" with kind/match/label extras."""
    return _store("libraries.json")


def library_key(kind, match):
    return "{}:{}".format(kind, match)


def library_rules():
    rules = [LibraryRule(e["kind"], e["match"], float(e["speed"]), e.get("label") or e["match"])
             for e in library_store().all() if e.get("kind") and e.get("match")]
    # Tags first: a Jellyfin library tag is more specific than the source path
    # its files may share with other libraries.
    return sorted(rules, key=lambda r: (r.kind != LIBRARY_TAG, r.label.casefold()))


def load_preferences():
    current = settings()
    return Preferences(
        enabled=current.getBool("enabled"),
        global_speed=round(current.getNumber("global_speed"), 2),
        libraries=library_rules(),
    )


def save_global_default(speed):
    """Returns False when Kodi refused to store it."""
    return settings().setNumber("global_speed", speed)


def home_window():
    return xbmcgui.Window(10000)
