# Crashes and logs (features 218-220). Unexpected Python errors are written
# to a log file and shown in a friendly window instead of closing Sparky.

import datetime
import logging
import logging.handlers
import platform
import sys
import traceback

from .. import __version__
from ..update.where import data_dir

_shown = {"count": 0}


def logs_dir():
    return data_dir() / "logs"


def setup_logging():
    folder = logs_dir()
    try:
        folder.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(folder / "sparky.log", maxBytes=512_000,
                                                       backupCount=3, encoding="utf-8")
    except OSError:
        return logging.getLogger("sparky")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log = logging.getLogger("sparky")
    log.setLevel(logging.INFO)
    if not log.handlers:
        log.addHandler(handler)
    log.info("Sparky %s started (Python %s, %s)", __version__, platform.python_version(),
             platform.platform())
    return log


def install_crash_handler(app):
    log = setup_logging()

    def hook(kind, value, tb):
        details = "".join(traceback.format_exception(kind, value, tb))
        log.error("Unexpected error:\n%s", details)
        if issubclass(kind, KeyboardInterrupt):
            app.quit()
            return
        _shown["count"] += 1
        if _shown["count"] > 3:          # don't bury the kid in windows
            return
        try:
            show_crash(details)
        except Exception:
            sys.__excepthook__(kind, value, tb)

    sys.excepthook = hook


def show_crash(details):
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QGuiApplication
    from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout
    from . import mascot
    from .widgets import text_button

    dialog = QDialog()
    dialog.setWindowTitle("Oops — Sparky tripped")
    dialog.resize(560, 440)
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(24, 20, 24, 18)
    face = QLabel()
    face.setPixmap(mascot.pixmap(72, "oops"))
    face.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(face)
    title = QLabel("Something went wrong inside Sparky")
    title.setObjectName("Heading")
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title)
    text = QLabel("It's not your fault. Your files are fine, and Sparky can usually keep going. "
                  "If it keeps happening, copy the details and send them to Mohith.")
    text.setWordWrap(True)
    text.setObjectName("Muted")
    layout.addWidget(text)
    box = QPlainTextEdit(f"Sparky {__version__} · {datetime.datetime.now():%Y-%m-%d %H:%M}\n\n{details}")
    box.setObjectName("Field")
    box.setReadOnly(True)
    layout.addWidget(box, 1)
    row = QHBoxLayout()
    copy = text_button("Copy details", icon="copy")
    copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(box.toPlainText()))
    row.addWidget(copy)
    row.addStretch(1)
    keep = text_button("Keep going", object_name="Primary")
    keep.clicked.connect(dialog.accept)
    row.addWidget(keep)
    layout.addLayout(row)
    dialog.exec()
