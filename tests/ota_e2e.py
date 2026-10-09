# End-to-end over-the-air update test against a REAL built app.
#
#   .buildvenv/bin/python tests/ota_e2e.py dist/Sparky.app/Contents/MacOS/Sparky
#   .buildvenv/bin/python tests/ota_e2e.py "python3 -m sparky_boot"   (Linux folder, PYTHONPATH set)
#
# 1. builds a code pack of this repo, labelled with a newer test version
# 2. signs a beta manifest for it with the real release key (served only on 127.0.0.1)
# 3. `selfcheck` in the app downloads, verifies and installs it
# 4. a second `selfcheck` must report the new version, running from the pack
# 5. `selfcheck ui` opens the IDE from the pack and saves a screenshot
# 6. a pack that "fails to start" twice must roll back to the built-in code
# Everything happens in a throwaway home folder.

import hashlib
import http.server
import json
import os
import shlex
import subprocess
import sys
import tempfile
import threading
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "release"))
import make_pack  # noqa: E402
from common import envelope, runtime, version  # noqa: E402

TEST_VERSION = os.environ.get("OTA_TEST_VERSION", "3.0.0-alpha.99")
FULL_TEST_VERSION = "3.0.99"


def prepare(web, base):
    """Write a test pack + signed beta.json into `web`, with URLs under `base`."""
    web.mkdir(parents=True, exist_ok=True)
    real = make_pack.build(web.parent / "built")
    pack = web / f"Sparky-{TEST_VERSION}-pack.zip"
    files = {}
    with zipfile.ZipFile(real) as src, zipfile.ZipFile(pack, "w", zipfile.ZIP_DEFLATED) as dst:
        for name in src.namelist():
            if name == "pack-files.json":
                continue
            data = src.read(name)
            if name == "sparky/__init__.py":
                data = data.replace(f'"{version()}"'.encode(), f'"{TEST_VERSION}"'.encode())
            files[name] = hashlib.sha256(data).hexdigest()
            dst.writestr(name, data)
        dst.writestr("pack-files.json", json.dumps({"version": TEST_VERSION, "runtime": runtime(),
                                                    "files": files}))
    payload = {"product": "sparky", "channel": "beta", "version": TEST_VERSION,
               "date": "2026-10-08", "notes": "Test update", "runtime": runtime(),
               "pack": {"runtime": runtime(), "url": f"{base}/{pack.name}",
                        "sha256": hashlib.sha256(pack.read_bytes()).hexdigest(),
                        "size": pack.stat().st_size}}
    (web / "beta.json").write_text(json.dumps(envelope(payload)))


def prepare_full(web, base, artifacts):
    """stable.json offering only FULL updates (a newer runtime), for the given files.
    artifacts: {platform: (path, kind)}"""
    import shutil
    full = {}
    for platform, (path, kind) in artifacts.items():
        target = web / Path(path).name
        if Path(path).resolve() != target.resolve():
            shutil.copy(path, target)
        full[platform] = {"url": f"{base}/{target.name}", "kind": kind, "size": target.stat().st_size,
                          "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
    payload = {"product": "sparky", "channel": "stable", "version": FULL_TEST_VERSION,
               "date": "2026-10-08", "notes": "Full test", "runtime": runtime() + 1, "full": full}
    (web / "stable.json").write_text(json.dumps(envelope(payload)))


if sys.argv[1] == "--prepare":   # container tests: --prepare WEB_DIR PORT [platform=path:kind ...]
    web_dir, url = Path(sys.argv[2]), f"http://127.0.0.1:{sys.argv[3]}"
    prepare(web_dir, url)
    extra = {}
    for item in sys.argv[4:]:
        platform, rest = item.split("=", 1)
        path, kind = rest.rsplit(":", 1)
        extra[platform] = (path, kind)
    if extra:
        prepare_full(web_dir, url, extra)
    print("prepared", sys.argv[2])
    raise SystemExit(0)

app = shlex.split(sys.argv[1])
work = Path(tempfile.mkdtemp(prefix="sparky-ota-"))
home = work / "home"
home.mkdir()
web = work / "web"


class Quiet(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(web), **k)

    def log_message(self, *a):
        pass


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Quiet)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{server.server_address[1]}"

