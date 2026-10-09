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

from PyQt6.QtCore import Qt, QPointF, QRectF, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from . import mascot
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
    mouse_moved = pyqtSignal(object)          # (x, y) in stage coordinates, or None
    stage_clicked = pyqtSignal(float, float)

    def __init__(self, model, palette, parent=None):
        super().__init__(parent)
        self.model = model
        self.palette_colors = palette
        self.painted_version = -1
        self.show_grid = False
        self.frame_color = None
        self.mood = "happy"
        self.setMinimumSize(240, 180)
        self.setMouseTracking(True)
        self.setAccessibleName("Stage")

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.maybe_repaint)
        self.timer.start(33)

    def apply_palette(self, palette):
        self.palette_colors = palette
        self.painted_version = -1

    def maybe_repaint(self):
        if self.model.version != self.painted_version:
            self.update()

    def set_grid(self, on):
        self.show_grid = on
        self.update()

    def stage_geometry(self):
        zoom = min(self.width() / STAGE_W, self.height() / STAGE_H)
        stage_w, stage_h = STAGE_W * zoom, STAGE_H * zoom
        left = (self.width() - stage_w) / 2
        top = (self.height() - stage_h) / 2
        return QRectF(left, top, stage_w, stage_h), zoom

    def to_stage(self, pos):
        rect, zoom = self.stage_geometry()
        if not rect.contains(pos):
            return None
        return ((pos.x() - rect.center().x()) / zoom, (rect.center().y() - pos.y()) / zoom)

    def mouseMoveEvent(self, event):
        self.mouse_moved.emit(self.to_stage(event.position()))

    def leaveEvent(self, event):
        self.mouse_moved.emit(None)

    def mousePressEvent(self, event):
        point = self.to_stage(event.position())
        if point is not None:
            self.stage_clicked.emit(*point)

    def render_image(self, scale=2):
        """The stage as an image, 480×360 times scale, without the frame."""
        image = QImage(int(STAGE_W * scale), int(STAGE_H * scale), QImage.Format.Format_ARGB32)
        image.fill(QColor(self.palette_colors.get("stage_bg", "#ffffff")))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.paint_stage(painter, QRectF(0, 0, image.width(), image.height()), scale,
                         framed=False)
        painter.end()
        return image

    # ---------- painting ----------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(self.palette_colors.get("surface",
                                                                     self.palette_colors["panel"])))
        rect, zoom = self.stage_geometry()
        self.paint_stage(painter, rect, zoom)

    def paint_stage(self, painter, stage_rect, zoom, framed=True):
        with self.model.lock:
            segments = list(self.model.segments)
            stamps = list(self.model.stamps)
            texts = list(self.model.texts)
            background = self.model.background
            sprite = self.model.sprite
            bubble = self.model.bubble
            self.painted_version = self.model.version

        painter.save()
        if framed:
            path = QPainterPath()
            path.addRoundedRect(stage_rect, 10, 10)
            painter.setClipPath(path)
        bg = background or self.palette_colors.get("stage_bg", self.palette_colors["editor_bg"])
        painter.fillRect(stage_rect, QColor(bg))

        cx = stage_rect.center().x()
        cy = stage_rect.center().y()
        if self.show_grid and framed:
            self.paint_grid(painter, stage_rect, zoom, QColor(bg))

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

        painter.restore()
        if framed:
            painter.setPen(QPen(QColor(self.frame_color or self.palette_colors.get(
                "line", self.palette_colors["border"])), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(stage_rect, 10, 10)

    def paint_grid(self, painter, rect, zoom, bg):
        dark = bg.lightness() < 128
        minor = QColor(255, 255, 255, 22) if dark else QColor(0, 0, 0, 16)
        major = QColor(255, 255, 255, 70) if dark else QColor(0, 0, 0, 55)
        cx, cy = rect.center().x(), rect.center().y()
        font = QFont()
        font.setPixelSize(max(8, int(9 * min(zoom, 1.6))))
        painter.setFont(font)
        for value in range(-240, 241, 20):
            x = cx + value * zoom
            painter.setPen(QPen(major if value == 0 else minor, 1))
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            if value % 100 == 0 and value:
                painter.setPen(major)
                painter.drawText(QPointF(x + 3, cy - 4), str(value))
        for value in range(-180, 181, 20):
            y = cy - value * zoom
            painter.setPen(QPen(major if value == 0 else minor, 1))
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            if value % 100 == 0 and value:
                painter.setPen(major)
                painter.drawText(QPointF(cx + 4, y - 3), str(value))


    def draw_sprite(self, painter, pos, heading, zoom, ghost=False):
        """Sparky the spark, pointing wherever it's heading (heading 0 = up)."""
        mascot.draw(painter, pos, 13 * zoom, self.mood, heading=heading, ghost=ghost)

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


class StageWindow(QWidget):
    """The stage on its own, fullscreen (Esc or a click on the corner closes it)."""

    def __init__(self, model, palette):
        super().__init__(None, Qt.WindowType.Window)
        self.setWindowTitle("Sparky — Stage")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = StageView(model, palette, self)
        self.view.palette_colors = dict(palette, surface="#000000")
        self.view.frame_color = "#000000"
        layout.addWidget(self.view)
        self.setStyleSheet("background: #000000;")

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_F11):
            self.close()
        else:
            super().keyPressEvent(event)
