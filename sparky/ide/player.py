# The Sparky Player: runs a .spark program in its own window — stage,
# console, and Play/Stop. No editor. This is what "Make an App" apps use.

import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QLineEdit,
                             QMainWindow, QPlainTextEdit, QPushButton,
                             QSplitter, QVBoxLayout, QWidget)

from .runner import RunnerThread
from .sounds import SoundBank
from .stage import StageModel, StageView
from .theme import LIGHT, build_qss, HEADING_FONTS
from ..paths import ASSETS_DIR as ASSETS


class PlayerWindow(QMainWindow):
    def __init__(self, source, title):
        super().__init__()
        self.source = source
        self.runner = None
        self.palette_colors = LIGHT
        self.setWindowTitle(f"{title} — made with Sparky")
        self.resize(760, 720)

        self.stage_model = StageModel()
        self.sound_bank = SoundBank()

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setCentralWidget(root)

        header = QWidget()
        header.setObjectName("HeaderBar")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 8, 14, 8)
        name = QLabel(f"⚡ {title}")
        name.setObjectName("AppTitle")
        header_layout.addWidget(name)
        header_layout.addStretch(1)

        self.play_button = QPushButton("▶  Play again")
        self.play_button.setObjectName("RunButton")
        self.play_button.clicked.connect(self.play)
        header_layout.addWidget(self.play_button)
        self.stop_button = QPushButton("■  Stop")
        self.stop_button.setObjectName("StopButton")
        self.stop_button.clicked.connect(self.stop)
        header_layout.addWidget(self.stop_button)
        layout.addWidget(header)

        split = QSplitter(Qt.Orientation.Vertical)
        self.stage = StageView(self.stage_model, self.palette_colors)
        split.addWidget(self.stage)

        console_box = QWidget()
        console_layout = QVBoxLayout(console_box)
        console_layout.setContentsMargins(0, 0, 0, 0)
        console_layout.setSpacing(0)
        self.console = QPlainTextEdit()
        self.console.setObjectName("Console")
        self.console.setReadOnly(True)
        console_layout.addWidget(self.console, 1)
        self.ask_input = QLineEdit()
        self.ask_input.setObjectName("AskInput")
        self.ask_input.setPlaceholderText("answers show up here...")
        self.ask_input.setEnabled(False)
        self.ask_input.returnPressed.connect(self.send_answer)
        wrap = QWidget()
        wrap_layout = QHBoxLayout(wrap)
        wrap_layout.setContentsMargins(8, 6, 8, 8)
        wrap_layout.addWidget(self.ask_input)
        console_layout.addWidget(wrap)
        split.addWidget(console_box)
        split.setSizes([520, 180])
        layout.addWidget(split, 1)

        QTimer.singleShot(150, self.play)  # start automatically

    def play(self):
        if self.runner and self.runner.isRunning():
            return
        self.stage_model.reset()
        self.console.clear()
        self.runner = RunnerThread(self.source, self.stage_model, 5)
        self.runner.sig_say.connect(self.on_say)
        self.runner.sig_ask.connect(self.on_ask)
        self.runner.sig_sound.connect(self.sound_bank.play)
        self.runner.sig_error.connect(self.on_error)
        self.runner.sig_done.connect(self.on_done)
        self.play_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.runner.start()

    def stop(self):
        if self.runner:
            self.runner.stop()

    def on_say(self, text):
        self.console.appendPlainText(text)

    def on_ask(self, prompt):
        self.console.appendPlainText("❓ " + prompt)
        self.ask_input.setEnabled(True)
        self.ask_input.setFocus()

    def send_answer(self):
        if not (self.runner and self.runner.isRunning()
                and self.ask_input.isEnabled()):
            return
        text = self.ask_input.text()
        self.console.appendPlainText("✏️ " + text)
        self.ask_input.clear()
        self.ask_input.setEnabled(False)
        self.runner.answer(text)

    def on_error(self, message, _line):
        self.console.appendPlainText(message)

    def on_done(self, _ok):
        self.play_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.ask_input.setEnabled(False)

    def closeEvent(self, event):
        if self.runner and self.runner.isRunning():
            self.runner.stop()
            self.runner.wait(1000)
        event.accept()


def play_file(path):
    app = QApplication(sys.argv)
    app.setStyleSheet(build_qss(LIGHT))
    font = QFont()
    font.setFamilies(HEADING_FONTS)
    font.setPointSize(13)
    app.setFont(font)
    icon = ASSETS / "logo_256.png"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))

    path = Path(path)
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as err:
        print(f"Couldn't open {path}: {err}")
        sys.exit(1)
    title = path.stem.replace("_", " ").replace("program", "").strip() \
        or "My App"
    window = PlayerWindow(source, title.title())
    window.show()
    sys.exit(app.exec())
