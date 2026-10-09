# Spark 3 building blocks: cards, icon buttons, pills, toasts, the update
# bar and the speed control. Icons are re-tinted whenever the theme changes
# (call retint(palette) on the window; every IconButton listens).

from PyQt6.QtCore import (QEasingCurve, QPoint, QPropertyAnimation, QSize, Qt,
                          QTimer, pyqtSignal)
from PyQt6.QtWidgets import (QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
                             QPushButton, QSizePolicy, QSlider, QToolButton,
                             QVBoxLayout, QWidget)

from . import icons

_tinted = []          # every IconButton / IconLabel, so a theme change can re-tint them
REDUCE_MOTION = {"on": False}


def retint(palette):
    alive = []
    for widget in _tinted:
        try:
            widget.apply_palette(palette)
            alive.append(widget)
        except RuntimeError:          # the C++ widget is gone
            pass
    _tinted[:] = alive


class IconButton(QToolButton):
    """A square icon button with a tooltip. role picks the icon color:
    'muted' (default), 'text', 'accent', 'danger'."""

    def __init__(self, name, tip="", size=18, checkable=False, role="muted", parent=None):
        super().__init__(parent)
        self.icon_name = name
        self.icon_size = size
        self.role = role
        self.setToolTip(tip)
        self.setAccessibleName(tip or name)
        self.setCheckable(checkable)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setIconSize(QSize(size, size))
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        _tinted.append(self)

    def set_icon_name(self, name, palette=None):
        self.icon_name = name
        if palette is not None:
            self.apply_palette(palette)

    def apply_palette(self, p):
        color = p.get(self.role, p["muted"])
        self.setIcon(icons.icon(self.icon_name, color, self.icon_size, active=p["accent"],
                                disabled=p["faint"]))


def text_button(text, icon=None, object_name=None, tip="", parent=None):
    button = QPushButton(text, parent)
    if object_name:
        button.setObjectName(object_name)
    if tip:
        button.setToolTip(tip)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if icon:
        button.icon_name = icon
        _tinted.append(_ButtonTint(button))
    return button


class _ButtonTint:
    """Keeps a QPushButton's icon in the right color for its style."""

    def __init__(self, button):
        self.button = button

    def apply_palette(self, p):
        name = self.button.objectName()
        color = p["accent_text"] if name in ("RunButton", "Primary") else \
            p["danger"] if name == "StopButton" else p["text"]
        self.button.setIcon(icons.icon(self.button.icon_name, color, 16, disabled=p["faint"]))
        self.button.setIconSize(QSize(16, 16))


class Card(QFrame):
    """A rounded surface with an optional header row (title + tool buttons)."""

    def __init__(self, title="", parent=None, margins=(0, 0, 0, 0)):
        super().__init__(parent)
        self.setObjectName("Card")
        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(1, 1, 1, 1)
        self.outer.setSpacing(0)
        self.header = QWidget()
        self.header.setObjectName("CardHeader")
        row = QHBoxLayout(self.header)
        row.setContentsMargins(12, 7, 7, 5)
        row.setSpacing(2)
        self.title = QLabel(title.upper())
        self.title.setObjectName("CardTitle")
        row.addWidget(self.title)
        row.addStretch(1)
        self.tools = row
        if not title:
            self.header.hide()
        self.outer.addWidget(self.header)
        self.body = QVBoxLayout()
        self.body.setContentsMargins(*margins)
        self.body.setSpacing(0)
        self.outer.addLayout(self.body, 1)

    def add_tool(self, widget):
        self.tools.addWidget(widget)
        return widget


