# Sparky the spark, drawn in vector so it's crisp at any size.
# Moods: happy, thinking, oops, wow. draw(painter, center, size, ...) paints
# it (pointing up, or toward `heading`); pixmap() gives a ready image.

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient

BODY = "#e0805f"
BODY_LIGHT = "#f2a585"
BODY_DARK = "#b85c3f"
INK = "#1d1b19"
EYE = "#fffdf8"
CHEEK = "#f6b3a0"
MOODS = ("happy", "thinking", "oops", "wow")


def body_path(r):
    """A rounded drop with a soft point on top (the spark's flame tip)."""
    path = QPainterPath()
    path.moveTo(0, -r * 1.75)
    path.cubicTo(r * 0.35, -r * 1.25, r * 1.0, -r * 0.75, r * 1.0, 0)
    path.cubicTo(r * 1.0, r * 0.62, r * 0.55, r * 1.0, 0, r * 1.0)
    path.cubicTo(-r * 0.55, r * 1.0, -r * 1.0, r * 0.62, -r * 1.0, 0)
    path.cubicTo(-r * 1.0, -r * 0.75, -r * 0.35, -r * 1.25, 0, -r * 1.75)
    return path


def draw(painter, center, size, mood="happy", heading=0.0, ghost=False, body=None):
    """size = the body's radius in pixels."""
    r = size
    painter.save()
    painter.translate(center)
    painter.rotate(heading)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    if ghost:
        painter.setOpacity(painter.opacity() * 0.35)
    color = QColor(body or BODY)
    grad = QRadialGradient(QPointF(-r * 0.35, -r * 0.45), r * 1.9)
    grad.setColorAt(0.0, color.lighter(118))
    grad.setColorAt(1.0, color.darker(108))
    painter.setPen(QPen(QColor(color.darker(135)), max(1.0, r * 0.07)))
    painter.setBrush(grad)
    painter.drawPath(body_path(r))
    if ghost:
        painter.restore()
        return

    # shine
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 255, 255, 80))
    painter.drawEllipse(QPointF(-r * 0.45, -r * 0.55), r * 0.16, r * 0.26)

    # face is drawn upright relative to the body
    look = {"thinking": (0.12, -0.12), "oops": (0.0, 0.05), "wow": (0, 0)}.get(mood, (0, 0.02))
    eye_r = r * 0.27
    for side in (-1, 1):
        c = QPointF(side * r * 0.38, -r * 0.12)
        painter.setBrush(QColor(EYE))
        painter.setPen(QPen(QColor(BODY_DARK), max(0.8, r * 0.03)))
        if mood == "wow":
            painter.drawEllipse(c, eye_r * 1.1, eye_r * 1.18)
        else:
            painter.drawEllipse(c, eye_r, eye_r * 1.06)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(INK))
        pupil = QPointF(c.x() + look[0] * r, c.y() + look[1] * r)
        pr = eye_r * (0.42 if mood == "wow" else 0.55)
        painter.drawEllipse(pupil, pr, pr)
        painter.setBrush(QColor(255, 255, 255, 230))
        painter.drawEllipse(QPointF(pupil.x() - pr * 0.35, pupil.y() - pr * 0.4), pr * 0.32, pr * 0.32)

    # cheeks
    painter.setBrush(QColor(CHEEK))
    for side in (-1, 1):
        painter.drawEllipse(QPointF(side * r * 0.66, r * 0.28), r * 0.14, r * 0.09)

    pen = QPen(QColor(INK), max(1.2, r * 0.085))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if mood == "happy":
        painter.drawArc(QRectF(-r * 0.28, r * 0.08, r * 0.56, r * 0.42), 200 * 16, 140 * 16)
    elif mood == "thinking":
        painter.drawLine(QPointF(-r * 0.12, r * 0.38), QPointF(r * 0.2, r * 0.32))
        # eyebrow raised
        painter.drawLine(QPointF(r * 0.22, -r * 0.5), QPointF(r * 0.55, -r * 0.58))
    elif mood == "oops":
        painter.setBrush(QColor(INK))
        painter.drawEllipse(QPointF(0, r * 0.38), r * 0.09, r * 0.11)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(QPointF(-r * 0.62, -r * 0.44), QPointF(-r * 0.26, -r * 0.58))
        painter.drawLine(QPointF(r * 0.62, -r * 0.44), QPointF(r * 0.26, -r * 0.58))
    elif mood == "wow":
        painter.setBrush(QColor("#7a2e1f"))
        painter.drawEllipse(QPointF(0, r * 0.4), r * 0.16, r * 0.2)
    painter.restore()


def pixmap(size_px, mood="happy", ratio=2.0, body=None):
    """A square image with Sparky centered (the drop fills about 70% of it)."""
    pm = QPixmap(int(size_px * ratio), int(size_px * ratio))
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    r = size_px * ratio * 0.27
    draw(painter, QPointF(size_px * ratio / 2, size_px * ratio * 0.6), r, mood, body=body)
    painter.end()
    pm.setDevicePixelRatio(ratio)
    return pm
