# Installing updates.
#
# Code packs unpack into <updates>/packs/<version>/ and become "current" in
# state.json. sparky_boot.py loads the current pack on the next start, and
# falls back to the built-in code if a pack ever fails to start.
#
# Full updates (a new Python/Qt runtime) are staged next to the packs and
# finished by a small helper script after Sparky quits: macOS swaps the app
# bundle, Windows runs the new installer silently, Linux replaces its folder.

import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from . import where

KEEP_PACKS = 2          # the current pack and the one before it


class InstallError(Exception):
    pass


# ---------- state.json ----------

def state_path(root=None):
    return Path(root or where.updates_dir()) / "state.json"


def load_state(root=None):
    try:
        data = json.loads(state_path(root).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(state, root=None):
    path = state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("state.json.tmp")
    tmp.write_text(json.dumps(state, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def record(state, version, kind):
    history = state.setdefault("history", [])
    history.append({"version": version, "kind": kind,
                    "date": datetime.datetime.now().isoformat(timespec="seconds")})
    del history[:-30]


# ---------- code packs ----------

def _safe_members(archive):
    for info in archive.infolist():
        name = info.filename
        parts = Path(name).parts
        if name.startswith(("/", "\\")) or ".." in parts or ":" in name:
            raise InstallError(f"unsafe path in the update: {name}")
        yield info


def install_pack(zip_path, version, runtime, sha256, root=None):
    """Unpack a verified code pack and make it the one Sparky starts next time."""
    root = Path(root or where.updates_dir())
    packs = root / "packs"
    packs.mkdir(parents=True, exist_ok=True)
    staging = packs / f"{version}.partial"
    final = packs / version
    shutil.rmtree(staging, ignore_errors=True)
    try:
        with zipfile.ZipFile(zip_path) as archive:
            for info in _safe_members(archive):
                archive.extract(info, staging)
        listing = json.loads((staging / "pack-files.json").read_text(encoding="utf-8"))
        if listing.get("version") != version or listing.get("runtime") != runtime:
            raise InstallError("the pack's version doesn't match the signed update")
        for rel, digest in listing["files"].items():
            target = staging / rel
            if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise InstallError(f"a file in the pack is damaged: {rel}")
        (staging / "pack.json").write_text(json.dumps({
            "version": version, "runtime": runtime, "sha256": sha256,
            "installed": datetime.datetime.now().isoformat(timespec="seconds")}),
            encoding="utf-8")
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as err:
        shutil.rmtree(staging, ignore_errors=True)
        raise InstallError(f"the update couldn't be unpacked ({err})")
    except InstallError:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    shutil.rmtree(final, ignore_errors=True)
    os.replace(staging, final)
    state = load_state(root)
    previous = state.get("current")
    state["current"] = version
    state["previous"] = previous
    state.setdefault("bad", [])
    if version in state["bad"]:
        state["bad"].remove(version)
    record(state, version, "pack")
    save_state(state, root)
    prune(root, keep={version, previous})
    return final


def prune(root=None, keep=()):
    packs = Path(root or where.updates_dir()) / "packs"
    if not packs.is_dir():
        return
    for item in packs.iterdir():
        if item.name not in keep:
            shutil.rmtree(item, ignore_errors=True) if item.is_dir() else item.unlink()


def forget_packs(root=None):
    """Go back to the built-in version on the next start (keeps the files for now)."""
    state = load_state(root)
    state["current"] = None
    save_state(state, root)


# ---------- full updates ----------

def _write_script(name, text):
    folder = Path(tempfile.mkdtemp(prefix="sparky-update-"))
    script = folder / name
    script.write_text(text, encoding="utf-8")
    script.chmod(0o755)
    return script


def stage_full(artifact, kind, root=None):
    """Prepare a full update. Returns the command to start right before Sparky quits."""
    root = Path(root or where.updates_dir())
    target = where.install_root()
    if target is None:
        raise InstallError("this copy of Sparky can't replace itself — download the new "
                           "version from sparky-code.web.app instead")
    pid = str(os.getpid())
    log = root / "full-update.log"
    if kind == "mac-app-zip":
        staging = root / "full"
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True)
        result = subprocess.run(["/usr/bin/ditto", "-x", "-k", str(artifact), str(staging)],
                                capture_output=True, text=True)
        apps = list(staging.glob("*.app"))
        if result.returncode or len(apps) != 1:
            raise InstallError("the new app couldn't be unpacked")
        if not os.access(target.parent, os.W_OK):
            raise InstallError(f"Sparky isn't allowed to change {target.parent} — "
                               "drag the new version there yourself")
        script = _write_script("finish.sh", f"""#!/bin/bash
PID={pid}
NEW={_q(apps[0])}
APP={_q(target)}
for i in $(seq 1 240); do kill -0 "$PID" 2>/dev/null || break; sleep 0.25; done
OLD="$APP.updating-$$"
if mv "$APP" "$OLD" && mv "$NEW" "$APP"; then
  rm -rf "$OLD"
  echo "ok $(date)" > {_q(log)}
else
  [ -d "$OLD" ] && [ ! -d "$APP" ] && mv "$OLD" "$APP"
  echo "failed $(date)" > {_q(log)}
fi
[ -n "$SPARKY_UPDATE_NO_RELAUNCH" ] || open "$APP"
""")
        return ["/bin/bash", str(script)]
    if kind == "windows-setup":
        launcher = target / "Python" / "pythonw.exe"
        script = _write_script("finish.bat", f"""@echo off
:wait
tasklist /FI "PID eq {pid}" 2>nul | find "{pid}" >nul && (ping -n 2 127.0.0.1 >nul & goto wait)
"{artifact}" /S /CurrentUser "/INSTDIR={target}"
if errorlevel 1 (echo failed > "{log}") else (echo ok > "{log}")
if not defined SPARKY_UPDATE_NO_RELAUNCH start "" "{launcher}" "{target / 'Sparky.launch.pyw'}"
""")
        return ["cmd", "/c", str(script)]
    if kind == "linux-tar":
        script = _write_script("finish.sh", f"""#!/bin/sh
PID={pid}
ROOT={_q(target)}
for i in $(seq 1 240); do kill -0 "$PID" 2>/dev/null || break; sleep 0.25; done
TMP="$(mktemp -d)"
if tar -xzf {_q(artifact)} -C "$TMP" && [ -d "$TMP/Sparky/app" ]; then
  rm -rf "$ROOT/app.old" && mv "$ROOT/app" "$ROOT/app.old" && cp -R "$TMP/Sparky/app" "$ROOT/app" \\
    && cp "$TMP/Sparky/sparky" "$ROOT/sparky" && chmod +x "$ROOT/sparky" && rm -rf "$ROOT/app.old" \\
    && echo "ok $(date)" > {_q(log)} \\
    || {{ [ -d "$ROOT/app.old" ] && rm -rf "$ROOT/app" && mv "$ROOT/app.old" "$ROOT/app"; echo "failed $(date)" > {_q(log)}; }}
else
  echo "failed $(date)" > {_q(log)}
fi
rm -rf "$TMP"
[ -n "$SPARKY_UPDATE_NO_RELAUNCH" ] || "$ROOT/sparky" >/dev/null 2>&1 &
""")
        return ["/bin/sh", str(script)]
    raise InstallError(f"Sparky doesn't know how to install {kind!r}")


def _q(path):
    text = str(path).replace("'", "'\\''")
    return f"'{text}'"


def launch_detached(command):
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = 0x00000008 | 0x00000200   # DETACHED_PROCESS | NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, close_fds=True, **kwargs)
