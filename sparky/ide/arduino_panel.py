# Sparky as an Arduino IDE (Sparky 3).
#
#   ArduinoPanel   the sidebar: board, port, Verify, Upload, Serial Monitor,
#                  Libraries, Boards, Examples, Pin maps, Sparky for Arduino
#   SerialCard     the Serial Monitor and Serial Plotter (right column)
#   dialogs        libraries, board packages, examples, pin maps
#
# Everything goes through arduino-cli (see sparky/arduino/cli.py). Slow calls
# run on worker threads and report back with Qt signals.

import math
import re
import tempfile
import threading
import time
from pathlib import Path

from PyQt6.QtCore import (QObject, QPointF, QProcess, QProcessEnvironment, QRectF, Qt,
                          QTimer, pyqtSignal)
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QHBoxLayout,
                             QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
                             QPlainTextEdit, QProgressBar, QPushButton, QStackedWidget,
                             QTabBar, QVBoxLayout, QWidget)

from ..arduino import cli as acli
from ..arduino.errors import explain, explain_upload
from ..arduino.translate import is_arduino_program, to_arduino
from ..lang import SparkyError
from ..paths import EXAMPLES_DIR
from .widgets import Card, IconButton, text_button

BAUDS = ["300", "1200", "2400", "4800", "9600", "19200", "38400", "57600", "74880",
         "115200", "230400", "250000", "500000", "1000000"]
ENDINGS = [("No line ending", ""), ("New line", "\n"), ("Carriage return", "\r"),
           ("Both NL & CR", "\r\n")]
SCRATCH = Path(tempfile.gettempdir()) / "sparky-arduino"
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


class Worker(QObject):
    """Run a slow function on a thread; deliver its answer on the main thread."""
    done = pyqtSignal(object, object)       # result, error (one is None)

    def __init__(self, fn, on_done, parent=None):
        super().__init__(parent)
        self.done.connect(on_done)
        threading.Thread(target=self._go, args=(fn,), daemon=True).start()

    def _go(self, fn):
        try:
            self.done.emit(fn(), None)
        except Exception as err:      # shown to the user as a friendly line
            self.done.emit(None, err)


def in_thread(owner, fn, on_done):
    worker = Worker(fn, on_done, owner)
    owner._workers = [w for w in getattr(owner, "_workers", []) if w is not worker] + [worker]
    return worker


# ---------- the sidebar ----------

