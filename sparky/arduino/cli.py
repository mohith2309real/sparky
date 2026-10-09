# Talking to arduino-cli, the engine inside Arduino IDE 2.
#
# Sparky never asks kids to install anything: it uses the arduino-cli that
# ships inside Arduino IDE 2 (and Arduino IDE's settings, so boards,
# libraries and the sketchbook are shared), or one on the PATH, or a copy
# Sparky downloaded itself (see download.py). No Qt in here.

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

IS_WINDOWS = sys.platform.startswith("win")
EXE = "arduino-cli.exe" if IS_WINDOWS else "arduino-cli"

# board packages kids ask for most, and where their index files live
EXTRA_INDEXES = {
    "esp32:esp32": "https://espressif.github.io/arduino-esp32/package_esp32_index.json",
    "esp8266:esp8266": "https://arduino.esp8266.com/stable/package_esp8266com_index.json",
    "rp2040:rp2040": "https://github.com/earlephilhower/arduino-pico/releases/download/global/"
                     "package_rp2040_index.json",
}

# boards shown first in the picker (when their package is installed)
FAVORITE_BOARDS = ["arduino:avr:uno", "arduino:avr:nano", "arduino:avr:mega",
                   "arduino:avr:leonardo", "arduino:renesas_uno:unor4wifi",
                   "arduino:renesas_uno:minima", "rp2040:rp2040:rpipico",
                   "arduino:mbed_rp2040:pico", "esp32:esp32:esp32", "esp8266:esp8266:nodemcuv2"]


class CLIError(Exception):
    pass


@dataclass
class Board:
    name: str
    fqbn: str


@dataclass
class Port:
    address: str
    label: str
    protocol: str = "serial"
    boards: list = field(default_factory=list)     # [Board] the port says it is

    def title(self):
        if self.boards:
            return f"{self.boards[0].name} on {self.short()}"
        return self.short()

    def short(self):
        return self.address.replace("/dev/cu.", "").replace("/dev/tty", "tty")

    def looks_like_board(self):
        """Bluetooth headphones and debug consoles also show up as serial ports."""
        if self.boards:
            return True
        name = self.address.lower()
        if re.fullmatch(r"com\d+", name):          # Windows
            return True
        return any(k in name for k in ("usbmodem", "usbserial", "wchusb", "ttyusb", "ttyacm",
                                       "slab_usb", "ttyama"))


def data_tools_dir():
    from ..update.where import data_dir
    return data_dir() / "tools"


def candidates():
    """Places arduino-cli might live, best first."""
    out = []
    if os.environ.get("SPARKY_ARDUINO_CLI"):
        out.append(Path(os.environ["SPARKY_ARDUINO_CLI"]))
    found = shutil.which("arduino-cli")
    if found:
        out.append(Path(found))
    bundled = Path("resources") / "app" / "lib" / "backend" / "resources" / EXE
    if sys.platform == "darwin":
        for apps in (Path("/Applications"), Path.home() / "Applications"):
            out.append(apps / "Arduino IDE.app" / "Contents" / bundled)
    elif IS_WINDOWS:
        for base in (os.environ.get("LOCALAPPDATA"), os.environ.get("ProgramFiles"),
                     os.environ.get("ProgramFiles(x86)")):
            if base:
                sub = "Programs" if base == os.environ.get("LOCALAPPDATA") else ""
                out.append(Path(base) / sub / "Arduino IDE" / bundled)
    else:
        for base in (Path("/opt/arduino-ide"), Path("/usr/lib/arduino-ide"),
                     Path.home() / "arduino-ide", Path("/usr/share/arduino-ide")):
            out.append(base / bundled)
    out.append(data_tools_dir() / EXE)
    return out


def ide_config():
    """Arduino IDE 2's settings for arduino-cli, if Arduino IDE is set up."""
    path = Path.home() / ".arduinoIDE" / "arduino-cli.yaml"
    return path if path.is_file() else None


