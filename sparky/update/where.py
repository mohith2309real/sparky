# Where updates live, and which build of Sparky is running.
#
# Kept free of Qt so the boot loader and the tests can use the same rules.
# sparky_boot.py repeats data_dir() (it must work before `sparky` is
# imported); tests/test_update.py checks the two never drift apart.

import os
import platform
import sys
from pathlib import Path


def data_dir():
    """Sparky's own app-data folder (not the user's ~/Sparky projects folder)."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Sparky"
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "Sparky"
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "sparky"


def updates_dir():
    return data_dir() / "updates"


def code_root():
    """The folder that holds the running `sparky` package (an update pack, or the app)."""
    return Path(__file__).resolve().parent.parent.parent


def frozen_app_bundle():
    """macOS: the Sparky.app folder we're running from, else None."""
    if sys.platform != "darwin" or not getattr(sys, "frozen", False):
        return None
    exe = Path(sys.executable).resolve()
    for parent in exe.parents:
        if parent.suffix == ".app":
            return parent
    return None


def install_root():
    """The folder that a full update replaces, or None when that isn't possible."""
    if sys.platform == "darwin":
        return frozen_app_bundle()
    boot = sys.modules.get("sparky_boot")
    base = Path(boot.__file__).resolve().parent if boot and getattr(boot, "__file__", None) else None
    if base is None or not (base / "sparky-installed.txt").exists():
        return None
    if sys.platform == "win32":
        return base.parent           # ...\Sparky (holds Python\, pkgs\, Sparky.launch.pyw)
    return base.parent               # .../Sparky (holds app/, the sparky launcher)


def platform_id():
    """mac-arm64 · windows-x64 · linux-x86_64 · linux-arm64 — or None when running from source."""
    if "sparky_boot" not in sys.modules:
        return None
    machine = platform.machine().lower()
    if sys.platform == "darwin":
        return "mac-arm64" if machine in ("arm64", "aarch64") else "mac-x86_64"
    if sys.platform == "win32":
        return "windows-x64"
    if machine in ("x86_64", "amd64"):
        return "linux-x86_64"
    if machine in ("aarch64", "arm64"):
        return "linux-arm64"
    return None