class ArduinoPanel(QWidget):
    message = pyqtSignal(str)

    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.cli = None
        self.boards = []
        self.ports = []
        self.task = None               # QProcess for compile / upload
        self.task_kind = ""
        self.task_log = ""
        self.task_source = ""
        self.task_ino = None
        self.after_upload_monitor = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 10)
        layout.setSpacing(8)
        title = QLabel("ARDUINO")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        self.status = QLabel("Looking for Arduino tools…")
        self.status.setObjectName("CardText")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.setup_button = text_button("Set up Arduino (18 MB, once)", "update", "Primary",
                                        "Download Arduino's official arduino-cli into Sparky")
        self.setup_button.clicked.connect(self.set_up)
        self.setup_button.hide()
        layout.addWidget(self.setup_button)
        self.setup_bar = QProgressBar()
        self.setup_bar.hide()
        layout.addWidget(self.setup_bar)

        board_label = QLabel("Board")
        board_label.setObjectName("FieldLabel")
        layout.addWidget(board_label)
        self.board_box = QComboBox()
        self.board_box.setEditable(True)
        self.board_box.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.board_box.setAccessibleName("Board")
        self.board_box.setToolTip("Which board you're using. Type to search.")
        self.board_box.activated.connect(self.board_chosen)
        layout.addWidget(self.board_box)

        port_row = QHBoxLayout()
        port_label = QLabel("Port")
        port_label.setObjectName("FieldLabel")
        port_row.addWidget(port_label)
        port_row.addStretch(1)
        refresh = IconButton("refresh", "Look for boards again", size=15)
        refresh.clicked.connect(lambda: self.refresh_ports(manual=True))
        port_row.addWidget(refresh)
        layout.addLayout(port_row)
        self.port_box = QComboBox()
        self.port_box.setAccessibleName("Port")
        self.port_box.setToolTip("Where your board is plugged in")
        self.port_box.activated.connect(self.port_chosen)
        layout.addWidget(self.port_box)

        buttons = QHBoxLayout()
        self.verify_button = text_button("Verify", "check", "GhostButton",
                                         "Check that the code compiles (Ctrl/Cmd+R)")
        self.verify_button.clicked.connect(lambda: self.build(upload=False))
        self.upload_button = text_button("Upload", "send", "Primary",
                                         "Send the program to the board (F5)")
        self.upload_button.clicked.connect(lambda: self.build(upload=True))
        buttons.addWidget(self.verify_button)
        buttons.addWidget(self.upload_button)
        layout.addLayout(buttons)

        serial = QHBoxLayout()
        monitor = text_button("Serial Monitor", "console", "GhostButton",
                              "See what the board prints with Serial.println")
        monitor.clicked.connect(lambda: self.main.show_serial("monitor"))
        plotter = text_button("Plotter", "music", "GhostButton", "Draw the numbers the board prints")
        plotter.clicked.connect(lambda: self.main.show_serial("plotter"))
        serial.addWidget(monitor)
        serial.addWidget(plotter)
        layout.addLayout(serial)

        more = QHBoxLayout()
        for label, slot, tip in (("Libraries", self.open_libraries, "Find and install libraries"),
                                 ("Boards", self.open_boards, "Install board packages"),
                                 ("Examples", self.open_examples, "Example sketches"),
                                 ("Pins", self.open_pins, "Which pin is which")):
            b = QPushButton(label)
            b.setObjectName("LinkButton")
            b.setToolTip(tip)
            b.clicked.connect(slot)
            more.addWidget(b)
        layout.addLayout(more)

        self.sparky_box = QLabel(
            "<b>Sparky for Arduino</b><br>Write Sparky words like <code>pin 13 on</code>, "
            "<code>wait 1</code> and <code>forever</code> — Upload turns them into Arduino "
            "code for you.")
        self.sparky_box.setObjectName("CardText")
        self.sparky_box.setWordWrap(True)
        layout.addWidget(self.sparky_box)
        self.show_code = text_button("Show as Arduino", "code", "GhostButton",
                                     "See the Arduino code for this Sparky program")
        self.show_code.clicked.connect(self.show_as_arduino)
        layout.addWidget(self.show_code)
        layout.addStretch(1)

        self.port_timer = QTimer(self)
        self.port_timer.timeout.connect(self.refresh_ports)
        QTimer.singleShot(200, self.find_cli)

    # ---------- arduino-cli ----------

    def find_cli(self):
        in_thread(self, acli.ArduinoCLI.find, self.got_cli)

    def got_cli(self, found, error):
        self.cli = found
        if found is None:
            self.status.setText("Sparky needs Arduino's tools to talk to boards. If you "
                                "have Arduino IDE 2, Sparky uses it. If not, one click "
                                "sets them up:")
            self.setup_button.show()
            self.set_enabled(False)
            return
        self.setup_button.hide()
        self.status.setText(f"Using arduino-cli from {found.where()}.")
        self.set_enabled(True)
        self.load_boards()
        self.refresh_ports()

    def set_enabled(self, on):
        for w in (self.board_box, self.port_box, self.verify_button, self.upload_button):
            w.setEnabled(on)

    def set_up(self):
        if self.main.settings.value('offline',False,type=bool):
            self.status.setText('Offline mode is on. Arduino tools cannot be downloaded.'); return
        from ..arduino import download
        self.setup_button.setEnabled(False)
        self.setup_bar.show()
        self.setup_bar.setRange(0, 0)
        self.status.setText("Downloading arduino-cli from arduino.cc…")

        def work():
            path = download.install()
            found = acli.ArduinoCLI(path, acli.ide_config())
            try:
                found.core_update_index()
                if not any(c["installed"] for c in found.core_search("arduino:avr")):
                    found.core_install("arduino:avr")
            except acli.CLIError:
                pass            # boards can be installed later from Boards
            return found

        def done(found, error):
            self.setup_bar.hide()
            self.setup_button.setEnabled(True)
            if error:
                self.status.setText(f"Setup didn't finish: {error}. Check the internet "
                                    "connection and try again.")
                return
            self.message.emit("Arduino is set up ✓")
            self.got_cli(found, None)

        in_thread(self, work, done)

    # ---------- boards and ports ----------

    def load_boards(self):
        in_thread(self, self.cli.boards, self.got_boards)

    def got_boards(self, boards, error):
        if error:
            self.status.setText(f"Couldn't list boards: {error}")
            return
        self.boards = boards or []
        self.board_box.clear()
        for board in self.boards:
            self.board_box.addItem(board.name, board.fqbn)
        if not self.boards:
            self.status.setText("No board packages are installed yet. Press Boards to "
                                "install Arduino AVR (Uno, Nano, Mega).")
        self.restore_board()

    def restore_board(self):
        fqbn = self.main.settings.value(self.board_key(), "", type=str) or \
            self.main.settings.value("arduino/board", "arduino:avr:uno", type=str)
        index = self.board_box.findData(fqbn)
        if index >= 0:
            self.board_box.setCurrentIndex(index)

    def board_key(self):
        editor = self.main.editor
        path = editor.path if editor is not None else None
        return f"arduino/board/{path}" if path else "arduino/board"

    def board_chosen(self, _index=None):
        fqbn = self.fqbn()
        if fqbn:
            self.main.settings.setValue("arduino/board", fqbn)
            self.main.settings.setValue(self.board_key(), fqbn)

    def fqbn(self):
        text = self.board_box.currentText().strip()
        index = self.board_box.findText(text, Qt.MatchFlag.MatchFixedString)
        if index >= 0:
            return self.board_box.itemData(index)
        return self.board_box.currentData()

    def board_name(self):
        return self.board_box.currentText().strip() or "the board"

    def refresh_ports(self, manual=False):
        if self.cli is None or getattr(self, "_ports_busy", False):
            return
        self._ports_busy = True

        def done(ports, error):
            self._ports_busy = False
            if error:
                if manual:
                    self.message.emit(f"Couldn't look for boards: {error}")
                return
            self.got_ports(ports, manual)

        in_thread(self, self.cli.ports, done)

    def got_ports(self, ports, manual):
        old = self.port()
        new_addresses = [p.address for p in ports]
        if new_addresses == [p.address for p in self.ports] and not manual:
            return
        plugged = [p for p in ports if p.address not in {q.address for q in self.ports}
                   and p.looks_like_board()]
        self.ports = ports
        self.port_box.clear()
        for port in ports:
            self.port_box.addItem(port.title(), port.address)
        if not ports:
            self.port_box.addItem("No ports — plug in your board", "")
        index = self.port_box.findData(old) if old else -1
        if index < 0:
            index = self.port_box.findData(self.main.settings.value("arduino/port", "", type=str))
        if index < 0 and ports and ports[0].looks_like_board():
            index = 0
        if index >= 0:
            self.port_box.setCurrentIndex(index)
        for port in plugged:
            if port.boards and self.cli is not None and self.boards:
                b = self.board_box.findData(port.boards[0].fqbn)
                if b >= 0:
                    self.board_box.setCurrentIndex(b)
                    self.board_chosen()
            self.port_box.setCurrentIndex(self.port_box.findData(port.address))
            self.message.emit(f"Found {port.title()} 🔌")
        if manual:
            boards = sum(1 for p in ports if p.looks_like_board())
            self.message.emit(f"Found {boards} board{'s' if boards != 1 else ''}."
                              if boards else "No boards found. Plug one in with a USB cable.")

    def port_chosen(self, _index=None):
        if self.port():
            self.main.settings.setValue("arduino/port", self.port())

    def port(self):
        return self.port_box.currentData() or ""

    def showEvent(self, event):
        self.port_timer.start(3000)
        super().showEvent(event)

    def hideEvent(self, event):
        self.port_timer.stop()
        super().hideEvent(event)

    def watch_ports(self, on):
        if on:
            self.port_timer.start(3000)
        elif not self.isVisible():
            self.port_timer.stop()

    # ---------- Verify / Upload ----------

    def busy(self):
        return self.task is not None and self.task.state() != QProcess.ProcessState.NotRunning

    def sketch_source(self):
        """(Arduino code, the editor, is it translated from Sparky?) for the open file."""
        editor = self.main.editor
        if editor is None:
            return None, None, False
        text = editor.toPlainText()
        if editor.language.id == "sparky":
            return to_arduino(text), editor, True
        return text, editor, False

    def build(self, upload):
        if self.cli is None:
            self.main.show_sidebar_named("arduino")
            self.message.emit("Set up Arduino first (one click in the Arduino panel).")
            return
        if self.busy():
            self.message.emit("Hang on — Sparky is still talking to the board.")
            return
        fqbn = self.fqbn()
        if not fqbn:
            self.main.show_sidebar_named("arduino")
            self.message.emit("Pick your board first.")
            return
        if upload and not self.port():
            self.main.show_sidebar_named("arduino")
            self.message.emit("Plug in your board and pick its port first.")
            return
        try:
            code, editor, translated = self.sketch_source()
        except SparkyError as err:
            self.main.console_write(err.pretty(), self.main.palette_colors["danger"])
            if err.line and self.main.editor is not None:
                self.main.editor.set_error_line(err.line)
            self.main.set_state("error", "Oops — check the console")
            return
        if code is None:
            return
        path = editor.path
        if path is not None and not translated and editor.document().isModified():
            self.main.save_file(editor)
        if translated:      # the Arduino code made from a Sparky program
            stem = path.stem if path is not None else "sparky_program"
            folder, ino = acli.sketch_folder(Path(stem + ".ino"), code, SCRATCH / "sparky")
        else:
            folder, ino = acli.sketch_folder(path, code, SCRATCH / "sketches")
        self.task_source = code
        self.task_ino = ino
        self.task_kind = "upload" if upload else "verify"
        self.task_log = ""
        self.task_editor = editor
        self.task_translated = translated
        self.after_upload_monitor = False
        if upload and self.main.serial_card.is_open():
            self.after_upload_monitor = True
            self.main.serial_card.close_port()
        command = (self.cli.upload_command(folder, fqbn, self.port()) if upload
                   else self.cli.compile_command(folder, fqbn))
        self.main.reset_run_view()
        verb = "Uploading to" if upload else "Checking the code for"
        self.main.console_write(f"▶ {verb} {self.board_name()}…", self.main.palette_colors["muted"])
        self.main.set_state("running", "Uploading…" if upload else "Verifying…")
        self.main.set_running(True)
        self.task = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("NO_COLOR", "1")
        self.task.setProcessEnvironment(env)
        self.task.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.task.readyReadStandardOutput.connect(self.read_task)
        self.task.finished.connect(self.task_done)
        self.task.errorOccurred.connect(self.task_failed)
        self.task.start(command[0], command[1:])

    def read_task(self):
        text = ANSI.sub("", bytes(self.task.readAllStandardOutput()).decode("utf-8", "replace"))
        self.task_log += text
        for line in text.splitlines():
            if self.worth_showing(line):
                self.main.console_write(line, self.main.palette_colors["muted"])

    @staticmethod
    def worth_showing(line):
        """Upload progress yes; compiler noise, tables of paths and raw errors no."""
        text = line.strip()
        if not text or acli.SIZE_RE.search(text) or acli.RAM_RE.search(text):
            return False
        if "error" in text.lower() or text.startswith(("/", "In file included", "Used ",
                                                       "Error during build", "~", "^", "|")):
            return False
        if "/Arduino15/" in text or "\\Arduino15\\" in text or line.startswith(" "):
            return False
        return True

    def task_failed(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.main.console_write("Couldn't start arduino-cli.", self.main.palette_colors["danger"])
            self.finish(False)

    def task_done(self, code, _status):
        self.read_task()
        ok = code == 0
        colors = self.main.palette_colors
        size = acli.size_summary(self.task_log)
        if ok:
            if size:
                self.main.console_write(size, colors["muted"])
            if self.task_kind == "upload":
                self.main.console_write(f"✓ Uploaded to {self.board_name()}.", colors["success"])
                self.main.set_state("done", "Uploaded ✓")
                self.message.emit(f"Uploaded to {self.board_name()} ✓")
            else:
                self.main.console_write("✓ The code is ready for the board.", colors["success"])
                self.main.set_state("done", "Verified ✓")
        else:
            problems = explain(self.task_log, self.task_ino.name, self.task_source) \
                if self.task_ino else []
            in_sketch = [p for p in problems if p.line]
            if problems:
                for p in problems[:6]:
                    self.main.console_write(p.pretty(), colors["danger"])
                first = in_sketch[0] if in_sketch else None
                if first and not self.task_translated and self.task_editor is not None:
                    self.task_editor.set_error_line(first.line)
                missing = [p.library for p in problems if p.library]
                if missing:
                    self.offer_library(missing[0])
            else:
                friendly = explain_upload(self.task_log) if self.task_kind == "upload" else None
                tail = "\n".join(self.task_log.strip().splitlines()[-6:])
                self.main.console_write(friendly or tail, colors["danger"])
            self.main.set_state("error", "Upload didn't work" if self.task_kind == "upload"
                                else "The code has a problem — check the console")
            self.main.last_error = self.task_log[-2000:]
        self.finish(ok)

    def finish(self, ok):
        self.main.set_running(False)
        if self.after_upload_monitor:
            QTimer.singleShot(1200, self.main.serial_card.open_port)

    def stop(self):
        if self.busy():
            self.task.kill()
            self.main.console_write("■ Stopped.", self.main.palette_colors["muted"])

    def offer_library(self, name):
        answer = QMessageBox.question(self.main, "Install a library?",
                                      f"Your sketch needs the {name} library. Install it now?")
        if answer == QMessageBox.StandardButton.Yes:
            self.message.emit(f"Installing {name}…")
            in_thread(self, lambda: self.cli.lib_install(name),
                      lambda _r, err: self.message.emit(
                          f"Couldn't install {name}: {err}" if err else f"Installed {name} ✓ — "
                          "press Verify again"))

    def show_as_arduino(self):
        editor = self.main.editor
        if editor is None or editor.language.id != "sparky":
            self.message.emit("Show as Arduino works on Sparky programs.")
            return
        try:
            code = to_arduino(editor.toPlainText())
        except SparkyError as err:
            self.main.console_write(err.pretty(), self.main.palette_colors["danger"])
            if err.line:
                editor.set_error_line(err.line)
            return
        from . import languages
        name = (editor.path.stem if editor.path else Path(editor.display_name()).stem) + ".ino"
        self.main.new_tab(code, None, languages.BY_ID["arduino"], name)

    # ---------- dialogs ----------

    def need_cli(self):
        if self.cli is None:
            self.message.emit("Set up Arduino first (one click in the Arduino panel).")
            return False
        return True

    def open_libraries(self):
        if self.need_cli():
            LibraryDialog(self.cli, self.main).exec()

    def open_boards(self):
        if self.need_cli():
            BoardsDialog(self.cli, self.main).exec()
            self.load_boards()

    def open_examples(self):
        ExamplesDialog(self.cli, self.main).exec()

    def open_pins(self):
        PinMapDialog(self.main, self.fqbn() or "").exec()


# ---------- serial monitor + plotter ----------

class SerialCard(Card):
    def __init__(self, main_window):
        super().__init__("Serial")
        self.main = main_window
        self.process = None
        self.qt_port = None
        self.buffer = ""
        self.lines_seen = 0

        self.tab_bar = QTabBar()
        self.tab_bar.addTab("Monitor")
        self.tab_bar.addTab("Plotter")
        self.tab_bar.setDrawBase(False)
        self.tab_bar.currentChanged.connect(lambda i: self.stack.setCurrentIndex(i))
        self.add_tool(self.tab_bar)
        self.baud = QComboBox()
        self.baud.addItems(BAUDS)
        self.baud.setCurrentText(self.main.settings.value("arduino/baud", "9600", type=str))
        self.baud.setToolTip("Baud rate — must match Serial.begin() in your sketch")
        self.baud.activated.connect(self.baud_changed)
        self.add_tool(self.baud)
        self.connect_button = IconButton("play", "Connect to the board", size=15, checkable=True)
        self.connect_button.toggled.connect(self.toggle)
        self.add_tool(self.connect_button)
        copy = IconButton("copy", "Copy everything the board printed", size=15)
        copy.clicked.connect(self.copy_all)
        self.add_tool(copy)
        clear = IconButton("trash", "Clear", size=15)
        clear.clicked.connect(self.clear)
        self.add_tool(clear)
        close = IconButton("close", "Hide the Serial card", size=15)
        close.clicked.connect(self.hide_card)
        self.add_tool(close)

        self.stack = QStackedWidget()
        monitor = QWidget()
        col = QVBoxLayout(monitor)
        col.setContentsMargins(0, 0, 0, 0)
        self.output = QPlainTextEdit()
        self.output.setObjectName("Console")
        self.output.setReadOnly(True)
        self.output.setMaximumBlockCount(5000)
        self.output.setAccessibleName("Serial output")
        col.addWidget(self.output, 1)
        row = QHBoxLayout()
        row.setContentsMargins(8, 4, 8, 8)
        self.send_box = QLineEdit()
        self.send_box.setObjectName("AskInput")
        self.send_box.setPlaceholderText("send a message to the board…")
        self.send_box.returnPressed.connect(self.send)
        row.addWidget(self.send_box, 1)
        self.ending = QComboBox()
        for label, value in ENDINGS:
            self.ending.addItem(label, value)
        self.ending.setCurrentIndex(1)
        row.addWidget(self.ending)
        self.stamps = QCheckBox("Time")
        self.stamps.setToolTip("Show when each line arrived")
        row.addWidget(self.stamps)
        self.autoscroll = QCheckBox("Scroll")
        self.autoscroll.setChecked(True)
        row.addWidget(self.autoscroll)
        col.addLayout(row)
        self.stack.addWidget(monitor)
        self.plotter = Plotter()
        self.stack.addWidget(self.plotter)
        self.body.addWidget(self.stack, 1)
        self.body.setContentsMargins(8, 0, 8, 0)
        self.hide()

    # ---------- open / close ----------

    def show_tab(self, which):
        self.show()
        self.tab_bar.setCurrentIndex(1 if which == "plotter" else 0)
        if not self.is_open():
            self.connect_button.setChecked(True)

    def hide_card(self):
        self.close_port()
        self.hide()

    def is_open(self):
        if self.qt_port is not None:
            return self.qt_port.isOpen()
        return self.process is not None and self.process.state() != QProcess.ProcessState.NotRunning

    def toggle(self, on):
        if on:
            self.open_port()
        else:
            self.close_port()

    def baud_changed(self):
        self.main.settings.setValue("arduino/baud", self.baud.currentText())
        if self.is_open():
            self.close_port()
            self.open_port()

    def note(self, text):
        self.output.appendPlainText(f"— {text}")

    def open_port(self):
        panel = self.main.arduino_panel
        port = panel.port()
        if not port:
            self.note("Pick your board's port in the Arduino panel first.")
            self.set_button(False)
            return
        baud = int(self.baud.currentText())
        self.buffer = ""
        if self.open_qt(port, baud):
            self.note(f"Connected to {port} at {baud} baud.")
            self.set_button(True)
            return
        if panel.cli is None:
            self.note("Set up Arduino first (Arduino panel).")
            self.set_button(False)
            return
        command = panel.cli.monitor_command(port, panel.fqbn(), baud)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(
            lambda: self.received(bytes(self.process.readAllStandardOutput())))
        self.process.finished.connect(lambda *_: (self.set_button(False),
                                                  self.note("Disconnected.")))
        self.process.start(command[0], command[1:])
        self.note(f"Connected to {port} at {baud} baud.")
        self.set_button(True)

    def open_qt(self, port, baud):
        """Qt's own serial port when this build has it (faster, no extra process)."""
        try:
            from PyQt6.QtSerialPort import QSerialPort
        except ImportError:
            return False
        sp = QSerialPort(self)
        sp.setPortName(port)
        sp.setBaudRate(baud)
        if not sp.open(QSerialPort.OpenModeFlag.ReadWrite):
            self.note(f"Couldn't open {port}: {sp.errorString()}. Is Arduino IDE or another "
                      "program using it?")
            return True     # handled (with a message) — don't try the other way
        sp.readyRead.connect(lambda: self.received(bytes(sp.readAll())))
        sp.errorOccurred.connect(self.qt_error)
        self.qt_port = sp
        return True

    def qt_error(self, error):
        from PyQt6.QtSerialPort import QSerialPort
        if error in (QSerialPort.SerialPortError.ResourceError,
                     QSerialPort.SerialPortError.PermissionError):
            self.note("The board was unplugged (or the port closed).")
            self.close_port()

    def set_button(self, on):
        self.connect_button.blockSignals(True)
        self.connect_button.setChecked(on)
        self.connect_button.blockSignals(False)
        self.connect_button.set_icon_name("stop" if on else "play", self.main.palette_colors)
        self.connect_button.setToolTip("Disconnect" if on else "Connect to the board")

    def close_port(self):
        if self.qt_port is not None:
            if self.qt_port.isOpen():
                self.qt_port.close()
            self.qt_port.deleteLater()
            self.qt_port = None
        if self.process is not None:
            self.process.kill()
            self.process.waitForFinished(1000)
            self.process = None
        self.set_button(False)

    # ---------- data ----------

    def received(self, data):
        text = self.buffer + data.decode("utf-8", "replace").replace("\r\n", "\n").replace("\r", "\n")
        lines = text.split("\n")
        self.buffer = lines.pop()
        if not lines:
            return
        stamp = time.strftime("%H:%M:%S") + " → " if self.stamps.isChecked() else ""
        bar = self.output.verticalScrollBar()
        at_end = bar.value() >= bar.maximum() - 4
        for line in lines:
            self.output.appendPlainText(stamp + line)
            self.plotter.add_line(line)
        if self.autoscroll.isChecked() or at_end:
            bar.setValue(bar.maximum())

    def send(self):
        text = self.send_box.text()
        if not self.is_open():
            self.note("Connect first (the ▶ button).")
            return
        payload = (text + self.ending.currentData()).encode("utf-8")
        if self.qt_port is not None:
            self.qt_port.write(payload)
        elif self.process is not None:
            self.process.write(payload)
        self.output.appendPlainText(f"✏️ {text}")
        self.send_box.clear()

    def clear(self):
        self.output.clear()
        self.plotter.clear()

    def copy_all(self):
        from PyQt6.QtGui import QGuiApplication
        QGuiApplication.clipboard().setText(self.output.toPlainText())
        self.main.toast("Serial output copied ✓")


NUMBER = re.compile(r"^-?\d+(\.\d+)?([eE][-+]?\d+)?$")


class Plotter(QWidget):
    """Live lines for the numbers a board prints: "12 40", "12,40" or "temp:21 light:300"."""
    COLORS = ["#d97757", "#6a9bcc", "#788c5d", "#e0a526", "#8e7cc3", "#e58fb1", "#4cc2c4", "#8d6748"]
    KEEP = 400

    def __init__(self):
        super().__init__()
        self.series = {}        # label -> [values]
        self.setMinimumHeight(160)
        self.setAccessibleName("Serial plotter")
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(50)
        self.dirty = False

    def clear(self):
        self.series = {}
        self.update()

    def add_line(self, line):
        parts = [p for p in re.split(r"[\s,;\t]+", line.strip()) if p]
        values = []
        for i, part in enumerate(parts):
            label, _, number = part.rpartition(":")
            if not NUMBER.match(number):
                continue
            values.append((label or f"value {i + 1}", float(number)))
        if not values:
            return
        for label, value in values:
            data = self.series.setdefault(label, [])
            data.append(value)
            if len(data) > self.KEEP:
                del data[:len(data) - self.KEEP]
        self.dirty = True

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(44, 26, -12, -22)
        pal = self.window().palette()
        text_color = pal.color(pal.ColorRole.WindowText)
        muted = QColor(text_color)
        muted.setAlpha(110)
        if not self.series:
            painter.setPen(muted)
            painter.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignCenter,
                             "Print numbers with Serial.println and they'll show up here.\n"
                             'Several at once: Serial.print(a); Serial.print(" "); Serial.println(b);')
            return
        values = [v for data in self.series.values() for v in data]
        low, high = min(values), max(values)
        if high - low < 1e-9:
            low, high = low - 1, high + 1
        pad = (high - low) * 0.08
        low, high = low - pad, high + pad
        grid = QColor(text_color)
        grid.setAlpha(28)
        font = QFont()
        font.setPixelSize(10)
        painter.setFont(font)
        for i in range(5):
            y = rect.bottom() - rect.height() * i / 4
            painter.setPen(QPen(grid, 1))
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            painter.setPen(muted)
            value = low + (high - low) * i / 4
            painter.drawText(QRectF(0, y - 7, 40, 14), Qt.AlignmentFlag.AlignRight,
                             f"{value:.4g}")
        x = rect.left()
        window = max(60, max(len(d) for d in self.series.values()))   # fills the width, then scrolls
        for n, (label, data) in enumerate(self.series.items()):
            color = QColor(self.COLORS[n % len(self.COLORS)])
            if len(data) > 1:
                path = QPainterPath()
                step = rect.width() / (window - 1)
                start = rect.right() - step * (len(data) - 1)
                for i, v in enumerate(data):
                    pt = QPointF(start + step * i, rect.bottom() - (v - low) / (high - low) * rect.height())
                    path.moveTo(pt) if i == 0 else path.lineTo(pt)
                painter.setPen(QPen(color, 2))
                painter.drawPath(path)
            painter.setPen(color)
            label_text = f"● {label}: {data[-1]:.4g}"
            painter.drawText(QPointF(x, 16), label_text)
            x += painter.fontMetrics().horizontalAdvance(label_text) + 14


