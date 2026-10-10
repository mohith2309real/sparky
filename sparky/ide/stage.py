# The Sparky stage: where programs draw and sprites live.
#
# StageModel holds everything to draw, guarded by a lock (the interpreter
# writes from its worker thread). StageView repaints it ~30 times a second,
# but only when the model actually changed.
#
# Sparky 3: many sprites with emoji costumes, shapes and fills, dashed and
# see-through pens, styled text, backdrops, speech and thought bubbles on
# any sprite, keys / clicks / the mouse for `when` blocks, and a cached
# drawing layer so pictures with 100,000+ lines stay smooth.
#
# Stage coordinates match Scratch: (0,0) at the center, x right, y UP,
# heading 0 points up and turning right is clockwise.

import collections
import math
import random
import threading

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (QBrush, QColor, QFont, QImage, QLinearGradient, QPainter,
                         QPainterPath, QPen, QPolygonF, QRadialGradient)
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from . import mascot
from .theme import HEADING_FONTS

STAGE_W = 480
STAGE_H = 360
MAX_ITEMS = 400000
SPRITE_RADIUS = 18.0

EMOJI_FONTS = ["Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", "Twemoji Mozilla",
               "EmojiOne Color", "Symbola"]

PEN_STYLES = {"solid": Qt.PenStyle.SolidLine, "dashed": Qt.PenStyle.DashLine,
              "dotted": Qt.PenStyle.DotLine}

KEY_NAMES = {
    Qt.Key.Key_Space: "space", Qt.Key.Key_Left: "left", Qt.Key.Key_Right: "right",
    Qt.Key.Key_Up: "up", Qt.Key.Key_Down: "down", Qt.Key.Key_Return: "enter",
    Qt.Key.Key_Enter: "enter", Qt.Key.Key_Backspace: "backspace", Qt.Key.Key_Tab: "tab",
    Qt.Key.Key_Shift: "shift",
}


def key_name(event):
    if event.key() in KEY_NAMES:
        return KEY_NAMES[event.key()]
    text = event.text().lower()
    if len(text) == 1 and text.isprintable() and not text.isspace():
        return text
    return None


