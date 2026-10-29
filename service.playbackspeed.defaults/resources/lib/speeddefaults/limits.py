"""Which tempos Kodi's VideoPlayer will accept.

Pure module (no xbmc imports) so it can be unit tested.

The rules mirror CProcessInfo::IsTempoAllowed and the <maxtempo> parsing in
CAdvancedSettings, which differ between Kodi 21 and Kodi 22:

- Kodi 21: <maxtempo> is clamped to [1.5, 2.1] and the upper bound is
  exclusive, so reaching 2.0x needs <maxtempo>2.1</maxtempo>.
- Kodi 22: <maxtempo> is clamped to [1.5, 2.0] and the upper bound is
  inclusive (it allows maxtempo + 0.05 exclusive).

On both, the lower bound is 0.75 exclusive and anything below 1.55 is always
allowed. <maxtempo>2.1</maxtempo> therefore gives 2.0x on both versions.
"""

import xml.etree.ElementTree as ET

MIN_TEMPO_PLATFORM = 0.75
MAX_TEMPO_PLATFORM = 1.55
DEFAULT_MAX_TEMPO = 1.55

STEP = 0.05
LOWEST_CHOICE = 0.8
HIGHEST_CHOICE = 2.0

_EPSILON = 1e-6


def all_choices():
    count = int(round((HIGHEST_CHOICE - LOWEST_CHOICE) / STEP)) + 1
    return [round(LOWEST_CHOICE + i * STEP, 2) for i in range(count)]


def parse_max_tempo(advancedsettings_xml):
    """Return the raw <video><maxtempo> value, or None if unset/invalid.

    Kodi reads it from <video>, not <videoplayer> (CAdvancedSettings::ParseSettingsFile).
    """
    if not advancedsettings_xml:
        return None
    try:
        root = ET.fromstring(advancedsettings_xml)
    except ET.ParseError:
        return None
    node = root.find("video/maxtempo")
    if node is None or node.text is None:
        return None
    try:
        return float(node.text.strip())
    except ValueError:
        return None


class TempoLimits:
    def __init__(self, kodi_major, max_tempo_setting=None):
        self.kodi_major = kodi_major
        if kodi_major >= 22:
            clamp_high, self._inclusive_slack = 2.0, 0.05
        else:
            clamp_high, self._inclusive_slack = 2.1, 0.0
        if max_tempo_setting is None:
            self.max_tempo = DEFAULT_MAX_TEMPO
        else:
            self.max_tempo = min(max(max_tempo_setting, 1.5), clamp_high)

    def is_allowed(self, tempo):
        # CVideoPlayer::SetTempo rounds to two decimals before checking.
        tempo = round(tempo, 2)
        if tempo <= MIN_TEMPO_PLATFORM + _EPSILON:
            return False
        upper = self.max_tempo + self._inclusive_slack
        return tempo < MAX_TEMPO_PLATFORM - _EPSILON or tempo < upper - _EPSILON

    def choices(self):
        return [c for c in all_choices() if self.is_allowed(c)]

    @property
    def highest(self):
        return self.choices()[-1]

    def clamp(self, tempo):
        """Nearest allowed choice not exceeding the request (or the lowest one)."""
        allowed = self.choices()
        below = [c for c in allowed if c <= tempo + _EPSILON]
        return below[-1] if below else allowed[0]
