import xbmc
import xbmcgui

from .kodiutils import localize, log, notify, rpc

SYNC_TO_DISPLAY = "videoplayer.usedisplayasclock"


def current_speed():
    """Current tempo of the playing video, or None while paused/seeking/stopped."""
    if not xbmc.Player().isPlayingVideo():
        return None
    if xbmc.getCondVisibility("Player.Paused | Player.Forwarding | Player.Rewinding"):
        return None
    # Player.PlaySpeed reports the tempo when the play speed is normal.
    try:
        return round(float(xbmc.getInfoLabel("Player.PlaySpeed")), 2)
    except ValueError:
        return None


def sync_to_display_enabled():
    result = rpc("Settings.GetSettingValue", setting=SYNC_TO_DISPLAY)
    return bool(result and result.get("value"))


def enable_sync_to_display():
    log("Enabling 'Sync playback to display'")
    rpc("Settings.SetSettingValue", setting=SYNC_TO_DISPLAY, value=True)


def ensure_possible(settings):
    """Make sure Kodi can change the tempo, enabling sync to display if allowed."""
    if sync_to_display_enabled():
        return True
    if settings.getBool("auto_sync_display"):
        enable_sync_to_display()
        return True
    notify(localize(32109), xbmcgui.NOTIFICATION_WARNING, 6000)
    return False


def apply(speed, monitor=None, timeout=5.0):
    """Set the tempo and wait until Kodi reports it. Returns True on success.

    Kodi ignores the request while paused or before the player can tempo, so
    keep retrying until the deadline.
    """
    monitor = monitor or xbmc.Monitor()
    command = "PlayerControl(Tempo({:.2f}))".format(speed)
    interval = 0.25
    waited = 0.0
    while waited < timeout:
        if not xbmc.Player().isPlayingVideo():
            return False
        current = current_speed()
        if current is not None and abs(current - speed) < 0.005:
            log("Speed is now {:.2f}".format(speed))
            return True
        if current is not None:
            xbmc.executebuiltin(command)
        if monitor.waitForAbort(interval):
            return False
        waited += interval
    log("Kodi did not accept speed {:.2f}".format(speed), xbmc.LOGWARNING)
    return False
