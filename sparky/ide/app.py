# The Sparky IDE main window: blocks on the left, code in the middle,
# stage and console on the right. Native Qt all the way — no browser engine.

import html
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QSettings, QTimer
from PyQt6.QtGui import QAction, QFont, QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLabel,
                             QLineEdit, QMainWindow, QMenu, QMessageBox,
                             QPlainTextEdit, QPushButton, QSlider, QSplitter,
                             QVBoxLayout, QWidget)

from .blocks import BlockPalette
from .dialogs import (AboutDialog, CommunityDialog, ExtensionsDialog,
                      SettingsDialog, WelcomeDialog, open_site)
from .editor import CodeEditor
from .export import make_app
from .extension_manager import ExtensionManager
from .learn import LearnDialog
from .runner import RunnerThread
from .sounds import SoundBank
from .stage import StageModel, StageView
from .theme import LIGHT, DARK, build_qss, HEADING_FONTS

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"
ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets"

WELCOME = '''\
# Welcome to Sparky!
# Press the orange Run button and watch the stage.
# Then try changing the numbers and run it again!

speed 7
pen color "orange"
pen size 4

say "Watch this!"

repeat 12 times
  move 80
  turn left 150
end

say "Now you try!"
'''


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.palette_colors = LIGHT
        self.dark = False
        self.file_path = None
        self.runner = None
        self.learn_dialog = None
        self.settings = QSettings("Sparky", "Sparky")

        self.setWindowTitle("Sparky")
        self.resize(1320, 840)
        icon_path = ASSETS_DIR / "logo_256.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.sound_bank = SoundBank()
        self.extension_manager = ExtensionManager()
        self.extension_manager.discover()

        self.stage_model = StageModel()
        self.build_ui()
        self.load_settings()
        self.apply_theme()

        self.editor.setPlainText(WELCOME)
        self.editor.document().setModified(False)
        self.update_file_label()
        self.status.showMessage("Ready to spark! Press Run.")

        if self.settings.value("show_welcome", True, type=bool):
            QTimer.singleShot(250, self.show_welcome)

    # ---------- building the window ----------

    def build_ui(self):
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.setCentralWidget(root)

        root_layout.addWidget(self.build_header())

        self.editor = CodeEditor(self.palette_colors)
        self.editor.document().modificationChanged.connect(
            lambda _: self.update_file_label())

        self.blocks = BlockPalette(
            self.palette_colors, self.editor.insert_snippet,
            extra_categories=self.extension_manager.api.block_categories)
        self.blocks.setFixedWidth(230)

        right = QSplitter(Qt.Orientation.Vertical)
        self.stage = StageView(self.stage_model, self.palette_colors)
        stage_box = QWidget()
        stage_layout = QVBoxLayout(stage_box)
        stage_layout.setContentsMargins(0, 0, 0, 0)
        stage_layout.setSpacing(0)
        stage_title = QLabel("STAGE")
        stage_title.setObjectName("StageTitle")
        stage_layout.addWidget(stage_title)
        stage_layout.addWidget(self.stage, 1)
        right.addWidget(stage_box)
        right.addWidget(self.build_console())
        right.setSizes([520, 280])

        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(self.blocks)
        split.addWidget(self.editor)
        split.addWidget(right)
        split.setSizes([230, 520, 540])
        split.setCollapsible(1, False)
        root_layout.addWidget(split, 1)

        self.status = self.statusBar()
        self.cursor_label = QLabel("Ln 1, Col 1")
        self.cursor_label.setObjectName("FileLabel")
        self.status.addPermanentWidget(self.cursor_label)
        credit = QPushButton("⚡ by Mohith")
        credit.setObjectName("GhostButton")
        credit.setCursor(Qt.CursorShape.PointingHandCursor)
        credit.setToolTip("Visit Mohith's website")
        credit.clicked.connect(open_site)
        self.status.addPermanentWidget(credit)
        self.editor.cursorPositionChanged.connect(self.update_cursor_label)

        QShortcut(QKeySequence("Ctrl+Return"), self, self.run_program)
        QShortcut(QKeySequence("Meta+Return"), self, self.run_program)
        QShortcut(QKeySequence("Ctrl+="), self, lambda: self.editor.zoom(+1))
        QShortcut(QKeySequence("Ctrl+-"), self, lambda: self.editor.zoom(-1))
        QShortcut(QKeySequence("Ctrl+0"), self,
                  lambda: self.editor.set_font_size(15))

    def build_header(self):
        bar = QWidget()
        bar.setObjectName("HeaderBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 9, 14, 9)
        layout.setSpacing(8)

        title = QLabel("⚡ Sparky")
        title.setObjectName("AppTitle")
        layout.addWidget(title)

        self.file_label = QLabel("")
        self.file_label.setObjectName("FileLabel")
        layout.addWidget(self.file_label)
        layout.addStretch(1)

        def ghost(text, slot, shortcut=None, tip=""):
            b = QPushButton(text)
            b.setObjectName("GhostButton")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            if shortcut:
                b.setShortcut(QKeySequence(shortcut))
            if tip:
                b.setToolTip(tip)
            layout.addWidget(b)
            return b

        ghost("New", self.new_file, "Ctrl+N")
        ghost("Open", self.open_file, "Ctrl+O")
        ghost("Save", self.save_file, "Ctrl+S")

        self.examples_button = ghost("Examples ▾", self.show_examples)
        ghost("Learn", self.show_learn,
              tip="Lessons, challenges, and the language guide")
        self.more_button = ghost("More ▾", self.show_more_menu)
        self.theme_button = ghost("\U0001f319", self.toggle_theme,
                                  tip="Switch light/dark")

        speed_label = QLabel("Speed")
        speed_label.setObjectName("FileLabel")
        layout.addWidget(speed_label)
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 10)
        self.speed_slider.setValue(5)
        self.speed_slider.setFixedWidth(110)
        self.speed_slider.setToolTip("How fast programs run (1 slow – 10 instant)")
        self.speed_slider.valueChanged.connect(self.speed_changed)
        layout.addWidget(self.speed_slider)

        self.run_button = QPushButton("▶  Run")
        self.run_button.setObjectName("RunButton")
        self.run_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.run_button.setToolTip("Run your program (Cmd+Return)")
        self.run_button.clicked.connect(self.run_program)
        layout.addWidget(self.run_button)

        self.stop_button = QPushButton("■  Stop")
        self.stop_button.setObjectName("StopButton")
        self.stop_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_button.clicked.connect(self.stop_program)
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button)
        return bar

    def build_console(self):
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel("CONSOLE")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        self.console = QPlainTextEdit()
        self.console.setObjectName("Console")
        self.console.setReadOnly(True)
        layout.addWidget(self.console, 1)

        ask_row = QWidget()
        ask_layout = QHBoxLayout(ask_row)
        ask_layout.setContentsMargins(8, 6, 8, 8)
        self.ask_input = QLineEdit()
        self.ask_input.setObjectName("AskInput")
        self.ask_input.setPlaceholderText("answers show up here...")
        self.ask_input.setEnabled(False)
        self.ask_input.returnPressed.connect(self.send_answer)
        ask_layout.addWidget(self.ask_input)
        layout.addWidget(ask_row)
        return box

    # ---------- learn / more / settings ----------

    def show_learn(self):
        if self.learn_dialog is None:
            self.learn_dialog = LearnDialog(self)
        self.learn_dialog.show()
        self.learn_dialog.raise_()

    def show_more_menu(self):
        menu = QMenu(self)
        actions = [
            ("📦  Make an App…", lambda: make_app(self)),
            ("🧩  Extensions…", lambda: ExtensionsDialog(self).exec()),
            ("🌍  Community…", lambda: CommunityDialog(self).exec()),
            ("⚙️  Settings…", lambda: SettingsDialog(self).exec()),
            ("⚡  About Sparky…", lambda: AboutDialog(self).exec()),
        ]
        for label, slot in actions:
            action = QAction(label, menu)
            action.triggered.connect(lambda _=False, s=slot: s())
            menu.addAction(action)
        menu.exec(self.more_button.mapToGlobal(
            self.more_button.rect().bottomLeft()))

    def show_welcome(self):
        WelcomeDialog(self).exec()
        self.settings.setValue("show_welcome", False)

    def update_cursor_label(self):
        cursor = self.editor.textCursor()
        self.cursor_label.setText(
            f"Ln {cursor.blockNumber() + 1}, Col {cursor.positionInBlock() + 1}")

    def load_settings(self):
        self.dark = self.settings.value("dark", False, type=bool)
        self.speed_slider.setValue(self.settings.value("speed", 5, type=int))
        self.editor.set_font_size(
            self.settings.value("font_size", 15, type=int))
        self.editor.completions_enabled = self.settings.value(
            "autocomplete", True, type=bool)
        self.sound_bank.enabled = self.settings.value(
            "sounds", True, type=bool)
        self.sound_bank.volume = self.settings.value(
            "volume", 80, type=int) / 100
        geometry = self.settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

    def save_settings(self):
        self.settings.setValue("dark", self.dark)
        self.settings.setValue("speed", self.speed_slider.value())
        self.settings.setValue("font_size", self.editor.font().pointSize())
        self.settings.setValue("autocomplete",
                               self.editor.completions_enabled)
        self.settings.setValue("sounds", self.sound_bank.enabled)
        self.settings.setValue("volume", int(self.sound_bank.volume * 100))
        self.settings.setValue("geometry", self.saveGeometry())

    # ---------- theming ----------

    def apply_theme(self):
        self.palette_colors = DARK if self.dark else LIGHT
        QApplication.instance().setStyleSheet(build_qss(self.palette_colors))
        self.editor.apply_palette(self.palette_colors)
        self.stage.apply_palette(self.palette_colors)
        self.blocks.apply_palette(self.palette_colors)
        self.theme_button.setText("☀️" if self.dark else "\U0001f319")

    def toggle_theme(self):
        self.dark = not self.dark
        self.apply_theme()

    # ---------- console helpers ----------

    def console_write(self, text, color=None):
        color = color or self.palette_colors["text"]
        self.console.appendHtml(
            f'<span style="color:{color}">{html.escape(text)}</span>')
        scroll = self.console.verticalScrollBar()
        scroll.setValue(scroll.maximum())

    # ---------- files ----------

    def update_file_label(self):
        name = self.file_path.name if self.file_path else "untitled.spark"
        star = " •" if self.editor.document().isModified() else ""
        self.file_label.setText(name + star)
        self.setWindowTitle(f"{name}{star} — Sparky")

    def confirm_discard(self):
        if not self.editor.document().isModified():
            return True
        answer = QMessageBox.question(
            self, "Save your program?",
            "Your program has changes that aren't saved yet.\n"
            "Save before moving on?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Save:
            return self.save_file()
        return answer == QMessageBox.StandardButton.Discard

    def new_file(self):
        if not self.confirm_discard():
            return
        self.editor.setPlainText("")
        self.editor.document().setModified(False)
        self.file_path = None
        self.reset_run_view()
        self.update_file_label()

    def open_file(self):
        if not self.confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open a Sparky program", str(Path.home()),
            "Sparky programs (*.spark);;All files (*)")
        if path:
            self.load_path(Path(path))

    def load_path(self, path):
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as err:
            QMessageBox.warning(self, "Couldn't open",
                                f"I couldn't open that file:\n{err}")
            return
        self.editor.setPlainText(source)
        self.editor.document().setModified(False)
        self.file_path = path
        self.reset_run_view()
        self.update_file_label()
        self.status.showMessage(f"Opened {path.name}")

    def save_file(self):
        if self.file_path is None:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save your Sparky program",
                str(Path.home() / "my_program.spark"),
                "Sparky programs (*.spark)")
            if not path:
                return False
            if not path.endswith(".spark"):
                path += ".spark"
            self.file_path = Path(path)
        try:
            self.file_path.write_text(self.editor.toPlainText(),
                                      encoding="utf-8")
        except OSError as err:
            QMessageBox.warning(self, "Couldn't save",
                                f"I couldn't save the file:\n{err}")
            return False
        self.editor.document().setModified(False)
        self.update_file_label()
        self.status.showMessage(f"Saved {self.file_path.name} ✓")
        return True

    def show_examples(self):
        menu = QMenu(self)
        examples = sorted(EXAMPLES_DIR.glob("*.spark")) \
            if EXAMPLES_DIR.is_dir() else []
        if not examples:
            menu.addAction("No examples found").setEnabled(False)
        for path in examples:
            pretty = path.stem.replace("_", " ").title()
            action = QAction(pretty, menu)
            action.triggered.connect(
                lambda _=False, p=path: self.open_example(p))
            menu.addAction(action)
        menu.exec(self.examples_button.mapToGlobal(
            self.examples_button.rect().bottomLeft()))

    def open_example(self, path):
        if not self.confirm_discard():
            return
        self.load_path(path)
        self.file_path = None  # saving an example makes a copy
        self.update_file_label()

    # ---------- running ----------

    def reset_run_view(self):
        self.stage_model.reset()
        self.console.clear()
        self.editor.set_running_line(None)
        self.editor.set_error_line(None)
        self.ask_input.setEnabled(False)

    def run_program(self):
        if self.runner and self.runner.isRunning():
            return
        self.reset_run_view()
        self.runner = RunnerThread(self.editor.toPlainText(),
                                   self.stage_model,
                                   self.speed_slider.value())
        self.runner.sig_say.connect(self.console_write)
        self.runner.sig_ask.connect(self.on_ask)
        self.runner.sig_sound.connect(self.sound_bank.play)
        self.runner.sig_line.connect(self.editor.set_running_line)
        self.runner.sig_error.connect(self.on_error)
        self.runner.sig_done.connect(self.on_done)
        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status.showMessage("Running...")
        self.runner.start()

    def stop_program(self):
        if self.runner:
            self.runner.stop()
            self.status.showMessage("Stopped.")

    def speed_changed(self, value):
        if self.runner and self.runner.isRunning():
            self.runner.set_speed(value)

    def on_ask(self, prompt):
        self.console_write("❓ " + prompt,
                           self.palette_colors["accent2"])
        self.ask_input.setEnabled(True)
        self.ask_input.setFocus()

    def send_answer(self):
        if not (self.runner and self.runner.isRunning()):
            return
        if not self.ask_input.isEnabled():
            return
        text = self.ask_input.text()
        self.console_write("✏️ " + text,
                           self.palette_colors["muted"])
        self.ask_input.clear()
        self.ask_input.setEnabled(False)
        self.runner.answer(text)

    def on_error(self, message, line):
        self.console_write(message, self.palette_colors["accent"])
        if line:
            self.editor.set_error_line(line)
        self.status.showMessage("There's a little problem — "
                                "check the console.")

    def on_done(self, ok):
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.ask_input.setEnabled(False)
        # leave the last highlight for a moment, then fade it away
        QTimer.singleShot(600, lambda: self.editor.set_running_line(None))
        if ok:
            self.status.showMessage("Done ✓")

    # ---------- closing ----------

    def closeEvent(self, event):
        if self.runner and self.runner.isRunning():
            self.runner.stop()
            self.runner.wait(1000)
        if self.confirm_discard():
            self.save_settings()
            event.accept()
        else:
            event.ignore()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Sparky")
    icon_path = ASSETS_DIR / "logo_256.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    font = QFont()
    font.setFamilies(HEADING_FONTS)
    font.setPointSize(13)
    app.setFont(font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
