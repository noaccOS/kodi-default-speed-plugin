"""Decide which default speed applies to a video.

Pure module (no xbmc imports) so it can be unit tested.

Precedence, most specific first:
    series default > library default > global default
"""

from dataclasses import dataclass, field
from typing import List

# A library is matched either by a tag (media servers such as Jellyfin tag each
# synced item with its library name) or by a Kodi source path.
LIBRARY_TAG = "tag"
LIBRARY_PATH = "path"

SOURCE_SERIES = "series"
SOURCE_LIBRARY = "library"
SOURCE_GLOBAL = "global"


@dataclass
class MediaInfo:
    kind: str = "other"  # "movie", "episode" or "other"
    title: str = ""
    series_title: str = ""
    genres: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    path: str = ""


@dataclass
class LibraryRule:
    kind: str  # LIBRARY_TAG or LIBRARY_PATH
    match: str
    speed: float
    label: str = ""

    def matches(self, info):
        if self.kind == LIBRARY_TAG:
            wanted = self.match.strip().casefold()
            return any(tag.strip().casefold() == wanted for tag in info.tags)
        if self.kind == LIBRARY_PATH:
            prefix = normalize_path(self.match)
            if not prefix.endswith("/"):
                prefix += "/"
            return normalize_path(info.path).startswith(prefix)
        return False


@dataclass
class Preferences:
    enabled: bool = True
    global_speed: float = 1.0
    libraries: List[LibraryRule] = field(default_factory=list)


@dataclass
class Resolution:
    speed: float
    source: str
    # Series title or library label the speed came from.
    detail: str = ""


def normalize_path(path):
    return path.replace("\\", "/").casefold()


def matching_libraries(info, rules):
    """Library rules that apply to the video, in configured order."""
    return [rule for rule in rules if rule.matches(info)]


def resolve(info, prefs, series_speed=None):
    """Return the Resolution for `info`, or None when the add-on is disabled.

    `series_speed` is the stored default for info.series_title, if any.
    """
    if not prefs.enabled:
        return None
    if info.series_title and series_speed is not None:
        return Resolution(series_speed, SOURCE_SERIES, info.series_title)
    libraries = matching_libraries(info, prefs.libraries)
    if libraries:
        return Resolution(libraries[0].speed, SOURCE_LIBRARY, libraries[0].label)
    return Resolution(prefs.global_speed, SOURCE_GLOBAL)