class Pill(QLabel):
    """A small rounded status label; set_state('running'|'done'|'error'|'paused'|'')."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setObjectName("Pill")

    def set_state(self, state, text):
        self.setText(text)
        self.setProperty("state", state)
        self.style().unpolish(self)
        self.style().polish(self)


class Badge(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("Badge")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(14)
        self.hide()

    def show_count(self, text):
        if not text:
            self.hide()
            return
        self.setText(str(text))
        self.adjustSize()
        self.setFixedWidth(max(14, self.sizeHint().width()))
        parent = self.parentWidget()
        self.move(parent.width() - self.width() - 2, 2)
        self.raise_()
        self.show()


def fade_in(widget, ms=180):
    if REDUCE_MOTION["on"]:
        widget.show()
        return
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(ms)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.finished.connect(lambda: widget.setGraphicsEffect(None))
    widget.show()
    anim.start()


class Toasts:
    """Small messages that float above the bottom of the window and fade away."""

    def __init__(self, window):
        self.window = window
        self.label = QLabel(window)
        self.label.setObjectName("Toast")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.hide()
        self.timer = QTimer(window)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.label.hide)

    def show(self, text, ms=2200):
        self.label.setText(text)
        self.label.adjustSize()
        w = self.window
        bottom = w.height() - (w.statusBar().height() if hasattr(w, "statusBar") else 0)
        self.label.move((w.width() - self.label.width()) // 2, bottom - self.label.height() - 18)
        self.label.raise_()
        fade_in(self.label)
        self.timer.start(ms)


class UpdateBar(QWidget):
    """"Sparky X is ready — Restart to update", like other apps do it."""
    restart = pyqtSignal()
    notes = pyqtSignal()
    later = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("UpdateBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row = QHBoxLayout(self)
        row.setContentsMargins(14, 6, 10, 6)
        row.setSpacing(8)
        self.icon = QLabel()
        row.addWidget(self.icon)
        self.text = QLabel()
        row.addWidget(self.text, 1)
        self.notes_button = text_button("What's new", object_name="GhostButton")
        self.notes_button.clicked.connect(self.notes.emit)
        row.addWidget(self.notes_button)
        self.later_button = text_button("Later", object_name="GhostButton")
        self.later_button.clicked.connect(self.later.emit)
        row.addWidget(self.later_button)
        self.restart_button = text_button("Restart to update", object_name="Primary")
        self.restart_button.clicked.connect(self.restart.emit)
        row.addWidget(self.restart_button)
        self.hide()
        _tinted.append(self)

    def apply_palette(self, p):
        self.icon.setPixmap(icons.pixmap("update", p["accent"], 18))

    def ready(self, version):
        self.text.setText(f"<b>Sparky {version}</b> is ready. Restart to start using it — "
                          "your files stay open.")
        self.restart_button.show()
        fade_in(self)


class SpeedControl(QWidget):
    """Turtle — slider — rabbit. Values 1 (slow) to 10 (instant)."""
    valueChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        self.turtle = QLabel()
        self.rabbit = QLabel()
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(1, 10)
        self.slider.setValue(5)
        self.slider.setFixedWidth(96)
        self.slider.setToolTip("How fast Sparky programs run (1 slow – 10 instant)")
        self.slider.setAccessibleName("Speed")
        self.slider.valueChanged.connect(self.valueChanged.emit)
        row.addWidget(self.turtle)
        row.addWidget(self.slider)
        row.addWidget(self.rabbit)
        _tinted.append(self)

    def apply_palette(self, p):
        self.turtle.setPixmap(icons.pixmap("turtle", p["muted"], 18))
        self.rabbit.setPixmap(icons.pixmap("rabbit", p["muted"], 18))

    def value(self):
        return self.slider.value()

    def setValue(self, value):
        self.slider.setValue(value)

    def setEnabled(self, on):
        self.slider.setEnabled(on)


class IconLabel(QLabel):
    def __init__(self, name, role="muted", size=18, parent=None):
        super().__init__(parent)
        self.icon_name, self.role, self.icon_size = name, role, size
        _tinted.append(self)

    def apply_palette(self, p):
        self.setPixmap(icons.pixmap(self.icon_name, p.get(self.role, p["muted"]), self.icon_size))


def hline():
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setObjectName("Rule")
    line.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return line


def slide_point(widget, start, end, ms=220):
    if REDUCE_MOTION["on"]:
        widget.move(end)
        return
    anim = QPropertyAnimation(widget, b"pos", widget)
    anim.setDuration(ms)
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.start()
    widget._slide = anim
    return anim


__all__ = ["IconButton", "IconLabel", "text_button", "Card", "Pill", "Badge", "Toasts",
           "UpdateBar", "SpeedControl", "fade_in", "retint", "hline", "slide_point", "QPoint",
           "REDUCE_MOTION"]