# ---------- dialogs ----------

class LibraryDialog(QDialog):
    def __init__(self, cli, parent):
        super().__init__(parent)
        self.cli = cli
        self.main = parent
        self.setWindowTitle("Libraries")
        self.resize(560, 520)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        title = QLabel("Arduino libraries")
        title.setObjectName("Heading")
        layout.addWidget(title)
        hint = QLabel("Libraries add new powers: screens, motors, sensors, LEDs. They're shared "
                      "with Arduino IDE.")
        hint.setObjectName("CardText")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setObjectName("Field")
        self.search.setPlaceholderText("Search: servo, neopixel, lcd, dht…")
        self.search.returnPressed.connect(self.find)
        row.addWidget(self.search, 1)
        go = QPushButton("Search")
        go.setObjectName("Primary")
        go.clicked.connect(self.find)
        row.addWidget(go)
        layout.addLayout(row)
        self.status = QLabel("")
        self.status.setObjectName("CardText")
        layout.addWidget(self.status)
        self.results = QListWidget()
        self.results.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results.currentItemChanged.connect(self.selected)
        layout.addWidget(self.results, 1)
        actions = QHBoxLayout()
        self.install = QPushButton("Install")
        self.install.setObjectName("Primary")
        self.install.setEnabled(False)
        self.install.clicked.connect(self.do_install)
        self.remove = QPushButton("Remove")
        self.remove.setObjectName("GhostButton")
        self.remove.setEnabled(False)
        self.remove.clicked.connect(self.do_remove)
        actions.addWidget(self.install)
        actions.addWidget(self.remove)
        actions.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        actions.addWidget(close)
        layout.addLayout(actions)
        self.installed = {}
        self.show_installed()

    def show_installed(self):
        self.status.setText("Installed libraries:")

        def done(found, error):
            if error:
                self.status.setText(f"Couldn't list libraries: {error}")
                return
            self.installed = found
            self.results.clear()
            for name, version in sorted(found.items(), key=lambda kv: kv[0].lower()):
                self.add_item(name, version, "installed")

        in_thread(self, self.cli.lib_installed, done)

    def add_item(self, name, version, sentence):
        mark = "✓ " if name in self.installed else ""
        item = QListWidgetItem(f"{mark}{name}  {version}\n{sentence}")
        item.setData(Qt.ItemDataRole.UserRole, name)
        self.results.addItem(item)

    def find(self):
        if self.main.settings.value('offline',False,type=bool):
            self.status.setText('Offline mode is on. Installed libraries still work.'); return
        query = self.search.text().strip()
        if not query:
            self.show_installed()
            return
        self.status.setText(f"Searching for “{query}”…")

        def done(found, error):
            if error:
                self.status.setText(f"Search didn't work: {error}")
                return
            self.results.clear()
            for lib in (found or [])[:80]:
                self.add_item(lib["name"], lib["version"], lib["sentence"])
            self.status.setText(f"{len(found or [])} found." if found else "Nothing found.")

        in_thread(self, lambda: self.cli.lib_search(query), done)

    def selected(self, item, _old=None):
        name = item.data(Qt.ItemDataRole.UserRole) if item else None
        self.install.setEnabled(bool(name))
        self.install.setText("Update" if name in self.installed else "Install")
        self.remove.setEnabled(name in self.installed)

    def current(self):
        item = self.results.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def do_install(self):
        if self.main.settings.value('offline',False,type=bool):
            self.status.setText('Offline mode is on. Downloads are paused.'); return
        name = self.current()
        if not name:
            return
        self.status.setText(f"Installing {name}…")
        self.install.setEnabled(False)

        def done(_r, error):
            self.status.setText(f"Couldn't install {name}: {error}" if error else f"Installed {name} ✓")
            if not error:
                self.installed[name] = "new"
            self.selected(self.results.currentItem())

        in_thread(self, lambda: self.cli.lib_install(name), done)

    def do_remove(self):
        name = self.current()
        if not name:
            return
        self.status.setText(f"Removing {name}…")

        def done(_r, error):
            self.status.setText(f"Couldn't remove {name}: {error}" if error else f"Removed {name}.")
            self.installed.pop(name, None)
            self.selected(self.results.currentItem())

        in_thread(self, lambda: self.cli.lib_uninstall(name), done)


