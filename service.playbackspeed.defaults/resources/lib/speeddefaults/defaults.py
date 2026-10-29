"""Default setting values, read from the add-on's resources/settings.xml."""

import xml.etree.ElementTree as ET


def parse_setting_defaults(xml):
    """Map each setting id to its <default>, converted to the setting's type."""
    defaults = {}
    for setting in ET.fromstring(xml).iter("setting"):
        default = setting.find("default")
        if default is None or default.text is None:
            continue
        kind = setting.get("type")
        text = default.text.strip()
        if kind == "boolean":
            value = text.casefold() == "true"
        elif kind == "integer":
            value = int(text)
        elif kind == "number":
            value = float(text)
        else:
            value = text
        defaults[setting.get("id")] = value
    return defaults
