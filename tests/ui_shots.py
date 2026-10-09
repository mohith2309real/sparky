# Screenshots of the real Sparky IDE, for checking the design.
#   QT_QPA_PLATFORM=offscreen python3 tests/ui_shots.py OUT_DIR [names...]
# Uses a throwaway settings file, so it never touches your own settings.

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp())
ONLY = set(sys.argv[2:])
OUT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("SPARKY_SETTINGS_FILE", str(Path(tempfile.mkdtemp()) / "settings.ini"))
os.environ["SPARKY_NEW_WINDOW"] = "1"

from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from sparky.ide import app as appmod  # noqa: E402
from sparky.ide import design  # noqa: E402
from sparky.ide.theme import load_fonts  # noqa: E402
from sparky.paths import ASSETS_DIR  # noqa: E402

qt = QApplication(sys.argv)
load_fonts(ASSETS_DIR)
from PyQt6.QtGui import QFont  # noqa: E402
f = QFont()
f.setFamilies(design.UI_FONTS)
f.setPointSize(13)
qt.setFont(f)

prefs = appmod.prefs.open_settings()
prefs.setValue("first_run_done", True)
prefs.setValue("mode", "pro")
prefs.sync()

win = appmod.MainWindow()
win.resize(1440, 900)
win.show()


def pump(seconds=0.3):
    end = time.time() + seconds
    while time.time() < end:
        qt.processEvents()
        time.sleep(0.01)


def wanted(name):
    return not ONLY or name in ONLY


def shot(name, widget=None):
    if not wanted(name):
        return
    pump(0.25)
    (widget or win).grab().save(str(OUT / f"{name}.png"))
    print("shot", name, flush=True)


def run_and_wait(limit=15):
    win.speed.setValue(10)
    win.run_program()
    end = time.time() + limit
    while win.is_running() and time.time() < end:
        pump(0.05)
    pump(0.3)


pump(0.6)
shot("home-daylight")
win.show_workspace()
win.show_sidebar_named("blocks")
run_and_wait()
shot("workspace-daylight")
for key in ("midnight", "candy", "contrast"):
    win.set_theme(key)
    shot(f"workspace-{key}")
win.set_theme("midnight")
win.show_home()
shot("home-midnight")
win.set_theme("daylight")
win.show_workspace()
win.set_grid(True)
win.step_program()
pump(0.6)
shot("paused-step")
win.stop_program()
pump(0.3)
win.set_grid(False)
win.set_mode("kid")
shot("workspace-kid")
win.set_mode("pro")

from sparky.ide.settings_dialog import SettingsDialog  # noqa: E402
for page in ("General", "Updates", "About"):
    if wanted(f"settings-{page.lower()}"):
        d = SettingsDialog(win, page)
        d.show()
        shot(f"settings-{page.lower()}", d)
        d.close()

from sparky.ide.dialogs import AboutDialog, FirstRunDialog, WhatsNewDialog  # noqa: E402
for name, cls in (("first-run", FirstRunDialog), ("whats-new", WhatsNewDialog), ("about", AboutDialog)):
    if wanted(name):
        d = cls(win)
        d.show()
        shot(name, d)
        d.close()

if any(wanted(n) for n in ("tour-1", "tour-3", "tour-5", "tour-9", "tour-12")) or not ONLY:
    win.show_home()
    win.start_tour()
    for i in range(1, 13):
        pump(0.35)
        if i in (1, 3, 5, 9, 12):
            shot(f"tour-{i}")
        step = win.tour.current()
        if step.helper:
            win.tour.run_helper()
            pump(0.6)
            if step.key in ("run", "draw"):
                end = time.time() + 10
                while win.is_running() and time.time() < end:
                    pump(0.05)
        win.tour.advance()
    if win.tour:
        win.tour.finish(False)

win.update_bar.ready("3.0.0-alpha.2")
win.show_workspace()
shot("update-bar")
print("done", OUT)