BOARD_PACKAGES = [
    ("arduino:avr", "Arduino AVR", "Uno, Nano, Mega, Leonardo — the classic boards"),
    ("arduino:renesas_uno", "Arduino UNO R4", "UNO R4 Minima and WiFi"),
    ("arduino:mbed_rp2040", "Arduino RP2040", "Nano RP2040 Connect, Raspberry Pi Pico"),
    ("rp2040:rp2040", "Raspberry Pi Pico (Earle Philhower)", "Pico, Pico W, Pico 2 and more"),
    ("esp32:esp32", "ESP32 (Espressif)", "ESP32 boards with WiFi and Bluetooth"),
    ("esp8266:esp8266", "ESP8266", "NodeMCU, Wemos D1 mini"),
]


class BoardsDialog(QDialog):
    def __init__(self, cli, parent):
        super().__init__(parent)
        self.cli = cli
        self.setWindowTitle("Boards")
        self.resize(560, 460)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        title = QLabel("Board packages")
        title.setObjectName("Heading")
        layout.addWidget(title)
        hint = QLabel("Each package teaches Sparky (and Arduino IDE) a family of boards. "
                      "Installing one can take a few minutes.")
        hint.setObjectName("CardText")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.status = QLabel("Checking what's installed…")
        self.status.setObjectName("CardText")
        layout.addWidget(self.status)
        self.list = QListWidget()
        layout.addWidget(self.list, 1)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        layout.addWidget(self.progress)
        row = QHBoxLayout()
        self.install = QPushButton("Install")
        self.install.setObjectName("Primary")
        self.install.clicked.connect(self.do_install)
        row.addWidget(self.install)
        row.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        layout.addLayout(row)
        self.installed = {}
        self.refresh()

    def refresh(self):
        if self.main.settings.value('offline',False,type=bool):
            self.status.setText('Offline mode is on. Package checks and downloads are paused.')
            return
        urls = list(acli.EXTRA_INDEXES.values())

        def work():
            try:
                return {c["id"]: c["installed"] for c in self.cli.core_search("", urls) if c["installed"]}
            except acli.CLIError:
                return {c["id"]: c["installed"] for c in self.cli.core_search("")
                        if c["installed"]}

        def done(installed, error):
            self.installed = installed or {}
            self.list.clear()
            for core_id, name, about in BOARD_PACKAGES:
                version = self.installed.get(core_id)
                mark = f"✓ {name} {version}" if version else name
                item = QListWidgetItem(f"{mark}\n{about}")
                item.setData(Qt.ItemDataRole.UserRole, core_id)
                self.list.addItem(item)
            self.status.setText("Pick a package and press Install." if not error
                                else f"Couldn't check: {error}")

        in_thread(self, work, done)

    def do_install(self):
        if self.main.settings.value('offline',False,type=bool):
            self.status.setText('Offline mode is on. Downloads are paused.'); return
        item = self.list.currentItem()
        if item is None:
            self.status.setText("Pick a package first.")
            return
        core_id = item.data(Qt.ItemDataRole.UserRole)
        urls = self.cli.index_urls([core_id])
        self.status.setText(f"Installing {core_id}… this can take a few minutes.")
        self.progress.show()
        self.install.setEnabled(False)

        def work():
            self.cli.core_update_index(urls)
            return self.cli.core_install(core_id, urls)

        def done(_r, error):
            self.progress.hide()
            self.install.setEnabled(True)
            self.status.setText(f"Couldn't install: {error}" if error else f"Installed {core_id} ✓")
            self.refresh()

        in_thread(self, work, done)


