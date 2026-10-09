# Zero setup: when there's no Arduino IDE, Sparky fetches arduino-cli itself.
#
# The file comes from Arduino's own download server and must match the
# SHA-256 below (copied from Arduino's published checksums for this
# version), or it is thrown away. It is unpacked into Sparky's data folder,
# never anywhere system-wide.

import io
import platform
import sys
import tarfile
import zipfile

from ..update import download as dl
from .cli import EXE, data_tools_dir

VERSION = "1.5.1"
BASE = "https://downloads.arduino.cc/arduino-cli/"
FILES = {   # computer: (file, size in bytes, SHA-256)
    "mac-arm64": ("arduino-cli_1.5.1_macOS_ARM64.tar.gz", 17370016,
                  "cb952e8c1621c95ef5f1d17831c945e3d0ec5973f89c557a7ec8feb9c4f7d4c9"),
    "mac-x86_64": ("arduino-cli_1.5.1_macOS_64bit.tar.gz", 19355892,
                   "c982e940027996bea9901050e95fae99c59c1dcfee54beedecaf28141e7bf2e7"),
    "windows-x64": ("arduino-cli_1.5.1_Windows_64bit.zip", 17965819,
                    "fabe42e0eb04d00e776a66178299ff95a46c623dbc260f997e58fd514853dd40"),
    "linux-x86_64": ("arduino-cli_1.5.1_Linux_64bit.tar.gz", 17630765,
                     "28a8e119c498a25607821c36cb2dc49e8463941b261a0d99091baa7bc692dd2b"),
    "linux-arm64": ("arduino-cli_1.5.1_Linux_ARM64.tar.gz", 16155457,
                    "1e69e077479f300614d4551334e0a33f08ee40b04315d83b8e7e0e94f0d0ee62"),
}


def this_computer():
    machine = platform.machine().lower()
    arm = machine in ("arm64", "aarch64")
    if sys.platform == "darwin":
        return "mac-arm64" if arm else "mac-x86_64"
    if sys.platform == "win32":
        return "windows-x64"
    return "linux-arm64" if arm else "linux-x86_64"


def install(progress=None, cancel=None):
    """Download, check and unpack arduino-cli. Returns its path."""
    name, size, sha256 = FILES[this_computer()]
    folder = data_tools_dir()
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder / name
    dl.download(BASE + name, archive, sha256, size, "Sparky arduino-cli setup",
                progress=progress, cancelled=cancel)
    data = archive.read_bytes()
    target = folder / EXE
    if name.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            target.write_bytes(zf.read(EXE))
    else:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            member = tf.getmember(EXE)
            target.write_bytes(tf.extractfile(member).read())
    target.chmod(0o755)
    archive.unlink(missing_ok=True)
    return target
