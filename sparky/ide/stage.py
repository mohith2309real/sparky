# The Sparky stage: where programs draw and the sprite lives.
#
# StageModel holds everything to draw, guarded by a lock (the interpreter
# writes from its worker thread). StageView repaints it ~30 times a second,
# but only when the model actually changed.
#
# Stage coordinates match Scratch: (0,0) at the center, x right, y UP,
# heading 0 points up and turning right is clockwise.

import math
import threading

from PyQt6.QtCore import Qt, QPointF, QRectF, QTimer
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import QWidget

from .theme import HEADING_FONTS

STAGE_W = 480
STAGE_H = 360
MAX_SEGMENTS = 60000


class StageModel:
    def __init__(self):
        self.lock = threading.Lock()
        self.version = 0
        self.reset()

    def reset(self):
        with self.lock:
            self.segments = []      # (x1, y1, x2, y2, color, width)
            self.stamps = []        # (x, y, heading, scale)
            self.texts = []         # (x, y, text, color, scale)
            self.background = None  # None = theme default
            self.sprite = (0.0, 0.0, 0.0, True, 1.0)  # x, y, heading, visible, scale
            self.bubble = None
            self.version += 1

    def bump(self):
        self.version += 1

    def add_segment(self, x1, y1, x2, y2, color, width):
        with self.lock:
            self.segments.append((x1, y1, x2, y2, color, width))
            if len(self.segments) > MAX_SEGMENTS:
                del self.segments[:MAX_SEGMENTS // 2]
            self.bump()

    def add_stamp(self, x, y, heading, scale):
        with self.lock:
            self.stamps.append((x, y, heading, scale))
            self.bump()

    def add_text(self, x, y, text, color, scale):
        with self.lock:
            self.texts.append((x, y, text, color, scale))
            self.bump()

    def set_sprite(self, x, y, heading, visible, scale):
        with self.lock:
            self.sprite = (x, y, heading, visible, scale)
            self.bump()

    def set_background(self, color):
        with self.lock:
            self.background = color
            self.bump()

    def set_bubble(self, text):
        with self.lock:
            self.bubble = text
            self.bump()

    def clear_drawings(self):
        with self.lock:
            self.segments = []
            self.stamps = []
            self.texts = []
            self.bump()


class StageView(QWidget):
    def __init__(self, model, palette, parent=None):
        super().__init__(parent)
        self.model = model
        self.palette_colors = palette
        self.painted_version = -1
        self.setMinimumSize(300, 240)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.maybe_repaint)
        self.timer.start(33)

    def apply_palette(self, palette):
        self.palette_colors = palette
        self.painted_version = -1

    def maybe_repaint(self):
        if self.model.version != self.painted_version:
            self.update()

    # ---------- painting ----------

    def paintEvent(self, event):
        with self.model.lock:
            segments = list(self.model.segments)
            stamps = list(self.model.stamps)
            texts = list(self.model.texts)
            background = self.model.background
            sprite = self.model.sprite
            bubble = self.model.bubble
            self.painted_version = self.model.version

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # fit the 480x360 stage inside the widget, keeping the aspect
        zoom = min(self.width() / STAGE_W, self.height() / STAGE_H)
        stage_w, stage_h = STAGE_W * zoom, STAGE_H * zoom
        left = (self.width() - stage_w) / 2
        top = (self.height() - stage_h) / 2
        stage_rect = QRectF(left, top, stage_w, stage_h)

        painter.fillRect(self.rect(), QColor(self.palette_colors["panel"]))

        path = QPainterPath()
        path.addRoundedRect(stage_rect, 12, 12)
        painter.setClipPath(path)
        bg = background or self.palette_colors["editor_bg"]
        painter.fillRect(stage_rect, QColor(bg))

        cx = left + stage_w / 2
        cy = top + stage_h / 2

        def to_screen(x, y):
            return QPointF(cx + x * zoom, cy - y * zoom)

        for x1, y1, x2, y2, color, width in segments:
            pen = QPen(QColor(color), max(0.75, width * zoom))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(to_screen(x1, y1), to_screen(x2, y2))

        for x, y, heading, scale in stamps:
            self.draw_sprite(painter, to_screen(x, y), heading,
                             zoom * scale, ghost=True)

        font = QFont()
        font.setFamilies(HEADING_FONTS)
        for x, y, text, color, scale in texts:
            font.setPointSizeF(max(6.0, 13 * zoom * scale))
            font.setWeight(QFont.Weight.DemiBold)
            painter.setFont(font)
            painter.setPen(QColor(color))
            painter.drawText(to_screen(x, y), text)

        sx, sy, heading, visible, scale = sprite
        if visible:
            pos = to_screen(sx, sy)
            self.draw_sprite(painter, pos, heading, zoom * scale)
            if bubble:
                self.draw_bubble(painter, pos, bubble, zoom * scale, stage_rect)

        painter.setClipping(False)
        painter.setPen(QPen(QColor(self.palette_colors["border"]), 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(stage_rect, 12, 12)

    def draw_sprite(self, painter, pos, heading, zoom, ghost=False):
        """Sparky the spark: a friendly coral drop with eyes, pointing
        wherever it's heading."""
        r = 14 * zoom
        painter.save()
        painter.translate(pos)
        painter.rotate(heading)  # heading 0 = up; Qt rotates clockwise
        painter.setOpacity(0.35 if ghost else 1.0)

        body = QColor("#d97757")
        outline = QColor("#b85c3f")

        # pointed nose (direction indicator)
        nose = QPolygonF([QPointF(0, -r * 1.7),
                          QPointF(-r * 0.55, -r * 0.55),
                          QPointF(r * 0.55, -r * 0.55)])
        painter.setPen(QPen(outline, max(1.0, 1.2 * zoom)))
        painter.setBrush(QBrush(body))
        painter.drawPolygon(nose)
        painter.drawEllipse(QPointF(0, 0), r, r)

        if not ghost:
            eye_r = r * 0.30
            pupil_r = eye_r * 0.55
            for side in (-1, 1):
                center = QPointF(side * r * 0.42, -r * 0.15)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#faf9f5"))
                painter.drawEllipse(center, eye_r, eye_r)
                painter.setBrush(QColor("#141413"))
                painter.drawEllipse(QPointF(center.x(), center.y() - eye_r * 0.2),
                                    pupil_r, pupil_r)
            # little smile
            painter.setPen(QPen(QColor("#141413"), max(1.0, 1.4 * zoom)))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(QRectF(-r * 0.35, r * 0.05, r * 0.7, r * 0.5),
                            210 * 16, 120 * 16)
        painter.restore()

    def draw_bubble(self, painter, pos, text, zoom, stage_rect):
        font = QFont()
        font.setFamilies(HEADING_FONTS)
        font.setPointSizeF(max(8.0, 11 * min(1.5, zoom)))
        painter.setFont(font)
        metrics = painter.fontMetrics()

        if len(text) > 60:
            text = text[:57] + "..."
        width = min(metrics.horizontalAdvance(text) + 20, 260.0)
        height = metrics.height() + 12

        x = pos.x() + 18 * zoom
        y = pos.y() - 26 * zoom - height
        x = min(max(stage_rect.left() + 4, x), stage_rect.right() - width - 4)
        y = max(stage_rect.top() + 4, y)
        rect = QRectF(x, y, width, height)

        painter.setPen(QPen(QColor("#b0aea5"), 1.2))
        painter.setBrush(QColor("#faf9f5"))
        painter.drawRoundedRect(rect, 9, 9)
        tail = QPolygonF([
            QPointF(rect.left() + width * 0.25, rect.bottom() - 1),
            QPointF(rect.left() + width * 0.25 + 10, rect.bottom() - 1),
            QPointF(pos.x() + 6 * zoom, pos.y() - 14 * zoom),
        ])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(tail)

        painter.setPen(QColor("#141413"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter,
                         text)