class ExamplesDialog(QDialog):
    def __init__(self, cli, parent):
        super().__init__(parent)
        self.cli = cli
        self.main = parent
        self.setWindowTitle("Arduino examples")
        self.resize(520, 540)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        title = QLabel("Examples")
        title.setObjectName("Heading")
        layout.addWidget(title)
        self.search = QLineEdit()
        self.search.setObjectName("Field")
        self.search.setPlaceholderText("Filter…")
        self.search.textChanged.connect(self.filter)
        layout.addWidget(self.search)
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self.open_item)
        layout.addWidget(self.list, 1)
        row = QHBoxLayout()
        open_button = QPushButton("Open")
        open_button.setObjectName("Primary")
        open_button.clicked.connect(lambda: self.open_item(self.list.currentItem()))
        row.addWidget(open_button)
        row.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        row.addWidget(close)
        layout.addLayout(row)
        for path in sorted((EXAMPLES_DIR / "arduino").glob("*")):
            if path.suffix in (".ino", ".spark"):
                kind = "Sparky for Arduino" if path.suffix == ".spark" else "Sparky's examples"
                self.add(f"{kind} · {path.stem.replace('_', ' ')}", path)
        if cli is not None:
            in_thread(self, cli.lib_examples, self.got_library_examples)

    def add(self, label, path):
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, str(path))
        self.list.addItem(item)

    def got_library_examples(self, found, error):
        for library, name, folder in found or []:
            sketch = folder / f"{folder.name}.ino"
            if sketch.exists():
                self.add(f"{library} · {name}", sketch)

    def filter(self, text):
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def open_item(self, item):
        if item is None:
            return
        path = Path(item.data(Qt.ItemDataRole.UserRole))
        from . import languages
        lang = languages.language_for(path)
        # examples open as new, unsaved sketches, so the originals stay safe
        self.main.new_tab(path.read_text(encoding="utf-8", errors="replace"), None, lang, path.name)
        self.accept()


