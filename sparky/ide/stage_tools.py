# Stage helpers for the IDE (Sparky 3): the sprites panel, the costume
# picker, answer buttons for `ask ... choices`, recording the stage as an
# animated GIF, and `speak` using the computer's voice.

import threading
import time

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton,
                             QTableWidget, QTableWidgetItem, QToolButton, QVBoxLayout, QWidget,
                             QHeaderView, QAbstractItemView)

from ..lang.interpreter import COSTUMES
from .gif import GifWriter, frame_from_qimage
from .stage import EMOJI_FONTS


class SpritesPanel(QWidget):
    """Every sprite on the stage with its x, y, size and costume (refreshes live)."""

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 0)
        self.table = QTableWidget(0, 5)
        self.table.setObjectName("SpritesTable")
        self.table.setHorizontalHeaderLabels(["Sprite", "", "x", "y", "size"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 5):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setMaximumHeight(130)
        self.table.setAccessibleName("Sprites")
        layout.addWidget(self.table)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.last = None

    def showEvent(self, event):
        self.refresh()
        self.timer.start(250)
        super().showEvent(event)

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def refresh(self):
        sprites = self.model.sprite_list()
        rows = [(s["name"], s["costume"] or "✦", f"{s['x']:.0f}", f"{s['y']:.0f}",
                 f"{s['scale'] * 100:.0f}%" + ("" if s["visible"] else " · hidden")) for s in sprites]
        if rows == self.last:
            return
        self.last = rows
        self.table.setRowCount(len(rows))
        emoji = QFont()
        emoji.setFamilies(EMOJI_FONTS)
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                item = QTableWidgetItem(value)
                if c == 1:
                    item.setFont(emoji)
                if c >= 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(r, c, item)


class CostumePicker(QDialog):
    """40 built-in costumes. Picking one inserts `costume "cat"` into your program."""
    picked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Costumes")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        title = QLabel("Pick a costume")
        title.setObjectName("Heading")
        layout.addWidget(title)
        hint = QLabel('It goes into your program as <b>costume "name"</b>. '
                      'Use it with <b>make sprite</b> or <b>tell</b>.')
        hint.setObjectName("CardText")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        grid = QGridLayout()
        grid.setSpacing(6)
        emoji = QFont()
        emoji.setFamilies(EMOJI_FONTS)
        emoji.setPixelSize(26)
        for i, (name, face) in enumerate(COSTUMES.items()):
            button = QToolButton()
            button.setText(f"{face}\n{name}")
            button.setToolTip(f'costume "{name}"')
            button.setAccessibleName(f"Costume {name}")
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            button.setFixedSize(76, 64)
            button.setObjectName("CostumeButton")
            button.clicked.connect(lambda _=False, n=name: (self.picked.emit(n), self.accept()))
            grid.addWidget(button, i // 8, i % 8)
        layout.addLayout(grid)
        sparky = QPushButton("Sparky himself")
        sparky.setObjectName("GhostButton")
        sparky.clicked.connect(lambda: (self.picked.emit("sparky"), self.accept()))
        row = QHBoxLayout()
        row.addWidget(sparky)
        row.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        row.addWidget(close)
        layout.addLayout(row)


class ChoiceBar(QWidget):
    """Answer buttons for `ask "..." choices [...]`."""
    chosen = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(8, 4, 8, 0)
        self.row.setSpacing(6)
        self.hide()

    def show_choices(self, choices):
        while self.row.count():
            item = self.row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, choice in enumerate(choices, 1):
            button = QPushButton(choice)
            button.setObjectName("Primary" if i == 1 else "GhostButton")
            button.setToolTip(f"Or type {i}")
            button.clicked.connect(lambda _=False, c=choice: self.pick(c))
            self.row.addWidget(button)
        self.row.addStretch(1)
        self.show()

    def pick(self, choice):
        self.hide()
        self.chosen.emit(choice)


class GifRecorder(QObject):
    """Records the stage at 12 frames a second (up to 30 seconds) and writes a GIF."""
    tick = pyqtSignal(float)              # seconds recorded so far
    saved = pyqtSignal(str)               # path
    failed = pyqtSignal(str)
    progress = pyqtSignal(int, int)

    FPS = 12
    LIMIT = 30.0

    def __init__(self, view, parent=None):
        super().__init__(parent)
        self.view = view
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.capture)
        self.writer = None
        self.started = 0.0
        self.encoding = False

    def recording(self):
        return self.timer.isActive()

    def start(self):
        self.writer = GifWriter(480, 360)
        self.started = time.monotonic()
        self.capture()
        self.timer.start(int(1000 / self.FPS))

    def capture(self):
        palette, indices = frame_from_qimage(self.view.render_image(scale=1))
        self.writer.add(palette, indices, int(100 / self.FPS))
        elapsed = time.monotonic() - self.started
        self.tick.emit(elapsed)
        if elapsed >= self.LIMIT:
            self.timer.stop()

    def stop(self):
        self.timer.stop()

    def save(self, path):
        """Encode in the background (it takes a few seconds), then write the file."""
        writer, self.writer = self.writer, None
        if writer is None or not writer.frames:
            self.failed.emit("Nothing was recorded.")
            return
        self.encoding = True

        def work():
            try:
                data = writer.encode(progress=lambda n, total: self.progress.emit(n, total))
                with open(path, "wb") as f:
                    f.write(data)
                self.saved.emit(str(path))
            except Exception as err:   # disk full, no permission...
                self.failed.emit(f"Couldn't save the GIF: {err}")
            finally:
                self.encoding = False

        threading.Thread(target=work, daemon=True).start()


class Speaker:
    """`speak "Hello"` with the computer's voice (Qt Text to Speech)."""

    def __init__(self):
        self.engine = None
        self.tried = False

    def available(self):
        if not self.tried:
            self.tried = True
            try:
                from PyQt6.QtTextToSpeech import QTextToSpeech
                engine = QTextToSpeech()
                if engine.state() != QTextToSpeech.State.Error:
                    self.engine = engine
            except Exception:
                self.engine = None
        return self.engine is not None

    def say(self, text, volume=1.0):
        if not self.available():
            return False
        self.engine.setVolume(max(0.0, min(1.0, volume)))
        self.engine.say(text)
        return True

    def stop(self):
        if self.engine is not None:
            self.engine.stop()
