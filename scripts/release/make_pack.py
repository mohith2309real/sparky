# Build a code pack: everything Sparky needs that isn't Python or Qt.
#   make_pack.py OUT_DIR  ->  OUT_DIR/Sparky-<version>-pack.zip
# The zip is reproducible (sorted names, fixed timestamps) and carries
# pack-files.json with a SHA-256 for every file, which sparky_boot checks.

import hashlib
import json
import sys
import zipfile
from pathlib import Path

from common import REPO, runtime, version

INCLUDE = ["sparky", "assets", "examples", "extensions", "GUIDE.md"]
SKIP_SUFFIXES = {".pyc", ".icns", ".ico"}
SKIP_NAMES = {"__pycache__", ".DS_Store", "brand-board.png"}


def pack_files():
    for top in INCLUDE:
        path = REPO / top
        if path.is_file():
            yield path
            continue
        for item in sorted(path.rglob("*")):
            if item.is_file() and not (set(item.relative_to(REPO).parts) & SKIP_NAMES) \
                    and item.suffix not in SKIP_SUFFIXES:
                yield item


def build(out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ver = version()
    files = {}
    data = {}
    for path in pack_files():
        rel = path.relative_to(REPO).as_posix()
        content = path.read_bytes()
        files[rel] = hashlib.sha256(content).hexdigest()
        data[rel] = content
    listing = {"version": ver, "runtime": runtime(), "files": files}
    target = out_dir / f"Sparky-{ver}-pack.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for rel in sorted(data):
            info = zipfile.ZipInfo(rel, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data[rel])
        info = zipfile.ZipInfo("pack-files.json", date_time=(2026, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, json.dumps(listing, indent=1, sort_keys=True))
    print(f"{target.name}: {len(files)} files, {target.stat().st_size / 1e6:.1f} MB")
    return target


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else REPO / "build" / "release")
