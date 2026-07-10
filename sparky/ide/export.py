# "Make an App": turn the current program into a folder with the program
# plus double-clickable launchers for macOS, Windows, and Linux.
# Honest framing: the launchers use the Sparky player, so the computer
# needs Sparky (the README in each app folder explains this).

import os
import re
import stat
import sys
from pathlib import Path

from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from .dialogs import SITE_URL
from ..paths import FROZEN

SPARKY_DIR = Path(__file__).resolve().parent.parent.parent


def player_command_unix():
    """The shell lines that launch the player, for .command/.sh files."""
    if FROZEN:
        # standalone app: everything is inside the app bundle itself
        return f'exec "{sys.executable}" play "$DIR/$PROGRAM"'
    return (f'SPARKY="{SPARKY_DIR}"\n'
            'PY="$SPARKY/.venv/bin/python"\n'
            '[ -x "$PY" ] || PY=python3\n'
            'cd "$SPARKY" || exit 1\n'
            'exec "$PY" -m sparky play "$DIR/$PROGRAM"')


def safe_name(name):
    name = re.sub(r"[^\w \-]", "", name).strip()
    return name or "My App"


def make_app(main_window):
    source = main_window.editor.toPlainText()
    if not source.strip():
        QMessageBox.information(main_window, "Nothing to package",
                                "Write a program first, then make it an app!")
        return

    name, ok = QInputDialog.getText(
        main_window, "Make an App",
        "What's your app called?", text="My App")
    if not ok:
        return
    name = safe_name(name)

    where = QFileDialog.getExistingDirectory(
        main_window, "Where should the app folder go?",
        str(Path.home() / "Desktop"))
    if not where:
        return

    folder = Path(where) / name
    n = 2
    while folder.exists():
        folder = Path(where) / f"{name} {n}"
        n += 1
    folder.mkdir(parents=True)

    program = folder / f"{name}.spark"
    program.write_text(source, encoding="utf-8")

    launch = player_command_unix().replace("$PROGRAM", f"{name}.spark")

    mac = folder / f"Play {name}.command"
    mac.write_text(f"""#!/bin/zsh
# {name} — made with Sparky ({SITE_URL})
DIR="$(cd "$(dirname "$0")" && pwd)"
{launch}
""", encoding="utf-8")

    linux = folder / f"play_{name.replace(' ', '_').lower()}.sh"
    linux.write_text(f"""#!/bin/sh
# {name} — made with Sparky ({SITE_URL})
DIR="$(cd "$(dirname "$0")" && pwd)"
{launch}
""", encoding="utf-8")

    for script in (mac, linux):
        os.chmod(script, os.stat(script).st_mode
                 | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    windows = folder / f"Play {name}.bat"
    windows.write_text(f"""@echo off
rem {name} - made with Sparky ({SITE_URL})
rem If Sparky lives somewhere else on this computer, edit the next line:
set SPARKY=C:\\sparky
cd /d "%SPARKY%"
.venv\\Scripts\\python -m sparky play "%~dp0{name}.spark"
pause
""", encoding="utf-8")

    (folder / "README.txt").write_text(f"""{name}
{'=' * len(name)}

Made with Sparky — a coding platform for kids.

HOW TO PLAY
  Mac:      double-click "Play {name}.command"
  Windows:  double-click "Play {name}.bat"
            (first edit the SPARKY line inside if needed)
  Linux:    run ./play_{name.replace(' ', '_').lower()}.sh

This app runs on the Sparky player, so the computer needs Sparky.
The program itself is "{name}.spark" — open it in the Sparky IDE
to see (and remix!) the code.

Sparky was created by Mohith — {SITE_URL}
""", encoding="utf-8")

    QMessageBox.information(
        main_window, "Your app is ready! 🎉",
        f"Made \"{name}\" at:\n{folder}\n\n"
        "Double-click the Play file inside to run it — "
        "no editor, just your program.")
