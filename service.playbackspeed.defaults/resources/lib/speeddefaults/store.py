"""Named speed defaults (series, libraries), persisted as JSON in the add-on profile.

Pure module (no xbmc imports) so it can be unit tested.

Series are keyed by their case-folded title rather than by library id, so
defaults survive library rebuilds and also apply to episodes played from
outside the library (plugins, file browsing) that carry a show title.
"""

import json
import os

SCHEMA_VERSION = 1


def normalize_key(name):
    return " ".join(name.split()).casefold()


class SpeedStore:
    """Maps a name to {"name": ..., "speed": ..., **extra}."""

    def __init__(self, path):
        self.path = path

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return {}
        entries = data.get("entries") if isinstance(data, dict) else None
        return entries if isinstance(entries, dict) else {}

    def _save(self, entries):
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"version": SCHEMA_VERSION, "entries": entries}, f, indent=2,
                      ensure_ascii=False, sort_keys=True)
        os.replace(tmp, self.path)

    @staticmethod
    def _valid(entry):
        try:
            return isinstance(entry["name"], str) and float(entry["speed"]) > 0
        except (TypeError, KeyError, ValueError):
            return False

    def entry(self, name):
        if not name:
            return None
        entry = self._load().get(normalize_key(name))
        return entry if self._valid(entry) else None

    def get(self, name):
        entry = self.entry(name)
        return float(entry["speed"]) if entry else None

    def set(self, name, speed, **extra):
        entries = self._load()
        entries[normalize_key(name)] = dict(extra, name=name, speed=round(speed, 2))
        self._save(entries)

    def remove(self, name):
        entries = self._load()
        if entries.pop(normalize_key(name), None) is not None:
            self._save(entries)

    def all(self):
        """Valid entries, sorted by name."""
        entries = [e for e in self._load().values() if self._valid(e)]
        return sorted(entries, key=lambda e: e["name"].casefold())
