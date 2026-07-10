# The Sparky code editor: line numbers, syntax colors, autocomplete,
# auto-indent, and soft highlights for the line that's running (blue)
# or the line with an error (orange).

import re

from PyQt6.QtCore import Qt, QRect, QSize, QStringListModel
from PyQt6.QtGui import (QColor, QFont, QFontMetricsF, QPainter,
                         QSyntaxHighlighter, QTextCharFormat, QTextCursor,
                         QTextFormat)
from PyQt6.QtWidgets import QCompleter, QPlainTextEdit, QTextEdit, QWidget

from ..lang.parser import STATEMENT_WORDS, HELPER_WORDS
from .theme import CODE_FONTS

COMMANDS = sorted(set(STATEMENT_WORDS))
HELPERS = sorted(set(HELPER_WORDS) | {"mod"})
BLOCK_OPENERS = ("repeat", "forever", "if", "teach", "else")

COMPLETIONS = sorted(set(COMMANDS + HELPERS) | {
    "pen down", "pen up", "pen color", "pen size", "turn left",
    "repeat until", "stop loop", "stop program", "else if",
})


class SparkyHighlighter(QSyntaxHighlighter):
    def __init__(self, document, palette):
        super().__init__(document)
        self.re_words = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")
        self.re_number = re.compile(r"(?<![\w.])-?\d+(\.\d+)?")
        self.re_string = re.compile(r'"[^"\n]*"?|\'[^\'\n]*\'?')
        self.set_palette(palette)

    def set_palette(self, palette):
        def fmt(color, bold=False, italic=False):
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            if bold:
                f.setFontWeight(QFont.Weight.Bold)
            if italic:
                f.setFontItalic(True)
            return f

        self.f_cmd = fmt(palette["syn_cmd"], bold=True)
        self.f_word = fmt(palette["syn_word"])
        self.f_str = fmt(palette["syn_str"])
        self.f_num = fmt(palette["syn_num"])
        self.f_com = fmt(palette["syn_com"], italic=True)
        self.rehighlight()

    def highlightBlock(self, text):
        # comments win over everything after their #
        comment_at = None
        in_string = None
        for i, ch in enumerate(text):
            if in_string:
                if ch == in_string:
                    in_string = None
            elif ch in "\"'":
                in_string = ch
            elif ch == "#":
                comment_at = i
                break
        code = text if comment_at is None else text[:comment_at]

        for m in self.re_number.finditer(code):
            self.setFormat(m.start(), m.end() - m.start(), self.f_num)
        for m in self.re_words.finditer(code):
            word = m.group().lower()
            if word in COMMANDS:
                self.setFormat(m.start(), m.end() - m.start(), self.f_cmd)
            elif word in HELPERS:
                self.setFormat(m.start(), m.end() - m.start(), self.f_word)
        for m in self.re_string.finditer(code):
            self.setFormat(m.start(), m.end() - m.start(), self.f_str)
        if comment_at is not None:
            self.setFormat(comment_at, len(text) - comment_at, self.f_com)


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.gutter_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_gutter(event)