prepare(web, base)

env = dict(os.environ, HOME=str(home), XDG_STATE_HOME=str(home / ".state"),
           LOCALAPPDATA=str(home / "AppData"), SPARKY_SETTINGS_FILE=str(work / "settings.ini"),
           QT_QPA_PLATFORM=os.environ.get("QT_QPA_PLATFORM", "offscreen"))


def run(*args, extra=None):
    result = subprocess.run(app + list(args), env=dict(env, **(extra or {})), capture_output=True,
                            text=True, timeout=180)
    lines = [l for l in (result.stdout + result.stderr).splitlines()
             if "Sparky" in l or "Qt " in l or "Error" in l or "Traceback" in l]
    return "\n".join(lines[-3:])


def expect(label, text, *needles):
    ok = all(n in text for n in needles)
    print(("PASS " if ok else "FAIL ") + label + ": " + text.replace("\n", " / "))
    if not ok:
        raise SystemExit(1)


expect("built-in app", run("selfcheck"), "signatures ok", "running built-in code")
expect("downloads + installs the pack", run("selfcheck", extra={"SPARKY_SELFCHECK_UPDATE_URL": base}),
       f"installed pack {TEST_VERSION}")
expect("starts from the pack", run("selfcheck"), f"Sparky {TEST_VERSION}", f"running pack {TEST_VERSION}")
shot = work / "ui-from-pack.png"
expect("IDE opens from the pack", run("selfcheck", "ui", str(shot)), f"Sparky {TEST_VERSION}",
       "lines drawn")

data_dir = (home / "Library" / "Application Support" / "Sparky" if sys.platform == "darwin" else
            home / "AppData" / "Sparky" if "wine" in app[0] else home / ".state" / "sparky")
(data_dir / "updates" / "booting.json").write_text(json.dumps({"version": TEST_VERSION, "tries": 2}))
expect("rolls back after failed starts", run("selfcheck"), "running built-in code")
state = json.loads((data_dir / "updates" / "state.json").read_text())
expect("marks the pack bad", json.dumps(state.get("bad")), TEST_VERSION)
# 7. Mac: a FULL update swaps the whole app (tested on a copy of it)
if sys.platform == "darwin" and ".app/Contents/MacOS/" in app[0]:
    import shutil
    import time
    bundle = Path(app[0]).resolve().parents[2]
    apps = work / "Apps"
    apps.mkdir()
    copy = apps / bundle.name
    subprocess.run(["ditto", str(bundle), str(copy)], check=True)
    zipped = web / "Sparky-mac-arm64.zip"
    subprocess.run(["ditto", "-c", "-k", "--keepParent", str(copy), str(zipped)], check=True)
    prepare_full(web, base, {"mac-arm64": (zipped, "mac-app-zip")})
    before = (copy / "Contents").stat().st_ino
    app = [str(copy / "Contents" / "MacOS" / Path(app[0]).name)]
    expect("full update downloads + stages", run("selfcheck", extra={
        "SPARKY_SELFCHECK_UPDATE_URL": base, "SPARKY_SELFCHECK_CHANNEL": "stable",
        "SPARKY_UPDATE_NO_RELAUNCH": "1"}), "staged full update 3.0.99")
    log = data_dir / "updates" / "full-update.log"
    for _ in range(120):
        if log.exists() and log.read_text().startswith(("ok", "failed")):
            break
        time.sleep(0.5)
    swapped = (copy / "Contents").stat().st_ino != before
    leftovers = [p.name for p in apps.iterdir() if p.name != copy.name]
    expect("full update swaps the app", f"{log.read_text().strip()} swapped={swapped} leftovers={leftovers}",
           "ok", "swapped=True", "leftovers=[]")
    expect("new app starts", run("selfcheck"), "signatures ok")

server.shutdown()
print(f"OTA end-to-end: all good (screenshot from the pack: {shot})")
