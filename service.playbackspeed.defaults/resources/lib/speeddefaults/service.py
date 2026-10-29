"""Background service: applies the default speed whenever a video starts."""

import time

import xbmc
import xbmcgui

from . import media, tempo
from .kodiutils import (PROP_DECIDED, addon, format_speed, home_window, load_preferences,
                        localize, log, notify, series_store, settings, tempo_limits)
from .resolver import SOURCE_GLOBAL, resolve

# How long to wait after a stop for another video to start before asking
# whether to save a manual speed change.
ASK_GRACE_SECONDS = 2.0


class Session:
    """The video currently playing and the speed the service gave it."""

    def __init__(self, info, applied):
        self.info = info
        self.applied = applied
        self.observed = None


class Player(xbmc.Player):
    # Callbacks only raise flags; the main loop does the work, so that a slow
    # JSON-RPC call or a dialog never blocks Kodi's callback delivery.
    def __init__(self):
        super().__init__()
        self.started = False
        self.stopped = False

    def onAVStarted(self):
        self.started = True

    def onPlayBackStopped(self):
        self.stopped = True

    def onPlayBackEnded(self):
        self.stopped = True

    def onPlayBackError(self):
        self.stopped = True


def source_label(resolution):
    if resolution.source == SOURCE_GLOBAL:
        return localize(32121)
    return resolution.detail


def start_session(player, monitor):
    home_window().clearProperty(PROP_DECIDED)
    info = media.from_player(player)
    if info is None:
        return None
    resolution = resolve(info, load_preferences(), series_store().get(info.series_title))
    if resolution is None:
        return Session(info, None)
    log("Resolved {:.2f} from {} {}".format(resolution.speed, resolution.source, resolution.detail))

    speed = resolution.speed
    current = settings()
    if abs(speed - 1.0) >= 0.005:
        limits = tempo_limits()
        if not limits.is_allowed(speed):
            clamped = limits.clamp(speed)
            notify(localize(32108, format_speed(speed), format_speed(clamped)),
                   xbmcgui.NOTIFICATION_WARNING, 8000)
            speed = clamped
        if not tempo.ensure_possible(current):
            return Session(info, 1.0)

    # Applied even for 1.0x, in case the player kept the previous video's tempo.
    if not tempo.apply(speed, monitor):
        return Session(info, 1.0)
    if current.getBool("notify_applied") and abs(speed - 1.0) >= 0.005:
        notify("{} · {}".format(format_speed(speed), source_label(resolution)))
    return Session(info, speed)


def should_offer_save(session):
    if session is None or session.applied is None or session.observed is None:
        return False
    if not session.info.series_title:
        return False
    if not settings().getBool("ask_save_on_stop"):
        return False
    if home_window().getProperty(PROP_DECIDED) == session.info.path:
        return False
    if abs(session.observed - session.applied) < 0.005:
        return False
    stored = series_store().get(session.info.series_title)
    return stored is None or abs(stored - session.observed) >= 0.005


def offer_save(finished, current, monitor):
    title, speed = finished.info.series_title, finished.observed
    if not xbmcgui.Dialog().yesno(addon().getAddonInfo("name"),
                                  localize(32114, title, format_speed(speed)),
                                  autoclose=15000):
        return
    series_store().set(title, speed)
    notify(localize(32115, format_speed(speed), title))
    # The next episode of the same show may already be playing at the old default.
    if current is not None and current.info.series_title.casefold() == title.casefold():
        if tempo.apply(speed, monitor):
            current.applied = speed


def run():
    monitor = xbmc.Monitor()
    player = Player()
    session = None
    pending = None  # (finished session, time to ask at)
    log("Service started")

    while not monitor.abortRequested():
        if player.stopped or (player.started and session is not None):
            player.stopped = False
            if should_offer_save(session):
                pending = (session, time.monotonic() + ASK_GRACE_SECONDS)
            session = None

        if player.started:
            player.started = False
            session = start_session(player, monitor)

        if session is not None:
            speed = tempo.current_speed()
            if speed is not None:
                session.observed = speed

        if pending is not None and (session is not None or time.monotonic() >= pending[1]):
            finished, pending = pending[0], None
            offer_save(finished, session, monitor)

        if monitor.waitForAbort(0.5):
            break

    log("Service stopped")
