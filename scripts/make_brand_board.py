# Renders the Sparky brand board (3x3 identity sheet) -> assets/brand-board.png
# Run with: .venv/bin/python scripts/make_brand_board.py

import math
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(__file__))

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QColor, QFont, QFontMetricsF, QImage, QLinearGradient,
                         QPainter, QPainterPath, QPen, QPolygonF)
from PyQt6.QtWidgets import QApplication

from make_logo import draw_logo
from sparky.lang import Interpreter, Runtime, parse

W, H = 3200, 2000          # 2x of a 1600x1000 board
S = 2.0
INK = QColor("#141413")
PANEL = QColor("#1d1c1a")
CREAM = QColor("#faf9f5")
MUTED = QColor("#8a887e")
CORAL, SKY, SAGE = QColor("#d97757"), QColor("#6a9bcc"), QColor("#788c5d")


def font(px, weight=QFont.Weight.DemiBold, family="Avenir Next"):
    f = QFont(family)
    f.setPixelSize(int(px * S))
    f.setWeight(weight)
    return f


def text(p, x, y, s, f, color, spacing=0.0):
    f = QFont(f)
    if spacing:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing * S)
    p.setFont(f)
    p.setPen(color)
    p.drawText(QPointF(x * S, y * S), s)


def tile(p, x, y, w, h, fill, label, num, dark=True):
    path = QPainterPath()
    path.addRoundedRect(QRectF(x * S, y * S, w * S, h * S), 14 * S, 14 * S)
    p.fillPath(path, fill)
    c = MUTED if dark else QColor("#8a887e")
    if label:
        text(p, x + 18, y + 26, label, font(9.5, QFont.Weight.Bold), c, 1.6)
    text(p, x + w - 28, y + h - 16, num, font(9.5, QFont.Weight.Medium), c)
    return path


def mascot(p, cx, cy, r, ghost=False):
    p.save()
    p.translate(cx * S, cy * S)
    r *= S
    p.setPen(QPen(QColor("#b85c3f"), max(1.0, r * 0.07)))
    p.setBrush(CORAL)
    p.drawPolygon(QPolygonF([QPointF(0, -r * 1.7), QPointF(-r * .55, -r * .55),
                             QPointF(r * .55, -r * .55)]))
    p.drawEllipse(QPointF(0, 0), r, r)
    for side in (-1, 1):
        c = QPointF(side * r * .42, -r * .15)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(CREAM)
        p.drawEllipse(c, r * .3, r * .3)
        p.setBrush(INK)
        p.drawEllipse(QPointF(c.x(), c.y() - r * .06), r * .165, r * .165)
    p.setPen(QPen(INK, r * .09, cap=Qt.PenCapStyle.RoundCap))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(QRectF(-r * .35, r * .05, r * .7, r * .5), 210 * 16, 120 * 16)
    p.restore()


class Rec(Runtime):
    def __init__(self):
        self.segs = []
        self.spr = (0, 0, 0)

    def line(self, x1, y1, x2, y2, c, w):
        self.segs.append((x1, y1, x2, y2))

    def sprite(self, x, y, h, v, s):
        self.spr = (x, y, h)


def spiral():
    rec = Rec()
    src = ("set length to 2\nrepeat 80 times\n  move length\n  turn 91\n"
           "  change length by 4\nend\n")
    for _ in Interpreter(parse(src), rec).run():
        pass
    return rec