# ---------- pin maps ----------

UNO_TOP = ["SCL", "SDA", "AREF", "GND", "13", "12", "~11", "~10", "~9", "8",
           "7", "~6", "~5", "4", "~3", "2", "TX 1", "RX 0"]
UNO_BOTTOM = ["IOREF", "RESET", "3.3V", "5V", "GND", "GND", "VIN", "", "A0", "A1", "A2",
              "A3", "A4", "A5"]
NANO_LEFT = ["D13", "3V3", "REF", "A0", "A1", "A2", "A3", "A4", "A5", "A6", "A7", "5V", "RST",
             "GND", "VIN"]
NANO_RIGHT = ["D12", "~D11", "~D10", "~D9", "D8", "D7", "~D6", "~D5", "D4", "~D3", "D2", "GND",
              "RST", "RX0", "TX1"]
PICO_LEFT = ["GP0", "GP1", "GND", "GP2", "GP3", "GP4", "GP5", "GND", "GP6", "GP7", "GP8", "GP9",
             "GND", "GP10", "GP11", "GP12", "GP13", "GND", "GP14", "GP15"]
PICO_RIGHT = ["VBUS", "VSYS", "GND", "3V3_EN", "3V3", "ADC_VREF", "GP28 A2", "AGND", "GP27 A1",
              "GP26 A0", "RUN", "GP22", "GND", "GP21", "GP20", "GP19", "GP18", "GND", "GP17",
              "GP16"]


