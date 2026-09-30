# Writes assets/sparky.ico (Windows icon) from assets/logo.png.
# Small sizes are classic 32-bit BMP entries (what every Windows tool
# accepts); 256px is PNG-compressed, as Windows Vista+ expects.
# Run with: .venv/bin/python scripts/make_ico.py

import os
import struct
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QBuffer, QIODevice, Qt
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication

ROOT = os.path.join(os.path.dirname(__file__), "..")
SIZES = (16, 24, 32, 48, 64, 128, 256)


def bmp_entry(img):
    size = img.width()
    img = img.convertToFormat(QImage.Format.Format_ARGB32)
    rows = []
    for y in range(size - 1, -1, -1):          # BMP rows run bottom-up
        rows.append(bytes(img.constScanLine(y).asarray(size * 4)))
    pixels = b"".join(rows)
    mask_row = ((size + 31) // 32) * 4        # AND mask, all zero (alpha wins)
    mask = b"\x00" * (mask_row * size)
    header = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0,
                         len(pixels) + len(mask), 0, 0, 0, 0)
    return header + pixels + mask


def png_entry(img):
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(buf.data())


def main():
    app = QApplication(sys.argv)  # noqa: F841
    src = QImage(os.path.join(ROOT, "assets", "logo.png"))
    entries = []
    for s in SIZES:
        img = src.scaled(s, s, Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
        entries.append((s, png_entry(img) if s == 256 else bmp_entry(img)))
    out = struct.pack("<HHH", 0, 1, len(entries))
    offset = 6 + 16 * len(entries)
    blobs = b""
    for s, data in entries:
        dim = 0 if s == 256 else s
        out += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
        blobs += data
    path = os.path.join(ROOT, "assets", "sparky.ico")
    with open(path, "wb") as f:
        f.write(out + blobs)
    print("wrote", path, len(out + blobs), "bytes")


if __name__ == "__main__":
    main()
