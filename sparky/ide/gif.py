# A small animated-GIF writer for "Record the stage as a GIF".
#
# Qt turns each frame into 256 colors (Format_Indexed8); this file only does
# the GIF part: LZW compression and the file layout. Pure Python, no Pillow.

import struct


def lzw_encode(data, min_size=8):
    """GIF-flavoured LZW (variable code size, up to 12 bits). data: bytes of indices."""
    clear = 1 << min_size
    eoi = clear + 1
    size = min_size + 1
    next_code = eoi + 1
    table = {}
    out = bytearray()
    acc = 0
    nbits = 0

    def max_code(bits):
        return 4096 if bits == 12 else (1 << bits) - 1

    def put(code):
        nonlocal acc, nbits
        acc |= code << nbits
        nbits += size
        while nbits >= 8:
            out.append(acc & 0xFF)
            acc >>= 8
            nbits -= 8

    put(clear)
    if not data:
        put(eoi)
        if nbits:
            out.append(acc & 0xFF)
        return bytes(out)
    prefix = data[0]
    for byte in memoryview(data)[1:]:
        key = (prefix << 8) | byte
        code = table.get(key)
        if code is not None:
            prefix = code
            continue
        put(prefix)
        if next_code > max_code(size) and size < 12:
            size += 1
        if next_code < 4096:
            table[key] = next_code
            next_code += 1
        else:                                   # table full: start over
            put(clear)
            table = {}
            next_code = eoi + 1
            size = min_size + 1
        prefix = byte
    put(prefix)
    if next_code > max_code(size) and size < 12:
        size += 1
    put(eoi)
    if nbits:
        out.append(acc & 0xFF)
    return bytes(out)


def sub_blocks(data):
    out = bytearray()
    for i in range(0, len(data), 255):
        chunk = data[i:i + 255]
        out.append(len(chunk))
        out += chunk
    out.append(0)
    return bytes(out)


class GifWriter:
    """Collects frames (palette + index bytes) and writes an animated GIF."""

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.frames = []      # [palette rgb list, indices bytes, delay in 1/100 s]

    def add(self, palette, indices, delay_cs):
        if self.frames and self.frames[-1][1] == indices and self.frames[-1][0] == palette:
            self.frames[-1][2] += delay_cs          # nothing changed: show it longer
            return
        self.frames.append([palette, indices, delay_cs])

    def encode(self, progress=None):
        out = bytearray(b"GIF89a")
        out += struct.pack("<HHBBB", self.width, self.height, 0, 0, 0)
        out += b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00"       # loop forever
        for n, (palette, indices, delay) in enumerate(self.frames):
            out += b"\x21\xf9\x04\x04" + struct.pack("<H", max(2, min(65535, delay))) + b"\x00\x00"
            out += b"\x2c" + struct.pack("<HHHH", 0, 0, self.width, self.height)
            out.append(0x80 | 7)                                     # 256-color local table
            table = bytearray()
            for rgb in palette[:256]:
                table += bytes(((rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255))
            table += b"\x00" * (768 - len(table))
            out += table
            out.append(8)
            out += sub_blocks(lzw_encode(indices, 8))
            if progress:
                progress(n + 1, len(self.frames))
        out.append(0x3B)
        return bytes(out)


def frame_from_qimage(image):
    """(palette, indices) for a QImage, using Qt's 256-color conversion."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QImage
    indexed = image.convertToFormat(QImage.Format.Format_Indexed8,
                                    Qt.ImageConversionFlag.AvoidDither)
    palette = [c & 0xFFFFFF for c in indexed.colorTable()]
    width, height, stride = indexed.width(), indexed.height(), indexed.bytesPerLine()
    ptr = indexed.constBits()
    ptr.setsize(indexed.sizeInBytes())
    raw = bytes(ptr)
    if stride == width:
        return palette, raw[:width * height]
    return palette, b"".join(raw[y * stride:y * stride + width] for y in range(height))
