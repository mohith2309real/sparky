# Where Sparky keeps its settings. Normally the system's place for them;
# SPARKY_SETTINGS_FILE points at an .ini file instead (tests, screenshots,
# and the portable version, which keeps settings next to the app).

import os

from PyQt6.QtCore import QSettings


def open_settings():
    path = os.environ.get("SPARKY_SETTINGS_FILE")
    if path:
        return QSettings(path, QSettings.Format.IniFormat)
    return QSettings("Sparky", "Sparky")