class StageModel:
    def __init__(self):
        self.lock = threading.RLock()      # re-entrant: helpers may lock inside a locked block
        self.version = 0
        self.epoch = 0                 # bumps when drawings are wiped (the view rebuilds its cache)
        self.listening = False         # a program is running: keys and clicks become events
        self.keys_down = set()
        self.mouse = (0.0, 0.0, False)
        self.queue = collections.deque()
        self.reset()

    def reset(self):
        with self.lock:
            self.items = []         # drawings, oldest first (see add_* for the shapes)
            self.background = None  # None = theme default
            self.backdrop = None    # a backdrop name or a picture path
            self.sprites = {"sparky": {"name": "sparky", "x": 0.0, "y": 0.0, "heading": 0.0,
                                       "visible": True, "scale": 1.0, "costume": None,
                                       "ghost": 0.0, "layer": 0}}
            self.bubbles = {}       # sprite name -> (kind, text)
            self.queue.clear()
            self.epoch += 1
            self.version += 1

    def bump(self):
        self.version += 1

    def _add(self, item):
        self.items.append(item)
        if len(self.items) > MAX_ITEMS:
            del self.items[:MAX_ITEMS // 2]
            self.epoch += 1
        self.bump()

    # ---------- drawing (called from the program's thread) ----------

    def add_line(self, x1, y1, x2, y2, pen):
        with self.lock:
            self._add(("L", x1, y1, x2, y2, pen["color"], pen["width"],
                       pen.get("style", "solid"), pen.get("opacity", 1.0)))

    def add_segment(self, x1, y1, x2, y2, color, width):
        self.add_line(x1, y1, x2, y2, {"color": color, "width": width})

    def add_shape(self, points, closed, pen, fill):
        with self.lock:
            self._add(("S", tuple(points), closed, pen["color"], pen["width"],
                       pen.get("style", "solid"), pen.get("opacity", 1.0), fill))

    def add_stamp(self, snapshot):
        with self.lock:
            self._add(("P", dict(snapshot)))

    def add_text(self, x, y, text, color, scale, style=None):
        style = style or {}
        with self.lock:
            self._add(("T", x, y, text, color, scale, style.get("size"),
                       bool(style.get("bold")), bool(style.get("italic"))))

    def set_sprite(self, snapshot):
        with self.lock:
            self.sprites[snapshot["name"]] = dict(snapshot)
            self.bump()

    def set_background(self, color):
        with self.lock:
            self.background = color
            self.bump()

    def set_backdrop(self, name):
        with self.lock:
            self.backdrop = None if name == "none" else name
            self.bump()

    def set_bubble(self, sprite, kind, text):
        with self.lock:
            if text:
                self.bubbles[sprite] = (kind, text)
            else:
                self.bubbles.pop(sprite, None)
            self.bump()

    def clear_drawings(self):
        with self.lock:
            self.items = []
            self.epoch += 1
            self.bump()

    @property
    def segments(self):
        """The lines drawn so far (Sparky 2 name)."""
        with self.lock:
            return [item for item in self.items if item[0] == "L"]

    def replay_frame(self):
        """What the stage looks like right now, for replaying the run later."""
        with self.lock:
            return (len(self.items), {n: dict(v) for n, v in self.sprites.items()},
                    dict(self.bubbles), self.background, self.backdrop, self.epoch)

    def sprite_list(self):
        with self.lock:
            return sorted((dict(s) for s in self.sprites.values()), key=lambda s: s["layer"])

    # ---------- input (called from the window) ----------

    def sprite_at(self, x, y):
        with self.lock:
            for s in sorted(self.sprites.values(), key=lambda s: -s["layer"]):
                if s["visible"] and math.hypot(s["x"] - x, s["y"] - y) <= SPRITE_RADIUS * s["scale"]:
                    return s["name"]
        return None

    def push_event(self, event):
        if self.listening:
            self.queue.append(event)
            if len(self.queue) > 200:
                self.queue.popleft()

    def drain_events(self):
        out = []
        while self.queue:
            out.append(self.queue.popleft())
        return out


# ---------- backdrops ----------



def _stars(count, seed):
    rnd = random.Random(seed)
    return [(rnd.uniform(-240, 240), rnd.uniform(-180, 180), rnd.uniform(0.5, 1.7),
             rnd.randint(110, 255)) for _ in range(count)]


STARS = _stars(110, 7)
NIGHT_STARS = _stars(45, 11)
_IMAGES = {}


def backdrop_image(path):
    if path not in _IMAGES:
        image = QImage(path)
        _IMAGES[path] = image if not image.isNull() else None
        if len(_IMAGES) > 12:
            _IMAGES.pop(next(iter(_IMAGES)))
    return _IMAGES[path]


def paint_backdrop(painter, rect, zoom, name):
    cx, cy = rect.center().x(), rect.center().y()

    def pt(x, y):
        return QPointF(cx + x * zoom, cy - y * zoom)

    def vertical(*stops):
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        for pos, color in stops:
            grad.setColorAt(pos, QColor(color))
        painter.fillRect(rect, QBrush(grad))

    painter.save()
    painter.setPen(Qt.PenStyle.NoPen)
    if name == "space":
        vertical((0, "#070b1f"), (0.6, "#141a40"), (1, "#24205a"))
        for x, y, r, a in STARS:
            painter.setBrush(QColor(255, 255, 255, a))
            painter.drawEllipse(pt(x, y), r * zoom, r * zoom)
        glow = QRadialGradient(pt(150, 95), 70 * zoom)
        glow.setColorAt(0, QColor(217, 119, 87, 120))
        glow.setColorAt(1, QColor(217, 119, 87, 0))
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(pt(150, 95), 70 * zoom, 70 * zoom)
        painter.setBrush(QColor("#d97757"))
        painter.drawEllipse(pt(150, 95), 18 * zoom, 18 * zoom)
    elif name == "night":
        vertical((0, "#0d1736"), (1, "#2b3d6b"))
        for x, y, r, a in NIGHT_STARS:
            if y > -60:
                painter.setBrush(QColor(255, 255, 240, a))
                painter.drawEllipse(pt(x, y), r * zoom, r * zoom)
        painter.setBrush(QColor("#f4efd6"))
        painter.drawEllipse(pt(-150, 115), 26 * zoom, 26 * zoom)
        painter.setBrush(QColor("#1a2850"))
        painter.drawEllipse(pt(-139, 122), 22 * zoom, 22 * zoom)
        hills = QPainterPath(pt(-240, -120))
        hills.cubicTo(pt(-120, -70), pt(0, -150), pt(120, -95))
        hills.cubicTo(pt(180, -75), pt(220, -100), pt(240, -110))
        hills.lineTo(pt(240, -180))
        hills.lineTo(pt(-240, -180))
        painter.setBrush(QColor("#111a33"))
        painter.drawPath(hills)
    elif name == "ocean":
        vertical((0, "#a9e2f7"), (0.35, "#4fa9d8"), (1, "#14507f"))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for i, y in enumerate((-40, -90, -140)):
            path = QPainterPath(pt(-240, y))
            for x in range(-240, 241, 10):
                path.lineTo(pt(x, y + 5 * math.sin((x + i * 37) / 24)))
            painter.setPen(QPen(QColor(255, 255, 255, 60), 2 * zoom))
            painter.drawPath(path)
        painter.setPen(Qt.PenStyle.NoPen)
        rnd = random.Random(3)
        for _ in range(14):
            painter.setBrush(QColor(255, 255, 255, 70))
            r = rnd.uniform(2, 6)
            painter.drawEllipse(pt(rnd.uniform(-230, 230), rnd.uniform(-170, 40)), r * zoom, r * zoom)
        painter.setBrush(QColor("#e8d29a"))
        sand = QPainterPath(pt(-240, -160))
        sand.cubicTo(pt(-100, -140), pt(80, -175), pt(240, -150))
        sand.lineTo(pt(240, -180))
        sand.lineTo(pt(-240, -180))
        painter.drawPath(sand)
    elif name == "grass":
        vertical((0, "#a9d8ff"), (0.62, "#e6f5ff"), (0.621, "#7cb342"), (1, "#4f7f2a"))
        painter.setBrush(QColor("#8cc152"))
        hill = QPainterPath(pt(-240, -45))
        hill.cubicTo(pt(-140, 10), pt(-40, -60), pt(60, -40))
        hill.cubicTo(pt(150, -20), pt(200, -55), pt(240, -45))
        hill.lineTo(pt(240, -180))
        hill.lineTo(pt(-240, -180))
        painter.drawPath(hill)
        painter.setBrush(QColor(255, 255, 255, 230))
        for x, y in ((-150, 120), (-120, 126), (120, 140), (150, 134)):
            painter.drawEllipse(pt(x, y), 22 * zoom, 13 * zoom)
        painter.setBrush(QColor("#f7c948"))
        painter.drawEllipse(pt(190, 140), 20 * zoom, 20 * zoom)
    elif name == "sunset":
        vertical((0, "#4b3b7a"), (0.45, "#e86f6f"), (0.72, "#ffb36b"), (0.721, "#3b2c4f"),
                 (1, "#241a33"))
        glow = QRadialGradient(pt(0, -80), 90 * zoom)
        glow.setColorAt(0, QColor(255, 220, 140, 255))
        glow.setColorAt(1, QColor(255, 220, 140, 0))
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(pt(0, -80), 90 * zoom, 90 * zoom)
        painter.setBrush(QColor("#ffd27a"))
        painter.drawPie(QRectF(pt(-45, -35), pt(45, -125)), 0, 180 * 16)
    elif name == "grid":
        painter.fillRect(rect, QColor("#fbfaf6"))
        for value in range(-240, 241, 20):
            painter.setPen(QPen(QColor(106, 155, 204, 90 if value % 100 else 150), 1))
            painter.drawLine(pt(value, -180), pt(value, 180))
        for value in range(-180, 181, 20):
            painter.setPen(QPen(QColor(106, 155, 204, 90 if value % 100 else 150), 1))
            painter.drawLine(pt(-240, value), pt(240, value))
    elif name:
        image = backdrop_image(name)
        if image is not None:
            scaled = image.size().scaled(QSize(int(rect.width()) + 1, int(rect.height()) + 1),
                                         Qt.AspectRatioMode.KeepAspectRatioByExpanding)
            target = QRectF(cx - scaled.width() / 2, cy - scaled.height() / 2,
                            scaled.width(), scaled.height())
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawImage(target, image)
    painter.restore()


def backdrop_is_dark(name):
    return name in ("space", "night", "sunset", "ocean")


class StageView(QWidget):
    mouse_moved = pyqtSignal(object)          # (x, y) in stage coordinates, or None
    stage_clicked = pyqtSignal(float, float)

    def __init__(self, model, palette, parent=None):
        super().__init__(parent)
        self.model = model
        self.palette_colors = palette
        self.painted_version = -1
        self.show_grid = False
        self.show_arrows = False
        self.frame_color = None
        self.stage_color = None        # None = follow the theme
        self.mood = "happy"
        self.cache = None
        self.cache_key = None
        self.cache_count = 0
        self.confetti = []
        self.replay = None             # a frame from replay_frame() while replaying
        self.setMinimumSize(240, 180)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setAccessibleName("Stage")

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.maybe_repaint)
        self.timer.start(33)
        self.confetti_timer = QTimer(self)
        self.confetti_timer.timeout.connect(self.step_confetti)

    def apply_palette(self, palette):
        self.palette_colors = palette
        self.painted_version = -1
        self.update()

    def maybe_repaint(self):
        if self.model.version != self.painted_version:
            self.update()

    def set_grid(self, on):
        self.show_grid = on
        self.update()

    def set_arrows(self, on):
        self.show_arrows = on
        self.update()

    def set_replay(self, frame):
        self.replay = frame
        self.update()

    def set_mood(self, mood):
        if mood != self.mood:
            self.mood = mood
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

    def background_color(self):
        return (self.model.background or self.stage_color
                or self.palette_colors.get("stage_bg", self.palette_colors.get("editor_bg", "#ffffff")))

    # ---------- input ----------

    def mouseMoveEvent(self, event):
        point = self.to_stage(event.position())
        if point is not None:
            self.model.mouse = (point[0], point[1], self.model.mouse[2])
        self.mouse_moved.emit(point)

    def leaveEvent(self, event):
        self.mouse_moved.emit(None)

    def mousePressEvent(self, event):
        point = self.to_stage(event.position())
        if point is None:
            return
        self.model.mouse = (point[0], point[1], True)
        hit = self.model.sprite_at(*point)
        if hit is not None:
            self.model.push_event(("click", hit))
        else:
            self.model.push_event(("stage_click", point[0], point[1]))
        self.stage_clicked.emit(*point)

    def mouseReleaseEvent(self, event):
        x, y, _ = self.model.mouse
        self.model.mouse = (x, y, False)

    def keyPressEvent(self, event):
        name = key_name(event)
        if name is None or not self.model.listening:
            super().keyPressEvent(event)
            return
        self.model.keys_down.add(name)
        self.model.push_event(("key", name))

    def keyReleaseEvent(self, event):
        if event.isAutoRepeat():
            return
        name = key_name(event)
        if name is not None:
            self.model.keys_down.discard(name)
        if not self.model.listening:
            super().keyReleaseEvent(event)

    def focusOutEvent(self, event):
        self.model.keys_down.clear()
        super().focusOutEvent(event)

    # ---------- exports ----------

    def render_image(self, scale=2):
        """The stage as an image, 480×360 times scale, without the frame."""
        image = QImage(int(STAGE_W * scale), int(STAGE_H * scale), QImage.Format.Format_ARGB32)
        image.fill(QColor(self.background_color()))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.paint_stage(painter, QRectF(0, 0, image.width(), image.height()), scale,
                         framed=False)
        painter.end()
        return image

    def save_svg(self, path):
        """The drawing as a vector picture (SVG)."""
        from PyQt6.QtCore import QRect
        from PyQt6.QtSvg import QSvgGenerator
        generator = QSvgGenerator()
        generator.setFileName(str(path))
        generator.setSize(QSize(STAGE_W, STAGE_H))
        generator.setViewBox(QRect(0, 0, STAGE_W, STAGE_H))
        generator.setTitle("Sparky drawing")
        generator.setDescription("Made with Sparky — sparky-code.web.app")
        painter = QPainter(generator)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(QRectF(0, 0, STAGE_W, STAGE_H), QColor(self.background_color()))
        self.paint_stage(painter, QRectF(0, 0, STAGE_W, STAGE_H), 1.0, framed=False)
        painter.end()
        return True

    # ---------- confetti ----------

    def celebrate(self, reduce_motion=False):
        if reduce_motion:
            return
        rect, _ = self.stage_geometry()
        colors = ["#d97757", "#6a9bcc", "#788c5d", "#f5c518", "#e58fb1", "#8e7cc3"]
        rnd = random.Random()
        self.confetti = []
        for _ in range(140):
            self.confetti.append([rnd.uniform(rect.left(), rect.right()), rect.top() - rnd.uniform(0, 80),
                                  rnd.uniform(-1.4, 1.4), rnd.uniform(1.5, 4.5), rnd.choice(colors),
                                  rnd.uniform(0, 360), rnd.uniform(-9, 9), rnd.uniform(4, 9)])
        self.confetti_ticks = 0
        self.confetti_timer.start(16)

    def step_confetti(self):
        self.confetti_ticks += 1
        for p in self.confetti:
            p[0] += p[2]
            p[1] += p[3]
            p[3] += 0.04
            p[5] += p[6]
        if self.confetti_ticks > 170:
            self.confetti = []
            self.confetti_timer.stop()
        self.update()

    def paint_confetti(self, painter):
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        fade = max(0.0, min(1.0, (170 - self.confetti_ticks) / 40))
        for x, y, _, _, color, angle, _, size in self.confetti:
            painter.save()
            painter.translate(x, y)
            painter.rotate(angle)
            c = QColor(color)
            c.setAlphaF(fade)
            painter.setBrush(c)
            painter.drawRect(QRectF(-size / 2, -size / 4, size, size / 2))
            painter.restore()
        painter.restore()

    # ---------- painting ----------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.fillRect(self.rect(), QColor(self.palette_colors.get("surface",
                                                                     self.palette_colors["panel"])))
        rect, zoom = self.stage_geometry()
        self.paint_stage(painter, rect, zoom)
        if self.confetti:
            self.paint_confetti(painter)

    def drawing_layer(self, rect, zoom):
        """The drawings as one cached image; only new drawings get painted each frame."""
        dpr = self.devicePixelRatioF()
        width, height = max(1, int(rect.width() * dpr)), max(1, int(rect.height() * dpr))
        with self.model.lock:
            key = (width, height, self.model.epoch)
            if key != self.cache_key:
                self.cache = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
                self.cache.setDevicePixelRatio(dpr)
                self.cache.fill(Qt.GlobalColor.transparent)
                self.cache_key = key
                self.cache_count = 0
            new = self.model.items[self.cache_count:]
            self.cache_count = len(self.model.items)
        if new:
            painter = QPainter(self.cache)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            local = QRectF(0, 0, rect.width(), rect.height())
            self.paint_items(painter, new, local, zoom)
            painter.end()
        return self.cache

    def paint_stage(self, painter, stage_rect, zoom, framed=True):
        replay = self.replay if framed else None
        with self.model.lock:
            if replay is not None and replay[5] == self.model.epoch:
                count, sprite_map, bubbles, background, backdrop, _ = replay
                sprites = sorted(sprite_map.values(), key=lambda s: s["layer"])
                items = self.model.items[:count]
            else:
                replay = None
                background = self.model.background
                backdrop = self.model.backdrop
                sprites = sorted((dict(s) for s in self.model.sprites.values()),
                                 key=lambda s: s["layer"])
                bubbles = dict(self.model.bubbles)
                items = None if framed else list(self.model.items)
            self.painted_version = self.model.version

        painter.save()
        if framed:
            path = QPainterPath()
            path.addRoundedRect(stage_rect, 10, 10)
            painter.setClipPath(path)
        bg = background or self.stage_color or self.palette_colors.get(
            "stage_bg", self.palette_colors["editor_bg"])
        painter.fillRect(stage_rect, QColor(bg))
        if backdrop:
            paint_backdrop(painter, stage_rect, zoom, backdrop)

        if self.show_grid and framed:
            dark = backdrop_is_dark(backdrop) or QColor(bg).lightness() < 128
            self.paint_grid(painter, stage_rect, zoom, dark)

        if framed and replay is None:
            painter.drawImage(stage_rect.topLeft(), self.drawing_layer(stage_rect, zoom))
        else:
            self.paint_items(painter, items, stage_rect, zoom)

        cx, cy = stage_rect.center().x(), stage_rect.center().y()
        for sprite in sprites:
            if not sprite["visible"]:
                continue
            pos = QPointF(cx + sprite["x"] * zoom, cy - sprite["y"] * zoom)
            self.draw_sprite(painter, pos, sprite, zoom)
            if self.show_arrows and framed:
                self.draw_arrow(painter, pos, sprite, zoom)
        for sprite in sprites:
            bubble = bubbles.get(sprite["name"])
            if bubble and sprite["visible"]:
                pos = QPointF(cx + sprite["x"] * zoom, cy - sprite["y"] * zoom)
                self.draw_bubble(painter, pos, bubble[1], zoom * sprite["scale"], stage_rect,
                                 think=bubble[0] == "think")

        painter.restore()
        if framed:
            painter.setPen(QPen(QColor(self.frame_color or self.palette_colors.get(
                "line", self.palette_colors["border"])), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(stage_rect, 10, 10)

    def paint_items(self, painter, items, rect, zoom):
        cx, cy = rect.center().x(), rect.center().y()

        def pt(x, y):
            return QPointF(cx + x * zoom, cy - y * zoom)

        text_font = QFont()
        text_font.setFamilies(HEADING_FONTS)
        for item in items:
            kind = item[0]
            if kind == "L":
                _, x1, y1, x2, y2, color, width, style, opacity = item
                c = QColor(color)
                if opacity < 1:
                    c.setAlphaF(opacity)
                pen = QPen(c, max(0.75, width * zoom))
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                if style != "solid":
                    pen.setStyle(PEN_STYLES.get(style, Qt.PenStyle.SolidLine))
                painter.setPen(pen)
                painter.drawLine(pt(x1, y1), pt(x2, y2))
            elif kind == "S":
                _, points, closed, color, width, style, opacity, fill = item
                poly = QPolygonF([pt(x, y) for x, y in points])
                if fill and closed:
                    fc = QColor(fill)
                    if opacity < 1:
                        fc.setAlphaF(opacity)
                    painter.setBrush(fc)
                else:
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                if width > 0:
                    c = QColor(color)
                    if opacity < 1:
                        c.setAlphaF(opacity)
                    pen = QPen(c, max(0.75, width * zoom))
                    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    if style != "solid":
                        pen.setStyle(PEN_STYLES.get(style, Qt.PenStyle.SolidLine))
                    painter.setPen(pen)
                else:
                    painter.setPen(Qt.PenStyle.NoPen)
                if closed:
                    painter.drawPolygon(poly)
                else:
                    painter.drawPolyline(poly)
            elif kind == "P":
                snapshot = item[1]
                pos = pt(snapshot["x"], snapshot["y"])
                self.draw_sprite(painter, pos, snapshot, zoom, stamp=True)
            elif kind == "T":
                _, x, y, text, color, scale, size, bold, italic = item
                text_font.setPointSizeF(max(5.0, (size or 13 * scale) * zoom))
                text_font.setWeight(QFont.Weight.Bold if bold else QFont.Weight.DemiBold)
                text_font.setItalic(italic)
                painter.setFont(text_font)
                painter.setPen(QColor(color))
                painter.drawText(pt(x, y), text)

    def paint_grid(self, painter, rect, zoom, dark):
        minor = QColor(255, 255, 255, 26) if dark else QColor(0, 0, 0, 16)
        major = QColor(255, 255, 255, 80) if dark else QColor(0, 0, 0, 55)
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
        painter.setPen(major)
        painter.drawText(QPointF(rect.right() - 14, cy - 4), "x")
        painter.drawText(QPointF(cx + 5, rect.top() + 12), "y")

    def draw_sprite(self, painter, pos, sprite, zoom, stamp=False):
        """Sparky (the mascot) or an emoji costume, turned to its heading."""
        scale = zoom * sprite.get("scale", 1.0)
        ghost = sprite.get("ghost", 0.0)
        costume = sprite.get("costume")
        painter.save()
        if ghost:
            painter.setOpacity(max(0.0, 1.0 - ghost / 100.0))
        if costume is None:
            mascot.draw(painter, pos, 13 * scale, self.mood, heading=sprite.get("heading", 0.0),
                        ghost=stamp)
        else:
            font = QFont()
            font.setFamilies(EMOJI_FONTS)
            font.setPixelSize(max(6, int(30 * scale)))
            painter.setFont(font)
            painter.translate(pos)
            painter.rotate(sprite.get("heading", 0.0))
            box = QRectF(-24 * scale, -24 * scale, 48 * scale, 48 * scale)
            painter.setPen(QColor("#141413"))
            painter.drawText(box, Qt.AlignmentFlag.AlignCenter, costume)
        painter.restore()

    def draw_arrow(self, painter, pos, sprite, zoom):
        heading = math.radians(sprite.get("heading", 0.0))
        length = (SPRITE_RADIUS * sprite.get("scale", 1.0) + 14) * zoom
        tip = QPointF(pos.x() + math.sin(heading) * length, pos.y() - math.cos(heading) * length)
        painter.save()
        pen = QPen(QColor("#d97757"), max(1.5, 2 * zoom))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(pos, tip)
        wing = 6 * zoom
        for side in (-1, 1):
            a = heading + math.pi + side * 0.5
            painter.drawLine(tip, QPointF(tip.x() + math.sin(a) * wing, tip.y() - math.cos(a) * wing))
        painter.restore()

    def draw_bubble(self, painter, pos, text, zoom, stage_rect, think=False):
        font = QFont()
        font.setFamilies(HEADING_FONTS)
        font.setPointSizeF(max(8.0, 11 * min(1.5, zoom)))
        painter.setFont(font)
        metrics = painter.fontMetrics()

        if len(text) > 60:
            text = text[:57] + "..."
        width = min(metrics.horizontalAdvance(text) + 22, 260.0)
        height = metrics.height() + 12

        x = pos.x() + 18 * zoom
        y = pos.y() - 26 * zoom - height
        x = min(max(stage_rect.left() + 4, x), stage_rect.right() - width - 4)
        y = max(stage_rect.top() + 4, y)
        rect = QRectF(x, y, width, height)

        painter.save()
        painter.setPen(QPen(QColor("#b0aea5"), 1.2))
        painter.setBrush(QColor("#faf9f5"))
        if think:
            painter.drawRoundedRect(rect, height / 2, height / 2)
            for i, r in enumerate((4.5, 3.0)):
                t = 0.45 + i * 0.3
                cx = rect.left() + width * 0.22 + (pos.x() - rect.left() - width * 0.22) * t
                cy = rect.bottom() + (pos.y() - 12 * zoom - rect.bottom()) * t
                painter.drawEllipse(QPointF(cx, cy), r, r)
        else:
            painter.drawRoundedRect(rect, 9, 9)
            tail = QPolygonF([
                QPointF(rect.left() + width * 0.25, rect.bottom() - 1),
                QPointF(rect.left() + width * 0.25 + 10, rect.bottom() - 1),
                QPointF(pos.x() + 6 * zoom, pos.y() - 14 * zoom),
            ])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPolygon(tail)
        painter.setPen(QColor("#5e5d59") if think else QColor("#141413"))
        if think:
            font.setItalic(True)
            painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()


class StageWindow(QWidget):
    """The stage on its own, fullscreen (Esc closes it)."""

    def __init__(self, model, palette, stage_color=None):
        super().__init__(None, Qt.WindowType.Window)
        self.setWindowTitle("Sparky — Stage")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = StageView(model, palette, self)
        self.view.palette_colors = dict(palette, surface="#000000")
        self.view.frame_color = "#000000"
        self.view.stage_color = stage_color
        layout.addWidget(self.view)
        self.setStyleSheet("background: #000000;")
        self.view.setFocus()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_F11):
            self.close()
        else:
            super().keyPressEvent(event)
