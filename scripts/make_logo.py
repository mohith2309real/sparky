# Renders the Sparky logo: the coral spark mascot on a rounded cream tile.
# Run with: .venv/bin/python scripts/make_logo.py
# Writes assets/logo.png plus smaller sizes for icons.

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QImage, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import QApplication


def draw_logo(size):
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    s = size / 512.0  # design on a 512 grid

    # cream tile with soft corner radius
    tile = QPainterPath()
    tile.addRoundedRect(QRectF(16 * s, 16 * s, 480 * s, 480 * s), 110 * s, 110 * s)
    p.fillPath(tile, QColor("#faf9f5"))
    p.setPen(QPen(QColor("#e8e6dc"), 6 * s))
    p.drawPath(tile)

    # spark rays behind the mascot (sage + sky)
    p.setPen(Qt.PenStyle.NoPen)
    for angle, color, length in ((-38, "#6a9bcc", 74), (32, "#788c5d", 64),
                                 (145, "#6a9bcc", 60), (-150, "#788c5d", 70)):
        p.save()
        p.translate(256 * s, 250 * s)
        p.rotate(angle)
        ray = QPolygonF([QPointF(0, -170 * s),
                         QPointF(-16 * s, -(170 - length) * s - length * s),
                         QPointF(16 * s, -170 * s + 4 * s)])
        ray = QPolygonF([QPointF(-13 * s, -(150 + length) * s),
                         QPointF(13 * s, -(150 + length) * s),
                         QPointF(0, -150 * s)])
        p.setBrush(QColor(color))
        p.drawPolygon(ray)
        p.restore()

    # the mascot: nose + round body
    p.save()
    p.translate(256 * s, 268 * s)
    r = 120 * s
    body = QColor("#d97757")
    outline = QColor("#b85c3f")
    nose = QPolygonF([QPointF(0, -r * 1.7),
                      QPointF(-r * 0.55, -r * 0.55),
                      QPointF(r * 0.55, -r * 0.55)])
    p.setPen(QPen(outline, 10 * s))
    p.setBrush(QBrush(body))
    p.drawPolygon(nose)
    p.drawEllipse(QPointF(0, 0), r, r)

    # eyes
    for side in (-1, 1):
        c = QPointF(side * r * 0.42, -r * 0.15)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#faf9f5"))
        p.drawEllipse(c, r * 0.30, r * 0.30)
        p.setBrush(QColor("#141413"))
        p.drawEllipse(QPointF(c.x(), c.y() - r * 0.06), r * 0.165, r * 0.165)

    # smile
    p.setPen(QPen(QColor("#141413"), 12 * s, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(QRectF(-r * 0.35, r * 0.05, r * 0.7, r * 0.5),
              210 * 16, 120 * 16)
    p.restore()
    p.end()
    return image


def main():
    QApplication(sys.argv)
    out = os.path.join(os.path.dirname(__file__), "..", "assets")
    os.makedirs(out, exist_ok=True)
    for size, name in ((512, "logo.png"), (256, "logo_256.png"),
                       (128, "logo_128.png"), (64, "logo_64.png"),
                       (32, "logo_32.png")):
        draw_logo(size).save(os.path.join(out, name))
        print("wrote", name)


if __name__ == "__main__":
    main()