class CodeEditor(QPlainTextEdit):
    def __init__(self, palette, parent=None):
        super().__init__(parent)
        self.setObjectName("Editor")
        self.palette_colors = palette
        self.running_line = None
        self.error_line = None
        self.completions_enabled = True

        self.set_font_size(15)

        self.gutter = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_gutter_width)
        self.updateRequest.connect(self.on_update_request)
        self.cursorPositionChanged.connect(self.refresh_highlights)
        self.update_gutter_width()

        self.highlighter = SparkyHighlighter(self.document(), palette)

        self.completer = QCompleter(QStringListModel(COMPLETIONS, self), self)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(
            QCompleter.CompletionMode.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.activated.connect(self.insert_completion)

    # ---------- font size / zoom ----------

    def set_font_size(self, size):
        size = max(10, min(28, size))
        font = QFont()
        font.setFamilies(CODE_FONTS)
        font.setPointSize(size)
        self.setFont(font)
        self.setTabStopDistance(QFontMetricsF(font).horizontalAdvance(" ") * 2)
        if hasattr(self, "gutter"):
            self.update_gutter_width()
            self.gutter.update()

    def zoom(self, delta):
        self.set_font_size(self.font().pointSize() + delta)

    # ---------- theming ----------

    def apply_palette(self, palette):
        self.palette_colors = palette
        self.highlighter.set_palette(palette)
        self.refresh_highlights()
        self.gutter.update()

    # ---------- gutter ----------

    def gutter_width(self):
        digits = max(2, len(str(self.blockCount())))
        return 18 + self.fontMetrics().horizontalAdvance("9") * digits

    def update_gutter_width(self):
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def on_update_request(self, rect, dy):
        if dy:
            self.gutter.scroll(0, dy)
        else:
            self.gutter.update(0, rect.y(), self.gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_gutter_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        rect = self.contentsRect()
        self.gutter.setGeometry(
            QRect(rect.left(), rect.top(), self.gutter_width(), rect.height()))

    def paint_gutter(self, event):
        painter = QPainter(self.gutter)
        painter.fillRect(event.rect(), QColor(self.palette_colors["editor_bg"]))
        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block)
                    .translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        current = self.textCursor().blockNumber()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                is_current = number == current
                painter.setPen(QColor(self.palette_colors["text"] if is_current
                                      else self.palette_colors["gutter"]))
                painter.drawText(0, top, self.gutter.width() - 10,
                                 self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, str(number + 1))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            number += 1

    # ---------- line highlights ----------

    def set_running_line(self, line):
        if line != self.running_line:
            self.running_line = line
            self.refresh_highlights()

    def set_error_line(self, line):
        self.error_line = line
        self.refresh_highlights()
        if line is not None:
            block = self.document().findBlockByNumber(line - 1)
            if block.isValid():
                cursor = QTextCursor(block)
                self.setTextCursor(cursor)
                self.centerCursor()

    def refresh_highlights(self):
        selections = []

        def line_selection(line, color):
            block = self.document().findBlockByNumber(line - 1)
            if not block.isValid():
                return
            sel = QTextEdit.ExtraSelection()
            sel.format.setBackground(QColor(color))
            sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            sel.cursor = QTextCursor(block)
            sel.cursor.clearSelection()
            selections.append(sel)

        # soft highlight on the cursor's line
        sel = QTextEdit.ExtraSelection()
        sel.format.setBackground(QColor(self.palette_colors["line_hl"]))
        sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        sel.cursor = self.textCursor()
        sel.cursor.clearSelection()
        selections.append(sel)

        if self.running_line:
            line_selection(self.running_line, self.palette_colors["run_hl"])
        if self.error_line:
            line_selection(self.error_line, self.palette_colors["err_hl"])
        self.setExtraSelections(selections)
        self.gutter.update()

    # ---------- typing behavior ----------

    def keyPressEvent(self, event):
        popup = self.completer.popup()
        if popup.isVisible() and event.key() in (
                Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab,
                Qt.Key.Key_Escape, Qt.Key.Key_Up, Qt.Key.Key_Down):
            event.ignore()
            return

        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.auto_indent_newline()
            return
        if event.key() == Qt.Key.Key_Tab:
            self.insertPlainText("  ")
            return

        super().keyPressEvent(event)

        # typing an error away should clear the orange mark
        if self.error_line is not None and event.text():
            self.set_error_line(None)

        self.maybe_complete(event)

    def auto_indent_newline(self):
        cursor = self.textCursor()
        line = cursor.block().text()
        indent = line[:len(line) - len(line.lstrip())]
        first = line.strip().split(" ")[0].lower() if line.strip() else ""
        extra = "  " if first in BLOCK_OPENERS else ""
        cursor.insertText("\n" + indent + extra)
        self.setTextCursor(cursor)

    def current_word(self):
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        return cursor.selectedText()

    def maybe_complete(self, event):
        if not self.completions_enabled:
            self.completer.popup().hide()
            return
        if not event.text() or not (event.text().isalnum() or event.text() == "_"):
            self.completer.popup().hide()
            return
        word = self.current_word()
        if len(word) < 2:
            self.completer.popup().hide()
            return

        # complete keywords plus words already used in this program
        words = set(COMPLETIONS)
        words.update(w.lower() for w in
                     re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}",
                                self.toPlainText()))
        words.discard(word.lower())
        model = self.completer.model()
        model.setStringList(sorted(words))

        self.completer.setCompletionPrefix(word)
        if self.completer.completionCount() == 0:
            self.completer.popup().hide()
            return
        rect = self.cursorRect()
        rect.setWidth(self.completer.popup().sizeHintForColumn(0) + 24)
        self.completer.complete(rect)

    def insert_completion(self, text):
        cursor = self.textCursor()
        word = self.current_word()
        for _ in range(len(word)):
            cursor.deletePreviousChar()
        cursor.insertText(text)
        self.setTextCursor(cursor)

    # ---------- snippets from the block palette ----------

    def insert_snippet(self, snippet):
        cursor = self.textCursor()
        line = cursor.block().text()
        indent = line[:len(line) - len(line.lstrip())]
        at_line_start = cursor.positionInBlock() <= len(indent)

        text = snippet.replace("\n", "\n" + indent)
        if not at_line_start and line.strip():
            text = "\n" + indent + text
        cursor.insertText(text)
        self.setTextCursor(cursor)
        self.setFocus()