def pin_color(label):
    if "GND" in label:
        return "#141413"
    if any(k in label for k in ("5V", "3.3V", "3V3", "VIN", "VBUS", "VSYS", "IOREF")):
        return "#e5484d"
    if label.startswith("A") and label[1:2].isdigit() or " A" in label:
        return "#e0a526"
    if "~" in label:
        return "#8e7cc3"
    return "#6a9bcc"


class PinMap(QWidget):
    def __init__(self, board):
        super().__init__()
        self.board = board
        self.setMinimumSize(560, 330)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont()
        font.setPixelSize(10)
        font.setWeight(QFont.Weight.DemiBold)
        p.setFont(font)
        w, h = self.width(), self.height()
        if self.board == "uno":
            board = QRectF(40, 60, w - 80, h - 120)
            self.draw_board(p, board, "#00878f", "Arduino Uno")
            p.setBrush(QColor("#b8bcc2"))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(board.left() - 18, board.top() + 30, 50, 46), 4, 4)  # USB
            p.setBrush(QColor("#222"))
            p.drawRoundedRect(QRectF(board.left() - 12, board.bottom() - 70, 44, 40), 4, 4)  # power
            self.row(p, UNO_TOP, board.left() + 90, board.top() + 12, board.right() - 20, top=True)
            self.row(p, UNO_BOTTOM, board.left() + 140, board.bottom() - 26, board.right() - 20,
                     top=False)
            p.setPen(QColor("#ffffff"))
            p.drawText(QRectF(board.left(), board.center().y() - 10, board.width(), 20),
                       Qt.AlignmentFlag.AlignCenter, "LED_BUILTIN is pin 13  ·  ~ pins can fade (PWM)")
        else:
            left, right, name, color = ((PICO_LEFT, PICO_RIGHT, "Raspberry Pi Pico", "#2e7d32")
                                        if self.board == "pico" else
                                        (NANO_LEFT, NANO_RIGHT, "Arduino Nano", "#1f5fa8"))
            board = QRectF(w / 2 - 70, 20, 140, h - 40)
            self.draw_board(p, board, color, name)
            self.column(p, left, board.left(), board, side=-1)
            self.column(p, right, board.right(), board, side=1)
        p.end()

    def draw_board(self, p, rect, color, name):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color))
        p.drawRoundedRect(rect, 10, 10)
        p.setPen(QColor("#ffffff"))
        title = QFont()
        title.setPixelSize(15)
        title.setWeight(QFont.Weight.Bold)
        p.save()
        p.setFont(title)
        p.drawText(QRectF(rect.left(), rect.top() + rect.height() * 0.62, rect.width(), 22),
                   Qt.AlignmentFlag.AlignCenter, name)
        p.restore()

    def row(self, p, labels, x0, y, x1, top):
        step = (x1 - x0) / max(1, len(labels))
        for i, label in enumerate(labels):
            if not label:
                continue
            x = x0 + step * i + step / 2
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#1b1b1b"))
            p.drawRect(QRectF(x - 5, y - 5, 10, 10))
            p.setBrush(QColor(pin_color(label)))
            tag = QRectF(x - step / 2 + 1, y - 38 if top else y + 12, step - 2, 22)
            p.drawRoundedRect(tag, 5, 5)
            p.setPen(QColor("#ffffff"))
            p.drawText(tag, Qt.AlignmentFlag.AlignCenter, label)

    def column(self, p, labels, x, board, side):
        step = (board.height() - 20) / len(labels)
        for i, label in enumerate(labels):
            y = board.top() + 10 + step * i + step / 2
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#d6c27a"))
            p.drawEllipse(QPointF(x - side * 9, y), 4, 4)
            p.setBrush(QColor(pin_color(label)))
            tag = QRectF(x + 8 if side > 0 else x - 8 - 92, y - 9, 92, 18)
            p.drawRoundedRect(tag, 5, 5)
            p.setPen(QColor("#ffffff"))
            p.drawText(tag, Qt.AlignmentFlag.AlignCenter, label)


class PinMapDialog(QDialog):
    def __init__(self, parent, fqbn=""):
        super().__init__(parent)
        self.setWindowTitle("Pin maps")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        tabs = QTabBar()
        names = [("uno", "Uno"), ("nano", "Nano"), ("pico", "Pico")]
        for _key, label in names:
            tabs.addTab(label)
        layout.addWidget(tabs)
        self.map = PinMap("uno")
        layout.addWidget(self.map, 1)
        legend = QLabel('<span style="color:#6a9bcc">■</span> digital &nbsp; '
                        '<span style="color:#8e7cc3">■</span> can fade (~ PWM) &nbsp; '
                        '<span style="color:#e0a526">■</span> analog in &nbsp; '
                        '<span style="color:#e5484d">■</span> power &nbsp; ■ ground')
        legend.setObjectName("CardText")
        layout.addWidget(legend)

        def pick(i):
            self.map.board = names[i][0]
            self.map.update()

        tabs.currentChanged.connect(pick)
        start = 2 if "pico" in fqbn or "rp2040" in fqbn else 1 if "nano" in fqbn else 0
        tabs.setCurrentIndex(start)
        pick(start)
        self.resize(640, 460)