class ArduinoCLI:
    def __init__(self, path, config=None):
        self.path = Path(path)
        self.config = Path(config) if config else None
        self._version = None

    @classmethod
    def find(cls):
        for path in candidates():
            if path.is_file() and os.access(path, os.X_OK):
                return cls(path, ide_config())
        return None

    def where(self):
        if "Arduino IDE" in str(self.path):
            return "Arduino IDE"
        if str(self.path).startswith(str(data_tools_dir())):
            return "Sparky's own copy"
        return str(self.path)

    def base(self):
        args = [str(self.path)]
        if self.config:
            args += ["--config-file", str(self.config)]
        return args

    def command(self, *args):
        """The full command line (for running it with a live log)."""
        return self.base() + [str(a) for a in args]

    def run(self, *args, timeout=180):
        try:
            result = subprocess.run(self.command(*args), capture_output=True, text=True,
                                    timeout=timeout, **_no_window())
        except subprocess.TimeoutExpired:
            raise CLIError("arduino-cli took too long to answer.")
        except OSError as err:
            raise CLIError(f"Couldn't start arduino-cli: {err}")
        return result

    def run_json(self, *args, timeout=180):
        result = self.run(*args, "--format", "json", timeout=timeout)
        text = result.stdout.strip()
        try:
            data = json.loads(text) if text else {}
        except ValueError:
            data = None
        if result.returncode != 0:
            message = (data or {}).get("error") if isinstance(data, dict) else None
            raise CLIError(message or result.stderr.strip() or text or "arduino-cli failed.")
        if data is None:
            raise CLIError("arduino-cli answered something Sparky couldn't read.")
        return data

    # ---------- what's there ----------

    def version(self):
        if self._version is None:
            try:
                data = self.run_json("version", timeout=30)
                self._version = data.get("VersionString") or data.get("version") or "?"
            except CLIError:
                self._version = "?"
        return self._version

    def boards(self):
        """Every board of every installed board package, favorites first."""
        data = self.run_json("board", "listall")
        boards = [Board(b["name"], b["fqbn"]) for b in data.get("boards", []) if b.get("fqbn")]
        rank = {fqbn: i for i, fqbn in enumerate(FAVORITE_BOARDS)}
        boards.sort(key=lambda b: (rank.get(b.fqbn, 999), b.name.lower()))
        return boards

    def ports(self):
        data = self.run_json("board", "list", timeout=60)
        out = []
        for item in data.get("detected_ports", []):
            port = item.get("port", {})
            boards = [Board(b.get("name", "?"), b.get("fqbn", ""))
                      for b in item.get("matching_boards", []) or []]
            out.append(Port(port.get("address", ""), port.get("label", ""),
                            port.get("protocol", "serial"), boards))
        out.sort(key=lambda p: (not p.looks_like_board(), p.address))
        return out

    # ---------- compile / upload / monitor (run with a live log) ----------

    def compile_command(self, sketch_dir, fqbn):
        return self.command("compile", "--fqbn", fqbn, sketch_dir)

    def upload_command(self, sketch_dir, fqbn, port):
        return self.command("compile", "--upload", "--fqbn", fqbn, "--port", port, sketch_dir)

    def monitor_command(self, port, fqbn, baud):
        args = ["monitor", "--port", port, "--config", f"baudrate={baud}", "--quiet", "--raw"]
        if fqbn:
            args += ["--fqbn", fqbn]
        return self.command(*args)

    # ---------- libraries ----------

    def lib_search(self, query):
        data = self.run_json("lib", "search", query, timeout=120)
        out = []
        for lib in data.get("libraries", []):
            latest = lib.get("latest") or {}
            if not latest and lib.get("releases"):
                latest = list(lib["releases"].values())[-1]
            out.append({"name": lib.get("name", "?"), "version": latest.get("version", ""),
                        "sentence": latest.get("sentence", ""),
                        "author": latest.get("author", "")})
        return out

    def lib_installed(self):
        data = self.run_json("lib", "list")
        out = {}
        for item in data.get("installed_libraries", []):
            lib = item.get("library", {})
            out[lib.get("name", "?")] = lib.get("version", "")
        return out

    def lib_install(self, name):
        return self.run_json("lib", "install", name, timeout=600)

    def lib_uninstall(self, name):
        return self.run_json("lib", "uninstall", name, timeout=120)

    def lib_examples(self):
        """[(library, example name, folder)] for every installed library."""
        data = self.run_json("lib", "examples")
        out = []
        for item in data.get("examples", []):
            name = item.get("library", {}).get("name", "?")
            for path in item.get("examples", []):
                out.append((name, Path(path).name, Path(path)))
        return out

    # ---------- board packages ----------

    def index_urls(self, core_ids=()):
        return [EXTRA_INDEXES[c] for c in core_ids if c in EXTRA_INDEXES]

    def core_update_index(self, urls=()):
        args = ["core", "update-index"]
        for url in urls:
            args += ["--additional-urls", url]
        return self.run_json(*args, timeout=600)

    def core_search(self, query="", urls=()):
        args = ["core", "search"] + ([query] if query else [])
        for url in urls:
            args += ["--additional-urls", url]
        data = self.run_json(*args, timeout=180)
        out = []
        for core in data.get("platforms", []):
            releases = core.get("releases", {}) or {}
            latest = core.get("latest_version") or (list(releases)[-1] if releases else "")
            info = releases.get(latest, {}) if latest else {}
            out.append({"id": core.get("id", "?"), "name": info.get("name", core.get("id", "?")),
                        "latest": latest, "installed": core.get("installed_version", ""),
                        "boards": [b.get("name") for b in info.get("boards", [])][:8]})
        return out

    def core_install(self, core_id, urls=()):
        args = ["core", "install", core_id]
        for url in urls:
            args += ["--additional-urls", url]
        return self.run_json(*args, timeout=1800)


