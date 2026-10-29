"""Dialogs: the in-playback speed menu, series/library management and the context menu."""

import xbmc
import xbmcgui

from . import media, tempo
from .kodiutils import (PROP_DECIDED, addon, format_speed, home_window, library_key,
                        library_store, load_preferences, localize, log, notify, rpc,
                        save_global_default, series_store, settings, tempo_limits)
from .resolver import LIBRARY_TAG


def choose_speed(heading, current=None, extra=()):
    """Pick a speed among those Kodi accepts.

    Returns the speed, "extra:N" when the Nth `extra` entry was picked, or None.
    """
    choices = tempo_limits().choices()
    labels = []
    for speed in choices:
        label = format_speed(speed)
        if current is not None and abs(speed - current) < 0.005:
            label = localize(32118, label)
        labels.append(label)
    labels.extend(extra)
    preselect = -1
    if current is not None:
        preselect = min(range(len(choices)), key=lambda i: abs(choices[i] - current))
    index = xbmcgui.Dialog().select(heading, labels, preselect=preselect)
    if index < 0:
        return None
    if index >= len(choices):
        return "extra:{}".format(index - len(choices))
    return choices[index]


def library_label(rule):
    return localize(32140 if rule.kind == LIBRARY_TAG else 32141, rule.label)


def save_library_default(rule, speed):
    library_store().set(library_key(rule.kind, rule.match), speed,
                        kind=rule.kind, match=rule.match, label=rule.label)


def playback_menu():
    player = xbmc.Player()
    info = media.from_player(player)
    if info is None:
        main_menu()
        return
    heading = localize(32100)
    if info.series_title:
        heading = "{} · {}".format(heading, info.series_title)
    speed = choose_speed(heading, tempo.current_speed())
    if speed is None:
        return
    if abs(speed - 1.0) >= 0.005 and not tempo.ensure_possible(settings()):
        return
    if not tempo.apply(speed):
        notify(localize(32119, format_speed(speed)), xbmcgui.NOTIFICATION_WARNING)
        return

    # Whatever is picked next, the user has decided: the service must not ask on stop.
    home_window().setProperty(PROP_DECIDED, info.path)

    targets = [(None, None, localize(32102))]
    if info.series_title:
        targets.append(("series", None, localize(32103, info.series_title)))
    for rule in media.library_candidates(info):
        targets.append(("library", rule, localize(32142, library_label(rule))))
    targets.append(("global", None, localize(32107)))
    index = xbmcgui.Dialog().select(localize(32101, format_speed(speed)),
                                    [label for _, _, label in targets])
    if index <= 0:
        return
    target, detail, label = targets[index]
    if target == "series":
        series_store().set(info.series_title, speed)
    elif target == "library":
        save_library_default(detail, speed)
    elif not save_global_default(speed):
        notify(localize(32122), xbmcgui.NOTIFICATION_ERROR, 6000)
        return
    log("Saved {:.2f} as default for {}".format(speed, label))
    notify(localize(32115, format_speed(speed), label))


def default_dialog(store, name, display, **extra):
    """Set or remove the stored default `name`, shown to the user as `display`.

    `extra` is stored with the entry (library defaults keep their own "label" there).
    """
    current = store.get(name)
    remove = [localize(32110)] if current is not None else []
    choice = choose_speed(localize(32116, display), current, remove)
    if choice is None:
        return
    if choice == "extra:0":
        store.remove(name)
        notify(localize(32120, display))
        return
    store.set(name, choice, **extra)
    notify(localize(32115, format_speed(choice), display))


def series_default_dialog(title):
    default_dialog(series_store(), title, title)


def library_default_dialog(rule):
    default_dialog(library_store(), library_key(rule.kind, rule.match), library_label(rule),
                   kind=rule.kind, match=rule.match, label=rule.label)


def pick_series_title():
    result = rpc("VideoLibrary.GetTVShows", properties=["title"],
                 sort={"method": "title", "ignorearticle": True})
    shows = [show["title"] for show in (result or {}).get("tvshows", [])]
    labels = [localize(32128)] + shows
    index = xbmcgui.Dialog().select(localize(32111), labels)
    if index < 0:
        return None
    if index == 0:
        title = xbmcgui.Dialog().input(localize(32129)).strip()
        return title or None
    return shows[index - 1]


def manage_series():
    while True:
        entries = series_store().all()
        labels = [localize(32111)]
        labels += ["{} · {}".format(e["name"], format_speed(e["speed"])) for e in entries]
        index = xbmcgui.Dialog().select(localize(32130), labels)
        if index < 0:
            return
        title = pick_series_title() if index == 0 else entries[index - 1]["name"]
        if title:
            series_default_dialog(title)


def pick_library():
    candidates = media.library_candidates()
    if not candidates:
        notify(localize(32144))
        return None
    index = xbmcgui.Dialog().select(localize(32143), [library_label(c) for c in candidates])
    return candidates[index] if index >= 0 else None


def manage_libraries():
    while True:
        rules = load_preferences().libraries
        labels = [localize(32143)]
        labels += ["{} · {}".format(library_label(r), format_speed(r.speed)) for r in rules]
        index = xbmcgui.Dialog().select(localize(32145), labels)
        if index < 0:
            return
        rule = pick_library() if index == 0 else rules[index - 1]
        if rule:
            library_default_dialog(rule)


def main_menu():
    entries = [(localize(32130), manage_series), (localize(32145), manage_libraries)]
    index = xbmcgui.Dialog().select(addon().getAddonInfo("name"), [label for label, _ in entries])
    if index >= 0:
        entries[index][1]()


def run_script(args):
    command = args[0] if args else ""
    if command == "series":
        manage_series()
    elif command == "libraries":
        manage_libraries()
    elif command == "menu" or xbmc.Player().isPlayingVideo():
        playback_menu()
    else:
        main_menu()


def run_context(listitem):
    title = media.series_title_from_listitem(listitem)
    if title:
        series_default_dialog(title)
