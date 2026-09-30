# The Learn panel: 10 lessons, challenges, and the full language
# reference. Lessons load starter code straight into the editor.

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QListWidget, QPushButton,
                             QTextBrowser, QVBoxLayout)

from .lessons_data import LESSONS, REFERENCE_HTML


class LearnDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("Learn Sparky")
        self.setModal(False)  # keep it open while coding along
        self.resize(760, 540)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        self.list = QListWidget()
        self.list.setFixedWidth(210)
        for lesson in LESSONS:
            self.list.addItem(f"{lesson['emoji']}  {lesson['title']}")
        self.list.addItem("📖  Language reference")
        self.list.currentRowChanged.connect(self.show_lesson)
        layout.addWidget(self.list)

        right = QVBoxLayout()
        self.body = QTextBrowser()
        self.body.setOpenExternalLinks(True)
        right.addWidget(self.body, 1)

        self.try_button = QPushButton("✨  Try this code")
        self.try_button.setObjectName("RunButton")
        self.try_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.try_button.clicked.connect(self.load_code)
        right.addWidget(self.try_button)
        layout.addLayout(right, 1)

        self.list.setCurrentRow(0)

    def show_lesson(self, row):
        if 0 <= row < len(LESSONS):
            self.body.setHtml(LESSONS[row]["html"])
            self.try_button.setVisible(True)
        else:
            self.body.setHtml(REFERENCE_HTML)
            self.try_button.setVisible(False)

    def load_code(self):
        row = self.list.currentRow()
        if not (0 <= row < len(LESSONS)):
            return
        title = LESSONS[row]["title"].split(". ", 1)[-1]
        self.main_window.open_text(LESSONS[row]["code"], title)
        self.main_window.status.showMessage(
            "Lesson opened in a new tab — press Run, then make it your own!")
        self.main_window.raise_()