def main():
    app = QApplication(sys.argv)  # noqa: F841
    img = QImage(W, H, QImage.Format.Format_ARGB32)
    img.fill(QColor("#0f0f0e"))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    cols, rows = [35, 551, 1067], [35, 351, 667]
    tw, th = 498, 298

    # 01 identity
    x, y = cols[0], rows[0]
    tile(p, x, y, tw, th, PANEL, "SPARKY · IDENTITY 1.0", "01")
    p.drawImage(QRectF((x + 88) * S, (y + 106) * S, 88 * S, 88 * S),
                draw_logo(512))
    text(p, x + 192, y + 176, "Sparky", font(62, QFont.Weight.Black), CREAM, -1.5)
    text(p, x + 18, y + th - 16, "Coding platform for kids",
         font(10, QFont.Weight.Medium), MUTED)

    # 02 construction
    x = cols[1]
    tile(p, x, y, tw, th, PANEL, "CONSTRUCTION", "02")
    cx, cy, r = x + 150, y + 175, 52
    guide = QPen(QColor(255, 255, 255, 40), 1 * S, Qt.PenStyle.DashLine)
    p.setPen(guide)
    p.setBrush(Qt.BrushStyle.NoBrush)
    for gx in (cx - r, cx, cx + r):
        p.drawLine(QPointF(gx * S, (y + 45) * S), QPointF(gx * S, (y + 270) * S))
    for gy in (cy - r * 1.7, cy - r, cy, cy + r):
        p.drawLine(QPointF((x + 40) * S, gy * S), QPointF((x + 262) * S, gy * S))
    p.drawEllipse(QPointF(cx * S, cy * S), r * S, r * S)
    mascot(p, cx, cy, r)
    tx = x + 300
    text(p, tx, y + 110, "One spark", font(17, QFont.Weight.Bold), CREAM)
    for i, (sw, a, b) in enumerate(((CORAL, "Body", "circle, radius r"),
                                    (SKY, "Nose", "points where it's heading"),
                                    (CREAM, "Eyes", "0.3r, looking up"))):
        yy = y + 140 + i * 38
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(sw)
        p.drawRoundedRect(QRectF(tx * S, (yy - 10) * S, 11 * S, 11 * S), 3 * S, 3 * S)
        text(p, tx + 20, yy, a, font(11, QFont.Weight.DemiBold), CREAM)
        text(p, tx + 20, yy + 14, b, font(8.5, QFont.Weight.Medium), MUTED)

    # 03 app icons
    x = cols[2]
    tile(p, x, y, tw, th, PANEL, "APP ICON", "03")
    logo = draw_logo(1024)
    p.drawImage(QRectF((x + 48) * S, (y + 70) * S, 150 * S, 150 * S), logo)
    circ = QPainterPath()
    circ.addEllipse(QRectF((x + 228) * S, (y + 95) * S, 110 * S, 110 * S))
    p.save()
    p.setClipPath(circ)
    p.fillPath(circ, CREAM)
    p.drawImage(QRectF((x + 220) * S, (y + 87) * S, 126 * S, 126 * S), logo)
    p.restore()
    p.drawImage(QRectF((x + 370) * S, (y + 112) * S, 78 * S, 78 * S), logo)
    for lx, s in ((x + 123, "macOS"), (x + 283, "Linux"), (x + 409, "Windows")):
        f = font(9.5, QFont.Weight.Medium)
        w = QFontMetricsF(f).horizontalAdvance(s) / S
        text(p, lx - w / 2, y + 250, s, f, MUTED)

    # 04 tagline
    x, y = cols[0], rows[1]
    grad = QLinearGradient(x * S, y * S, (x + tw) * S, (y + th) * S)
    grad.setColorAt(0, QColor("#e08766"))
    grad.setColorAt(1, QColor("#c4603f"))
    path = QPainterPath()
    path.addRoundedRect(QRectF(x * S, y * S, tw * S, th * S), 14 * S, 14 * S)
    p.fillPath(path, grad)
    mascot(p, x + 34, y + 44, 13)
    text(p, x + 18, y + 208, "Code that reads", font(46, QFont.Weight.Black), CREAM, -1.2)
    text(p, x + 18, y + 262, "like English.", font(46, QFont.Weight.Black), CREAM, -1.2)
    text(p, x + tw - 28, y + th - 16, "04", font(9.5, QFont.Weight.Medium), CREAM)

    # 05 colour
    x = cols[1]
    tile(p, x, y, tw, th, CREAM, "COLOUR", "05", dark=False)
    sw = [("Coral", "#D97757", CORAL, True), ("Sky", "#6A9BCC", SKY, True),
          ("Sage", "#788C5D", SAGE, True), ("Cream", "#FAF9F5", QColor("#e8e6dc"), False),
          ("Ink", "#141413", INK, True)]
    bw = (tw - 36 - 4 * 8) / 5
    for i, (n, hx, c, light) in enumerate(sw):
        bx = x + 18 + i * (bw + 8)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c)
        p.drawRoundedRect(QRectF(bx * S, (y + 44) * S, bw * S, 216 * S), 10 * S, 10 * S)
        tc = CREAM if light else INK
        text(p, bx + 11, y + 232, n, font(11, QFont.Weight.DemiBold), tc)
        text(p, bx + 11, y + 248, hx, font(8.5, QFont.Weight.Medium), tc)

    # 06 type
    x = cols[2]
    tile(p, x, y, tw, th, PANEL, "TYPE", "06")
    text(p, x + 22, y + 222, "Aa", font(150, QFont.Weight.Black), CREAM, -4)
    tx = x + 250
    text(p, tx, y + 76, "Avenir Next", font(19, QFont.Weight.Bold), CREAM)
    text(p, tx, y + 94, "Black · Bold · Medium", font(9, QFont.Weight.Medium), MUTED)
    for i, s in enumerate(("ABCDEFGHIJKLM", "abcdefghijklm", "0123456789 &?!")):
        text(p, tx, y + 128 + i * 22, s, font(13, QFont.Weight.Medium), CREAM)
    text(p, tx, y + 214, "Menlo", font(15, QFont.Weight.Bold, "Menlo"), CORAL)
    text(p, tx, y + 234, 'say "hello!"', font(12, QFont.Weight.Normal, "Menlo"), MUTED)

    # 07 code
    x, y = cols[0], rows[2]
    tile(p, x, y, tw, th, QColor("#f1efe7"), "LANGUAGE", "07", dark=False)
    card = QRectF((x + 70) * S, (y + 48) * S, 358 * S, 214 * S)
    p.setPen(QPen(QColor("#dcd9cc"), 1 * S))
    p.setBrush(QColor("#fffdf8"))
    p.drawRoundedRect(card, 12 * S, 12 * S)
    code = [[("teach ", "#c05d3d"), ("square length", "#141413")],
            [("  repeat ", "#c05d3d"), ("4 ", "#8e6bb5"), ("times", "#5a86b5")],
            [("    move ", "#c05d3d"), ("length", "#141413")],
            [("    turn ", "#c05d3d"), ("90", "#8e6bb5")],
            [("  end", "#c05d3d")], [("end", "#c05d3d")], [],
            [("do ", "#c05d3d"), ("square ", "#141413"), ("50", "#8e6bb5")]]
    f = font(13, QFont.Weight.Bold, "Menlo")
    fm = QFontMetricsF(f)
    for i, parts in enumerate(code):
        text(p, x + 90, y + 80 + i * 20, str(i + 1), font(10, QFont.Weight.Normal, "Menlo"),
             QColor("#b0aea5"))
        cx = (x + 116) * S
        for s, c in parts:
            p.setFont(f)
            p.setPen(QColor(c))
            p.drawText(QPointF(cx, (y + 80 + i * 20) * S), s)
            cx += fm.horizontalAdvance(s)

    # 08 live stage
    x = cols[1]
    path = QPainterPath()
    path.addRoundedRect(QRectF(x * S, y * S, tw * S, th * S), 14 * S, 14 * S)
    p.fillPath(path, INK)
    p.save()
    p.setClipPath(path)
    rec = spiral()
    ox, oy, k = x + tw / 2 + 60, y + th / 2 + 6, 0.62
    p.setPen(QPen(CORAL, 2.2 * S, cap=Qt.PenCapStyle.RoundCap))
    for x1, y1, x2, y2 in rec.segs:
        p.drawLine(QPointF((ox + x1 * k) * S, (oy - y1 * k) * S),
                   QPointF((ox + x2 * k) * S, (oy - y2 * k) * S))
    sx, sy, _ = rec.spr
    mascot(p, ox + sx * k, oy - sy * k, 11)
    p.restore()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(CORAL)
    p.drawEllipse(QPointF((x + 23) * S, (y + 22) * S), 4 * S, 4 * S)
    text(p, x + 32, y + 26, "RUNNING", font(9.5, QFont.Weight.Bold), CREAM, 1.6)
    text(p, x + 18, y + 250, "80 / 80", font(34, QFont.Weight.Black), CREAM, -1)
    text(p, x + 18, y + 272, "loops drawn", font(11, QFont.Weight.Medium), MUTED)
    text(p, x + tw - 28, y + th - 16, "08", font(9.5, QFont.Weight.Medium), MUTED)

    # 09 system
    x = cols[2]
    tile(p, x, y, tw, th, PANEL, "SYSTEM", "09")
    chips = [("say", CORAL), ("move", SKY), ("pen color", SAGE), ("repeat", CORAL),
             ("play note", SAGE)]
    cx = x + 18
    f = font(10.5, QFont.Weight.DemiBold)
    for s, c in chips:
        w = QFontMetricsF(f).horizontalAdvance(s) / S + 24
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c)
        p.drawRoundedRect(QRectF(cx * S, (y + 50) * S, w * S, 26 * S), 8 * S, 8 * S)
        text(p, cx + 12, y + 67, s, f, CREAM)
        cx += w + 8
    for i, (msg, pill, pc) in enumerate((
            ('say "Watch this!"', "Done ✓", SAGE),
            ('mvoe 20', 'Did you mean "move"?', CORAL))):
        ry = y + 108 + i * 64
        p.setPen(QPen(QColor("#33322e"), 1 * S))
        p.setBrush(QColor("#191817"))
        p.drawRoundedRect(QRectF((x + 18) * S, ry * S, (tw - 36) * S, 50 * S), 10 * S, 10 * S)
        text(p, x + 34, ry + 30, msg, font(12, QFont.Weight.Normal, "Menlo"), CREAM)
        pf = font(10, QFont.Weight.DemiBold)
        pw = QFontMetricsF(pf).horizontalAdvance(pill) / S + 22
        bg = QColor(pc)
        bg.setAlphaF(0.22)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(QRectF((x + tw - 34 - pw) * S, (ry + 12) * S, pw * S, 26 * S),
                          13 * S, 13 * S)
        text(p, x + tw - 34 - pw + 11, ry + 29, pill, pf, pc.lighter(125))

    p.end()
    out = os.path.join(ROOT, "assets", "brand-board.png")
    img.save(out)
    print("wrote", out)


if __name__ == "__main__":
    main()
