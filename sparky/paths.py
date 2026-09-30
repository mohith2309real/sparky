# Where Sparky's files live — in all the lives it leads:
#
# 1. Running from the repo (developers, from-source): read-only data
#    (assets, examples) sits next to the code, and writable folders
#    (gallery, extensions) live in the repo too.
#
# 2. Running as a frozen standalone app (PyInstaller bundle, macOS):
#    read-only data is baked INSIDE the app.
#
# 3. Running from an installed copy (Windows installer, Linux package):
#    the code and data sit in a folder the user may not be allowed to
#    write to, marked by a `sparky-installed.txt` file next to the code.
#
# In cases 2 and 3 the writable folders move to a friendly ~/Sparky
# folder, so the installed app itself never changes.

import shutil
import sys
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)
_CODE_ROOT = Path(__file__).resolve().parent.parent

if FROZEN:
    RESOURCES = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
else:
    RESOURCES = _CODE_ROOT

INSTALLED = FROZEN or (_CODE_ROOT / "sparky-installed.txt").exists()
USER_DIR = Path.home() / "Sparky" if INSTALLED else _CODE_ROOT

ASSETS_DIR = RESOURCES / "assets"
EXAMPLES_DIR = RESOURCES / "examples"
GALLERY_DIR = USER_DIR / "gallery"
EXTENSIONS_DIR = USER_DIR / "extensions"


def prepare_user_dirs():
    """Create ~/Sparky (or repo folders) and seed the sample extension."""
    GALLERY_DIR.mkdir(parents=True, exist_ok=True)
    EXTENSIONS_DIR.mkdir(parents=True, exist_ok=True)
    if INSTALLED:
        sample = RESOURCES / "extensions" / "shape_pack.py"
        target = EXTENSIONS_DIR / "shape_pack.py"
        if sample.exists() and not target.exists():
            try:
                shutil.copy(sample, target)
            except OSError:
                pass
