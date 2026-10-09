# Sparky's launcher for installed copies (the Mac app, the Windows
# installer, the Linux folder). It runs before the `sparky` package is
# imported, so it can choose which copy of the code starts:
#
#   * the newest installed update pack, if it's newer than the built-in
#     code, matches this app's runtime, and passes its file checks, or
#   * the code built into the app.
#
# If a pack fails to start twice in a row, it's marked bad and Sparky goes
# back to the previous good version, then says so. `--safe` skips packs.
#
# Keep this file small and dependency-free: it can only change with a
# full update, never through a pack.

import hashlib
import json
import os
import re
import sys
from pathlib import Path

BASE_VERSION = "3.0.0-alpha.1"   # the version of the code built into this app
RUNTIME = 1                      # bump when Python, Qt or the bundled libraries change

running_pack = None              # the pack version in use, or None for the built-in code
notice = ""                      # a message for the app to show once, e.g. after a rollback
safe_mode = False
_tries_limit = 2


def data_dir():
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Sparky"
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "Sparky"
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "sparky"


def updates_dir():
    return data_dir() / "updates"


_VERSION = re.compile(r"^(\d+)\.(\d+)(?:\.(\d+))?(?:-(alpha|beta|rc)(?:\.(\d+))?)?$")


def _key(text):
    match = _VERSION.match(str(text))
    if not match:
        return None
    major, minor, patch, pre, num = match.groups()
    rank = {"alpha": 0, "beta": 1, "rc": 2}.get(pre, 3)
    return int(major), int(minor), int(patch or 0), rank, int(num or 0)


def _newer(a, b):
    ka, kb = _key(a), _key(b)
    return ka is not None and kb is not None and ka > kb


def _read_json(path, default):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, type(default)) else default
    except (OSError, ValueError):
        return default


def _write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def pack_is_sound(folder, version):
    """True if the pack folder is complete, unchanged and made for this runtime."""
    folder = Path(folder)
    meta = _read_json(folder / "pack.json", {})
    listing = _read_json(folder / "pack-files.json", {})
    if meta.get("version") != version or listing.get("version") != version:
        return False
    if meta.get("runtime") != RUNTIME or listing.get("runtime") != RUNTIME:
        return False
    files = listing.get("files")
    if not isinstance(files, dict) or "sparky/__init__.py" not in files:
        return False
    for rel, digest in files.items():
        try:
            if hashlib.sha256((folder / rel).read_bytes()).hexdigest() != digest:
                return False
        except OSError:
            return False
    return True


def _fall_back(state, version, why):
    global notice
    bad = state.setdefault("bad", [])
    if version not in bad:
        bad.append(version)
    previous = state.get("previous")
    usable = previous and previous != version and previous not in bad
    state["current"] = previous if usable else None
    state["previous"] = None
    back_to = previous if usable else BASE_VERSION
    notice = f"Sparky {version} {why}, so Sparky went back to {back_to}."
    _write_json(updates_dir() / "state.json", state)


def choose_pack():
    """The folder of the pack to start, or None for the built-in code."""
    updates = updates_dir()
    state = _read_json(updates / "state.json", {})
    for _ in range(3):
        version = state.get("current")
        if not version or not _newer(version, BASE_VERSION):
            return None, None
        if version in state.get("bad", []):
            state["current"] = None
            return None, None
        booting = _read_json(updates / "booting.json", {})
        if booting.get("version") == version and booting.get("tries", 0) >= _tries_limit:
            (updates / "booting.json").unlink(missing_ok=True)
            _fall_back(state, version, "didn't start")
            continue
        folder = updates / "packs" / version
        if not pack_is_sound(folder, version):
            _fall_back(state, version, "was damaged")
            continue
        return folder, version
    return None, None


def mark_good():
    """Called by the app once its window is up: whatever is running works."""
    try:
        (updates_dir() / "booting.json").unlink(missing_ok=True)
        if running_pack:
            state = _read_json(updates_dir() / "state.json", {})
            if state.get("last_good") != running_pack:
                state["last_good"] = running_pack
                _write_json(updates_dir() / "state.json", state)
    except OSError:
        pass


def main():
    global running_pack, safe_mode
    if "--safe" in sys.argv[1:]:
        sys.argv.remove("--safe")
        safe_mode = True
        os.environ["SPARKY_SAFE_MODE"] = "1"
    elif os.environ.get("SPARKY_NO_PACKS") != "1":
        try:
            folder, version = choose_pack()
            if folder is not None:
                booting = _read_json(updates_dir() / "booting.json", {})
                tries = booting.get("tries", 0) + 1 if booting.get("version") == version else 1
                _write_json(updates_dir() / "booting.json", {"version": version, "tries": tries})
                sys.path.insert(0, str(folder))
                running_pack = version
        except Exception:         # never let an update stop Sparky from starting
            running_pack = None
    from sparky.__main__ import main as sparky_main
    sparky_main()


if __name__ == "__main__":
    # Run as a script (the Linux launcher): the updater finds this module by name
    sys.modules.setdefault("sparky_boot", sys.modules[__name__])
    main()
