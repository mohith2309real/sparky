# Where Sparky's files live — in BOTH lives it leads:
#
# 1. Running from the repo (developers, from-source): read-only data
#    (assets, examples) sits next to the code, and writable folders
#    (gallery, extensions) live in the repo too.
#
# 2. Running as a frozen standalone app (PyInstaller bundle): read-only
#    data is baked INSIDE the app, and writable folders move to a
#    friendly ~/Sparky folder so the app itself never changes.

import shutil
import sys
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)

if FROZEN:
    RESOURCES = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    USER_DIR = Path.home() / "Sparky"
else:
    RESOURCES = Path(__file__).resolve().parent.parent
    USER_DIR = Path(__file__).resolve().parent.parent

ASSETS_DIR = RESOURCES / "assets"
EXAMPLES_DIR = RESOURCES / "examples"
GALLERY_DIR = USER_DIR / "gallery"
EXTENSIONS_DIR = USER_DIR / "extensions"


def prepare_user_dirs():
    """Create ~/Sparky (or repo folders) and seed the sample extension."""
    GALLERY_DIR.mkdir(parents=True, exist_ok=True)
    EXTENSIONS_DIR.mkdir(parents=True, exist_ok=True)
    if FROZEN:
        sample = RESOURCES / "extensions" / "shape_pack.py"
        target = EXTENSIONS_DIR / "shape_pack.py"
        if sample.exists() and not target.exists():
            try:
                shutil.copy(sample, target)
            except OSError:
                pass
