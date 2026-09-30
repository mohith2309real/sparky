# The code editor: line numbers, syntax colors for every language Sparky
# knows, autocomplete (keywords, your own words, and VS Code snippets),
# auto-indent, comment toggling, and soft highlights for the line that's
# running (blue) or the line with an error (orange).

import re

from PyQt6.QtCore import Qt, QRect, QSize, QStringListModel
from PyQt6.QtGui import (QColor, QFont, QFontMetricsF, QPainter,
                         QSyntaxHighlighter, QTextCharFormat, QTextCursor,
                         QTextDocument, QTextFormat)
from PyQt6.QtWidgets import QCompleter, QPlainTextEdit, QTextEdit, QWidget

from .languages import BY_ID, language_for
from .theme import CODE_FONTS

SPARKY_PHRASES = {"pen down", "pen up", "pen color", "pen size", "turn left",
                  "repeat until", "stop loop", "stop program", "else if",
                  "for each", "give back", "play note"}
WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
NUMBER_RE = re.compile(r"\d+(\.\d+)?|\.\d+")


class CodeHighlighter(QSyntaxHighlighter):
    """One highlighter for every language, driven by the Language table."""

    def __init__(self, document, palette, language):
        super().__init__(document)
        self.language = language
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

        self.formats = {
            "cmd": fmt(palette["syn_cmd"], bold=True),
            "word": fmt(palette["syn_word"]),
            "string": fmt(palette["syn_str"]),
            "number": fmt(palette["syn_num"]),
            "comment": fmt(palette["syn_com"], italic=True),
        }
        self.rehighlight()

    def set_language(self, language):
        self.language = language
        self.rehighlight()

    def highlightBlock(self, text):
        lang = self.language
        fmt = self.formats
        n = len(text)
        i = 0
        self.setCurrentBlockState(-1)

        state = self.previousBlockState()
        if 0 <= state < len(lang.multiline):
            _, end, kind = lang.multiline[state]
            j = text.find(end)
            if j == -1:
                self.setFormat(0, n, fmt[kind])
                self.setCurrentBlockState(state)
                return
            self.setFormat(0, j + len(end), fmt[kind])
            i = j + len(end)

        case_blind = lang.id == "sparky"
        while i < n:
            for index, (start, end, kind) in enumerate(lang.multiline):
                if text.startswith(start, i):
                    j = text.find(end, i + len(start))
                    if j == -1:
                        self.setFormat(i, n - i, fmt[kind])
                        self.setCurrentBlockState(index)
                        return
                    self.setFormat(i, j + len(end) - i, fmt[kind])
                    i = j + len(end)
                    break
            else:
                ch = text[i]
                if lang.comment and text.startswith(lang.comment, i):
                    self.setFormat(i, n - i, fmt["comment"])
                    return
                if ch in lang.quotes:
                    j = i + 1
                    while j < n and text[j] != ch:
                        j += 2 if text[j] == "\\" else 1
                    self.setFormat(i, min(j + 1, n) - i, fmt["string"])
                    i = j + 1
                    continue
                if ch.isdigit() or (ch == "." and i + 1 < n and text[i + 1].isdigit()):
                    m = NUMBER_RE.match(text, i)
                    if m and (i == 0 or not (text[i - 1].isalnum() or text[i - 1] == "_")):
                        self.setFormat(i, m.end() - i, fmt["number"])
                        i = m.end()
                        continue
                if ch.isalpha() or ch == "_":
                    m = WORD_RE.match(text, i)
                    word = m.group().lower() if case_blind else m.group()
                    if word in lang.keywords:
                        self.setFormat(i, m.end() - i, fmt["cmd"])
                    elif word in lang.builtins:
                        self.setFormat(i, m.end() - i, fmt["word"])
                    i = m.end()
                    continue
                i += 1


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.gutter_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_gutter(event)


