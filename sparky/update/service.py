# The update service the IDE talks to.
#
#   check()      fetch and verify the channel's manifest (in a thread)
#   download()   fetch the update, verify its SHA-256, install or stage it
#   restart()    relaunch into the new version (packs), or hand over to the
#                full-update helper, then quit
#
# Signals carry plain values so the UI can show them: available(Update),
# progress(done, total), ready(Update), up_to_date(str), failed(str, bool manual).

import datetime
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from .. import __version__
from . import download as dl
from . import install, manifest, versions, where

SITE = "https://sparky-code.web.app"
CHECK_EVERY_MS = 6 * 60 * 60 * 1000


def runtime():
    boot = sys.modules.get("sparky_boot")
    return getattr(boot, "RUNTIME", 0)


def updatable():
    """True for installed copies that can update themselves (not source runs)."""
    return where.platform_id() is not None and runtime() > 0


class UpdateService(QObject):
    checking = pyqtSignal()
    available = pyqtSignal(object)
    progress = pyqtSignal(int, int)
    ready = pyqtSignal(object)
    up_to_date = pyqtSignal(str)
    failed = pyqtSignal(str, bool)
    _checked = pyqtSignal()

    def __init__(self, parent=None, settings=None, manifest_base=None):
        super().__init__(parent)
        if settings is None:
            from ..ide.prefs import open_settings
            settings = open_settings()
        self.settings = settings
        self.manifest_base = manifest_base or os.environ.get("SPARKY_UPDATE_URL") or \
            f"{SITE}/updates"
        self.update = None          # the newest Update seen
        self.staged = None          # what's ready to apply on restart
        self.restart_command = None
        self.busy = False
        self._cancel = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self.check(manual=False))
        self._checked.connect(lambda: self.settings.setValue(
            "updates/last_check", datetime.datetime.now().isoformat(timespec="minutes")))

    # ---------- settings ----------

    def channel(self):
        value = self.settings.value("updates/channel", "", type=str)
        if value not in manifest.CHANNELS:
            value = "beta" if versions.is_prerelease(__version__) else "stable"
        return value

    def auto_check(self):
        return self.settings.value("updates/auto_check", True, type=bool)

    def auto_download(self):
        return self.settings.value("updates/auto_download", True, type=bool)

    def offline(self):
        return self.settings.value("offline", False, type=bool)

    def last_check(self):
        return self.settings.value("updates/last_check", "", type=str)

    def history(self):
        return install.load_state().get("history", [])

    def start(self):
        """Begin quiet automatic checks (first one a few seconds after launch)."""
        if updatable() and self.auto_check() and not self.offline():
            QTimer.singleShot(4000, lambda: self.check(manual=False))
            self.timer.start(CHECK_EVERY_MS)

    # ---------- checking ----------

    def user_agent(self):
        return f"Sparky/{__version__} ({where.platform_id() or 'source'})"

    def fetch_latest(self):
        """Signed payloads for this channel (beta also sees stable), newest first."""
        channels = ["stable", "beta"] if self.channel() == "beta" else ["stable"]
        found, problems = [], []
        for name in channels:
            try:
                raw = dl.fetch_bytes(f"{self.manifest_base}/{name}.json", self.user_agent())
                found.append(manifest.read(raw, name))
            except (dl.DownloadError, manifest.ManifestError) as err:
                problems.append(f"{name}: {err}")
        if not found:
            raise dl.DownloadError("; ".join(problems) or "no update information")
        found.sort(key=lambda d: versions.parse(d["version"]), reverse=True)
        return found[0]

    def check(self, manual=True):
        if self.busy:
            return
        if self.offline():
            if manual:
                self.failed.emit("Offline mode is on, so Sparky didn't check for updates.", True)
            return
        if not updatable():
            if manual:
                self.failed.emit("This copy of Sparky runs from source code. Update it with "
                                 "git pull, or install Sparky from sparky-code.web.app.", True)
            return
        self.busy = True
        self.checking.emit()
        skip = self.settings.value("updates/skip", "", type=str)
        threading.Thread(target=self._check_thread, args=(manual, skip, self.auto_download()),
                         daemon=True).start()

    def _check_thread(self, manual, skip, auto_download):
        try:
            data = self.fetch_latest()
            update = manifest.choose(data, __version__, runtime(), where.platform_id())
        except (dl.DownloadError, manifest.ManifestError) as err:
            self.busy = False
            self.failed.emit(f"Couldn't check for updates: {err}", manual)
            return
        except Exception as err:          # never let a check crash the app
            self.busy = False
            self.failed.emit(f"Couldn't check for updates: {err}", manual)
            return
        self._checked.emit()
        self.busy = False
        if update is None:
            self.up_to_date.emit(__version__)
            return
        if not manual and update.version == skip:
            return
        self.update = update
        self.available.emit(update)
        if update.kind != "manual" and (manual or auto_download):
            self._start_download(update)

    # ---------- downloading and installing ----------

    def download(self):
        if self.update is not None and not self.busy:
            self._start_download(self.update)

    def _start_download(self, update):
        if update.kind == "manual":
            return
        if self.staged is not None and self.staged.version == update.version:
            self.ready.emit(update)
            return
        self.busy = True
        self._cancel = False
        threading.Thread(target=self._download_thread, args=(update,), daemon=True).start()

    def _download_thread(self, update):
        folder = where.updates_dir() / "downloads"
        name = update.url.rsplit("/", 1)[-1].split("?")[0] or "update.bin"
        try:
            path = dl.download(update.url, folder / name, update.sha256, update.size,
                               self.user_agent(), progress=self.progress.emit,
                               cancelled=lambda: self._cancel)
            if update.kind == "pack":
                install.install_pack(path, update.version, runtime(), update.sha256)
                path.unlink(missing_ok=True)
                self.restart_command = None
            else:
                self.restart_command = install.stage_full(path, update.artifact)
        except (dl.DownloadError, install.InstallError) as err:
            self.busy = False
            self.failed.emit(f"The update didn't install: {err}", True)
            return
        except Exception as err:
            self.busy = False
            self.failed.emit(f"The update didn't install: {err}", True)
            return
        self.busy = False
        self.staged = update
        self.ready.emit(update)

    def cancel(self):
        self._cancel = True

    def skip(self, version):
        self.settings.setValue("updates/skip", version)

    # ---------- restarting ----------

    def relaunch_command(self):
        bundle = where.frozen_app_bundle()
        if bundle is not None:
            return ["/usr/bin/open", "-n", str(bundle)]
        if sys.platform == "win32":
            return [sys.executable] + sys.argv[:1]
        return [sys.executable, "-m", "sparky_boot"]

    def restart(self, app):
        """Quit and come back as the new version."""
        command = self.restart_command or self.relaunch_command()
        if self.restart_command is None:
            command = after_exit(command)
        install.launch_detached(command)
        self.settings.setValue("updates/just_updated", self.staged.version if self.staged else "")
        app.quit()


def after_exit(command):
    """Wrap a command so it runs once this process has exited."""
    pid = os.getpid()
    if sys.platform == "win32":
        folder = Path(tempfile.mkdtemp(prefix="sparky-restart-"))
        script = folder / "restart.bat"
        quoted = " ".join(f'"{c}"' for c in command)
        script.write_text(f"""@echo off
:wait
tasklist /FI "PID eq {pid}" 2>nul | find "{pid}" >nul && (ping -n 2 127.0.0.1 >nul & goto wait)
start "" {quoted}
""", encoding="utf-8")
        return ["cmd", "/c", str(script)]
    return ["/bin/sh", "-c",
            f'while kill -0 {pid} 2>/dev/null; do sleep 0.2; done; exec "$@"', "sh"] + command
