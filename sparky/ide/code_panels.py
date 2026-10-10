# The Outline sidebar (your commands, events, sprites and functions — click
# to jump) and Find in all files (search the open folder).

import os
import re
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QPushButton, QVBoxLayout, QWidget)

from . import code_tools

KIND_MARKS = {"command": "◆", "event": "⚡", "sprite": "✦", "variable": "▪", "function": "ƒ",
              "class": "▣"}
SEARCH_SUFFIXES = {".spark", ".py", ".js", ".ino", ".c", ".cpp", ".h", ".hpp", ".html", ".css",
                   ".json", ".md", ".txt"}


class OutlinePanel(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 10)
        layout.setSpacing(6)
        title = QLabel("OUTLINE")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        self.hint = QLabel("Your commands, events, sprites and variables show up here. "
                           "Click one to jump to it.")
        self.hint.setObjectName("CardText")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        self.list = QListWidget()
        self.list.setAccessibleName("Outline")
        self.list.itemClicked.connect(self.jump)
        self.list.itemActivated.connect(self.jump)
        layout.addWidget(self.list, 1)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.refresh)
        self.watched = None

    def watch(self, editor):
        """Follow this editor's text."""
        if self.watched is not None:
            try:
                self.watched.textChanged.disconnect(self.timer.start)
            except TypeError:
                pass
        self.watched = editor
        if editor is not None:
            editor.textChanged.connect(self.timer.start)
        self.refresh()

    def showEvent(self, event):
        self.refresh()
        super().showEvent(event)

    def refresh(self):
        editor = self.watched
        self.list.clear()
        if editor is None:
            return
        items = code_tools.outline(editor.lines(), editor.language.id)
        for line, kind, name in items:
            item = QListWidgetItem(f"{KIND_MARKS.get(kind, '·')}  {name}")
            item.setToolTip(f"{kind} — line {line}")
            item.setData(Qt.ItemDataRole.UserRole, line)
            self.list.addItem(item)
        self.hint.setVisible(not items)

    def jump(self, item):
        line = item.data(Qt.ItemDataRole.UserRole)
        if self.watched is not None and line:
            self.watched.goto_line(int(line))


class FindInFilesDialog(QDialog):
    def __init__(self, main_window, folder, text=""):
        super().__init__(main_window)
        self.main = main_window
        self.folder = Path(folder)
        self.setWindowTitle("Find in all files")
        self.resize(640, 520)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        title = QLabel("Find in all files")
        title.setObjectName("Heading")
        layout.addWidget(title)
        where = QLabel(f"In {self.folder}")
        where.setObjectName("CardText")
        layout.addWidget(where)
        row = QHBoxLayout()
        self.box = QLineEdit(text)
        self.box.setObjectName("Field")
        self.box.setPlaceholderText("What are you looking for?")
        self.box.returnPressed.connect(self.search)
        row.addWidget(self.box, 1)
        self.case = QCheckBox("Aa")
        self.case.setToolTip("Match capital letters")
        row.addWidget(self.case)
        self.whole = QCheckBox("Whole word")
        row.addWidget(self.whole)
        go = QPushButton("Find")
        go.setObjectName("Primary")
        go.clicked.connect(self.search)
        row.addWidget(go)
        layout.addLayout(row)
        self.status = QLabel("")
        self.status.setObjectName("CardText")
        layout.addWidget(self.status)
        self.results = QListWidget()
        self.results.itemActivated.connect(self.open_result)
        self.results.itemDoubleClicked.connect(self.open_result)
        layout.addWidget(self.results, 1)
        if text:
            QTimer.singleShot(0, self.search)

    def search(self):
        text = self.box.text()
        self.results.clear()
        if not text:
            return
        flags = 0 if self.case.isChecked() else re.IGNORECASE
        body = re.escape(text)
        pattern = re.compile(rf"(?<!\w){body}(?!\w)" if self.whole.isChecked() else body, flags)
        hits = files = 0
        for path in self.walk():
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            found = False
            for n, line in enumerate(lines, 1):
                if pattern.search(line):
                    found = True
                    hits += 1
                    rel = path.relative_to(self.folder)
                    item = QListWidgetItem(f"{rel}:{n}    {line.strip()[:90]}")
                    item.setData(Qt.ItemDataRole.UserRole, (str(path), n))
                    self.results.addItem(item)
                    if hits >= 2000:
                        break
            files += found
            if hits >= 2000:
                break
        self.status.setText(f"{hits} match{'es' if hits != 1 else ''} in {files} file"
                            f"{'s' if files != 1 else ''}." if hits else "Nothing found.")

    def walk(self):
        skip = {".git", "node_modules", "__pycache__", ".venv", "build", "dist"}
        count = 0
        for root, dirs, names in os.walk(self.folder):
            dirs[:] = [d for d in dirs if d not in skip and not d.startswith(".")]
            for name in names:
                path = Path(root) / name
                if path.suffix.lower() in SEARCH_SUFFIXES:
                    count += 1
                    if count > 5000:
                        return
                    yield path

    def open_result(self, item):
        path, line = item.data(Qt.ItemDataRole.UserRole)
        editor = self.main.open_path(Path(path))
        if editor is None:
            editor = self.main.editor
        if editor is not None:
            editor.goto_line(line)