def expand_snippet(body):
    """VS Code snippet text -> (plain text, where the cursor goes).

    ${1:default} keeps its default, ${1|a,b|} keeps its first choice, $1 and
    $0 are empty tab stops; the cursor lands on the lowest numbered stop
    (or $0, or the end). Variables like ${TM_FILENAME} become their default.
    """
    text = body.replace("\\$", "\0")
    text = re.sub(r"\$\{(\d+)\|([^,|}]*)[^}]*\|\}", r"${\1:\2}", text)
    text = re.sub(r"\$\{([A-Z_]+)(?::([^}]*))?\}", lambda m: m.group(2) or "", text)
    out, pos, first, zero = [], 0, None, None
    for m in re.finditer(r"\$\{(\d+):([^}]*)\}|\$(\d+)", text):
        out.append(text[pos:m.start()])
        here = sum(len(part) for part in out)
        number = int(m.group(1) or m.group(3))
        if number == 0:
            zero = here if zero is None else zero
        elif first is None or number < first[0]:
            first = (number, here)
        out.append(m.group(2) or "")
        pos = m.end()
    out.append(text[pos:])
    plain = "".join(out).replace("\0", "$")
    if first is not None:
        return plain, first[1]
    return plain, (zero if zero is not None else len(plain))


class CodeEditor(QPlainTextEdit):
    def __init__(self, palette, language=None, path=None, parent=None):
        super().__init__(parent)
        self.setObjectName("Editor")
        self.palette_colors = palette
        self.running_line = None
        self.error_line = None
        self.completions_enabled = True
        self.path = path
        self.title = None           # name shown for files that aren't saved yet
        self.language = language or language_for(path)
        self.snippets = {}          # prefix -> (body, description)

        self.set_font_size(15)

        self.gutter = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_gutter_width)
        self.updateRequest.connect(self.on_update_request)
        self.cursorPositionChanged.connect(self.refresh_highlights)
        self.update_gutter_width()

        self.highlighter = CodeHighlighter(self.document(), palette, self.language)

        self.completer = QCompleter(QStringListModel([], self), self)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(
            QCompleter.CompletionMode.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.activated.connect(self.insert_completion)

    # ---------- language ----------

    @property
    def indent_unit(self):
        return "    " if self.language.id == "python" else "  "

    def set_language(self, language):
        if isinstance(language, str):
            language = BY_ID[language]
        self.language = language
        self.highlighter.set_language(language)

    def display_name(self):
        if self.path:
            return self.path.name
        if self.title:
            return self.title
        return f"untitled{self.language.extensions[0] if self.language.extensions else ''}"

    # ---------- font size / zoom ----------

    def set_font_size(self, size):
        size = max(10, min(28, size))
        font = QFont()
        font.setFamilies(CODE_FONTS)
        font.setPointSize(size)
        self.setFont(font)
        self.setTabStopDistance(QFontMetricsF(font).horizontalAdvance(" ") * 4)
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
            self.goto_line(line)

    def goto_line(self, line):
        block = self.document().findBlockByNumber(max(0, line - 1))
        if block.isValid():
            self.setTextCursor(QTextCursor(block))
            self.centerCursor()
            self.setFocus()

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

    # ---------- find ----------

    def find_text(self, text, backward=False, case=False, whole=False):
        """Find the next match, wrapping around. True if found."""
        if not text:
            return False
        flags = QTextDocument.FindFlag(0)
        if backward:
            flags |= QTextDocument.FindFlag.FindBackward
        if case:
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if whole:
            flags |= QTextDocument.FindFlag.FindWholeWords
        if self.find(text, flags):
            return True
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End if backward
                            else QTextCursor.MoveOperation.Start)
        self.setTextCursor(cursor)
        return self.find(text, flags)

    def replace_all(self, text, replacement, case=False, whole=False):
        """Replace every match in one undo step. Returns how many."""
        if not text:
            return 0
        flags = QTextDocument.FindFlag(0)
        if case:
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if whole:
            flags |= QTextDocument.FindFlag.FindWholeWords
        count = 0
        cursor = QTextCursor(self.document())
        cursor.beginEditBlock()
        found = self.document().find(text, 0, flags)
        while not found.isNull():
            found.insertText(replacement)
            count += 1
            found = self.document().find(text, found.position(), flags)
        cursor.endEditBlock()
        return count

    # ---------- typing behavior ----------

    def keyPressEvent(self, event):
        popup = self.completer.popup()
        if popup.isVisible() and event.key() in (
                Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab,
                Qt.Key.Key_Escape, Qt.Key.Key_Up, Qt.Key.Key_Down):
            event.ignore()
            return

        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and \
                not event.modifiers() & (Qt.KeyboardModifier.ControlModifier |
                                         Qt.KeyboardModifier.MetaModifier):
            self.auto_indent_newline()
            return
        if event.key() == Qt.Key.Key_Tab:
            if self.textCursor().hasSelection():
                self.shift_lines(+1)
            else:
                self.insertPlainText(self.indent_unit)
            return
        if event.key() == Qt.Key.Key_Backtab:
            self.shift_lines(-1)
            return

        super().keyPressEvent(event)

        # typing an error away should clear the orange mark
        if self.error_line is not None and event.text():
            self.set_error_line(None)

        self.maybe_complete(event)

    def auto_indent_newline(self):
        cursor = self.textCursor()
        line = cursor.block().text()[:cursor.positionInBlock()]
        indent = line[:len(line) - len(line.lstrip())]
        opens = self.language.openers and self.language.openers(line)
        cursor.insertText("\n" + indent + (self.indent_unit if opens else ""))
        self.setTextCursor(cursor)

    def selected_blocks(self):
        cursor = self.textCursor()
        doc = self.document()
        first = doc.findBlock(cursor.selectionStart())
        last = doc.findBlock(max(cursor.selectionStart(), cursor.selectionEnd() - 1)
                             if cursor.hasSelection() else cursor.position())
        blocks = []
        block = first
        while block.isValid():
            blocks.append(block)
            if block == last:
                break
            block = block.next()
        return blocks

    def shift_lines(self, direction):
        unit = self.indent_unit
        cursor = self.textCursor()
        cursor.beginEditBlock()
        for block in self.selected_blocks():
            c = QTextCursor(block)
            if direction > 0:
                c.insertText(unit)
            else:
                text = block.text()
                remove = len(text) - len(text.lstrip(" "))
                remove = min(remove, len(unit))
                for _ in range(remove):
                    c.deleteChar()
        cursor.endEditBlock()

    def toggle_comment(self):
        mark = self.language.comment
        if not mark:
            return
        blocks = [b for b in self.selected_blocks() if b.text().strip()]
        if not blocks:
            return
        commented = all(b.text().lstrip().startswith(mark) for b in blocks)
        cursor = self.textCursor()
        cursor.beginEditBlock()
        for block in blocks:
            text = block.text()
            lead = len(text) - len(text.lstrip())
            c = QTextCursor(block)
            c.setPosition(block.position() + lead)
            if commented:
                size = len(mark) + (1 if text[lead + len(mark):].startswith(" ") else 0)
                for _ in range(size):
                    c.deleteChar()
            else:
                c.insertText(mark + " ")
        cursor.endEditBlock()

    # ---------- autocomplete + snippets ----------

    def current_word(self):
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        return cursor.selectedText()

    def completion_words(self):
        lang = self.language
        words = set(lang.keywords) | set(lang.builtins) | set(self.snippets)
        if lang.id == "sparky":
            words |= SPARKY_PHRASES
        words.update(re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", self.toPlainText()))
        return words

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

        words = self.completion_words()
        words.discard(word)
        self.completer.model().setStringList(sorted(words, key=str.lower))
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
        if text in self.snippets:
            self.setTextCursor(cursor)
            self.insert_snippet_body(self.snippets[text][0])
            return
        cursor.insertText(text)
        self.setTextCursor(cursor)

    def insert_snippet_body(self, body):
        """Insert a VS Code snippet, indented to match, cursor at its first stop."""
        cursor = self.textCursor()
        line = cursor.block().text()
        indent = line[:len(line) - len(line.lstrip())]
        text, offset = expand_snippet(body.replace("\t", self.indent_unit))
        text = text.replace("\n", "\n" + indent)
        extra = text[:offset].count("\n") * len(indent)
        start = cursor.position()
        cursor.insertText(text)
        cursor.setPosition(start + offset + extra)
        self.setTextCursor(cursor)
        self.setFocus()

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
