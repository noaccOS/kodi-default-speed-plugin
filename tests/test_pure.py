"""Tests for the modules that do not depend on Kodi's Python API."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "service.playbackspeed.defaults",
                                "resources", "lib", "speeddefaults"))

import defaults  # noqa: E402
import limits  # noqa: E402
import resolver  # noqa: E402
import store  # noqa: E402
from resolver import LibraryRule, MediaInfo, Preferences  # noqa: E402


class LimitsTest(unittest.TestCase):
    def test_choices_cover_range(self):
        choices = limits.all_choices()
        self.assertEqual(choices[0], 0.8)
        self.assertEqual(choices[-1], 2.0)
        self.assertIn(1.25, choices)

    def test_default_limit(self):
        self.assertEqual(limits.TempoLimits(21).highest, 1.5)
        # Kodi 22 keeps the 1.55 default but makes it inclusive.
        self.assertEqual(limits.TempoLimits(22).highest, 1.55)

    def test_kodi21_maxtempo_is_exclusive(self):
        self.assertEqual(limits.TempoLimits(21, 2.0).highest, 1.95)
        self.assertEqual(limits.TempoLimits(21, 2.1).highest, 2.0)

    def test_kodi22_maxtempo_is_inclusive(self):
        self.assertEqual(limits.TempoLimits(22, 2.0).highest, 2.0)
        self.assertEqual(limits.TempoLimits(22, 1.8).highest, 1.8)
        # Clamped to 2.0 on Kodi 22, so the Kodi 21 recommendation still works.
        self.assertEqual(limits.TempoLimits(22, 2.1).highest, 2.0)

    def test_minimum(self):
        lim = limits.TempoLimits(21)
        self.assertFalse(lim.is_allowed(0.75))
        self.assertTrue(lim.is_allowed(0.8))

    def test_clamp(self):
        lim = limits.TempoLimits(21)
        self.assertEqual(lim.clamp(2.0), 1.5)
        self.assertEqual(lim.clamp(1.3), 1.3)
        self.assertEqual(lim.clamp(0.5), 0.8)

    def test_parse_max_tempo(self):
        xml = "<advancedsettings><video><maxtempo> 2.1 </maxtempo></video></advancedsettings>"
        self.assertEqual(limits.parse_max_tempo(xml), 2.1)
        # Kodi ignores it under <videoplayer>, so must the add-on.
        wrong = "<advancedsettings><videoplayer><maxtempo>2.1</maxtempo></videoplayer></advancedsettings>"
        self.assertIsNone(limits.parse_max_tempo(wrong))
        self.assertIsNone(limits.parse_max_tempo("<advancedsettings/>"))
        self.assertIsNone(limits.parse_max_tempo("not xml"))
        self.assertIsNone(limits.parse_max_tempo(""))


def prefs(libraries=()):
    return Preferences(enabled=True, global_speed=1.1, libraries=list(libraries))


ANIME_TAG = LibraryRule(resolver.LIBRARY_TAG, "Anime", 1.5, "Anime")
ANIME_PATH = LibraryRule(resolver.LIBRARY_PATH, "smb://nas/Anime", 1.4, "NAS anime")


class ResolverTest(unittest.TestCase):
    episode = MediaInfo(kind="episode", series_title="Game of Thrones", tags=["TV Shows"],
                        path="smb://nas/tv/got/s01e01.mkv")
    # Jellyfin for Kodi in add-on mode: stream URL, library name as a tag.
    anime_episode = MediaInfo(kind="episode", series_title="One Piece", tags=["anime"],
                              path="http://jellyfin:8096/Videos/abc/stream")
    movie = MediaInfo(kind="movie", title="Heat")

    def test_global(self):
        res = resolver.resolve(self.movie, prefs())
        self.assertEqual((res.speed, res.source), (1.1, resolver.SOURCE_GLOBAL))

    def test_library_beats_global(self):
        res = resolver.resolve(self.anime_episode, prefs([ANIME_TAG]))
        self.assertEqual((res.speed, res.source, res.detail),
                         (1.5, resolver.SOURCE_LIBRARY, "Anime"))

    def test_other_library_falls_back_to_global(self):
        res = resolver.resolve(self.episode, prefs([ANIME_TAG, ANIME_PATH]))
        self.assertEqual((res.speed, res.source), (1.1, resolver.SOURCE_GLOBAL))

    def test_series_beats_everything(self):
        res = resolver.resolve(self.anime_episode, prefs([ANIME_TAG]), series_speed=2.0)
        self.assertEqual((res.speed, res.source, res.detail),
                         (2.0, resolver.SOURCE_SERIES, "One Piece"))

    def test_disabled(self):
        p = prefs()
        p.enabled = False
        self.assertIsNone(resolver.resolve(self.episode, p, series_speed=1.5))

    def test_path_rule(self):
        self.assertTrue(ANIME_PATH.matches(MediaInfo(path="smb://NAS/anime/Frieren/e01.mkv")))
        self.assertFalse(ANIME_PATH.matches(MediaInfo(path="smb://nas/Anime Movies/x.mkv")))
        windows = LibraryRule(resolver.LIBRARY_PATH, "D:\\Anime\\", 1.4)
        self.assertTrue(windows.matches(MediaInfo(path="D:\\Anime\\x.mkv")))

    def test_tag_rule(self):
        self.assertTrue(ANIME_TAG.matches(MediaInfo(tags=["Favorite tvshows", " ANIME "])))
        self.assertFalse(ANIME_TAG.matches(MediaInfo(tags=["Anime Movies"])))


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.store = store.SpeedStore(os.path.join(self.dir.name, "profile", "series.json"))

    def tearDown(self):
        self.dir.cleanup()

    def test_roundtrip(self):
        self.assertIsNone(self.store.get("One Piece"))
        self.store.set("One Piece", 1.3)
        self.store.set("Game of Thrones", 1.0)
        self.assertEqual(self.store.get("one  piece "), 1.3)
        self.assertEqual([(e["name"], e["speed"]) for e in self.store.all()],
                         [("Game of Thrones", 1.0), ("One Piece", 1.3)])
        self.store.remove("ONE PIECE")
        self.assertIsNone(self.store.get("One Piece"))

    def test_extra_fields(self):
        self.store.set("tag:Anime", 1.5, kind="tag", match="Anime", label="Anime")
        self.assertEqual(self.store.entry("TAG:anime")["match"], "Anime")

    def test_corrupt_file(self):
        os.makedirs(os.path.dirname(self.store.path))
        with open(self.store.path, "w") as f:
            f.write("{not json")
        self.assertEqual(self.store.all(), [])
        self.store.set("Frieren", 1.5)
        self.assertEqual(self.store.get("Frieren"), 1.5)

    def test_empty_title(self):
        self.assertIsNone(self.store.get(""))


class DefaultsTest(unittest.TestCase):
    def test_shipped_settings(self):
        path = os.path.join(os.path.dirname(__file__), "..", "service.playbackspeed.defaults",
                            "resources", "settings.xml")
        with open(path, "r", encoding="utf-8") as f:
            parsed = defaults.parse_setting_defaults(f.read())
        self.assertEqual(parsed, {
            "enabled": True,
            "global_speed": 1.0,
            "auto_sync_display": True,
            "notify_applied": True,
            "debug": False,
            "ask_save_on_stop": True,
        })


if __name__ == "__main__":
    unittest.main()