def _no_window():
    if IS_WINDOWS:
        return {"creationflags": 0x08000000}          # CREATE_NO_WINDOW
    return {}


# ---------- sketches ----------

def sketchbook():
    """The Arduino sketchbook folder (shared with Arduino IDE)."""
    config = ide_config()
    if config:
        match = re.search(r"^\s*user:\s*(.+)$", config.read_text(encoding="utf-8"), re.M)
        if match:
            return Path(match.group(1).strip().strip('"'))
    return Path.home() / "Documents" / "Arduino"


def sketch_folder(path, text, scratch):
    """Arduino wants Blink/Blink.ino. Use the file's own folder when it already
    looks like that; otherwise copy the sketch into a matching scratch folder.
    Returns (folder to compile, the .ino path inside it)."""
    if path is not None:
        path = Path(path)
        if path.parent.name == path.stem:          # saved by the IDE just before
            return path.parent, path
        name = re.sub(r"[^A-Za-z0-9_]", "_", path.stem) or "sketch"
    else:
        name = "untitled_sketch"
    if name[0].isdigit():
        name = "sketch_" + name
    folder = Path(scratch) / name
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.ino"):
        if old.name != f"{name}.ino":
            old.unlink()
    target = folder / f"{name}.ino"
    target.write_text(text, encoding="utf-8")
    return folder, target


SIZE_RE = re.compile(r"Sketch uses (\d+) bytes \((\d+)%\)")
RAM_RE = re.compile(r"Global variables use (\d+) bytes \((\d+)%\)")


def size_summary(log):
    """'Uses 884 bytes (2% of the board) and 9 bytes of memory (0%)' from a compile log."""
    size, ram = SIZE_RE.search(log), RAM_RE.search(log)
    if not size:
        return None
    text = f"Uses {int(size.group(1)):,} bytes ({size.group(2)}% of the board's space)"
    if ram:
        text += f" and {int(ram.group(1)):,} bytes of memory ({ram.group(2)}%)"
    return text + "."
