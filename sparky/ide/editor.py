# The code editor: line numbers, syntax colors for every language Sparky
# knows, autocomplete (keywords, your own words, snippets — with what each
# one does), auto-indent, comment toggling, and soft highlights for the line
# that's running (blue) or the line with an error (orange).
#
# Sparky 3 adds: auto `end` and auto-closing brackets, matching blocks,
# problems underlined while you type, hover help, Alt-drag numbers, color
# swatches (Alt-click to pick), go to definition (Ctrl/Cmd-click), rename,
# format, folding, breakpoints and bookmarks in the gutter, a minimap, word
# wrap / show spaces, line tools, the run trail, and colored HTML export.

import html
import re
import time

from PyQt6.QtCore import QEvent, QPointF, QRect, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QPolygonF,
                         QStandardItem, QStandardItemModel, QSyntaxHighlighter,
                         QTextBlockUserData, QTextCharFormat, QTextCursor, QTextDocument,
                         QTextFormat, QTextOption)
from PyQt6.QtWidgets import (QColorDialog, QCompleter, QPlainTextEdit, QStyle,
                             QStyledItemDelegate, QTextEdit, QToolTip, QWidget)

from . import code_tools, docs
from .languages import BY_ID, language_for
from .theme import CODE_FONTS

SPARKY_PHRASES = {"pen down", "pen up", "pen color", "pen size", "turn left",
                  "repeat until", "repeat while", "wait until", "stop loop", "stop program",
                  "else if", "for each", "give back", "play note", "make sprite", "next frame",
                  "bounce if on edge", "fill color", "no fill", "pen style", "reset timer"}
WORD_RE = re.compile(r"[^\W\d]\w*")      # any alphabet (names can be Hindi, Telugu...)
TEMPLATE_RE = re.compile(r"(?<!\{)\{[^{}]+\}(?!\})")
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
                    if lang.id == "sparky":
                        # "Hi {name}!" — the part in braces is code
                        for m in TEMPLATE_RE.finditer(text, i + 1, min(j, n)):
                            self.setFormat(m.start(), m.end() - m.start(), fmt["word"])
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


class BlockData(QTextBlockUserData):
    """Marks that travel with a line as text is typed above it."""

    def __init__(self):
        super().__init__()
        self.bookmark = False
        self.breakpoint = False


def block_data(block, create=False):
    data = block.userData()
    if data is None and create:
        data = BlockData()
        block.setUserData(data)
    return data


class LineNumberArea(QWidget):
    """The gutter: breakpoint dots, line numbers, bookmarks and fold arrows."""

    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.setMouseTracking(True)

    def sizeHint(self):
        return QSize(self.editor.gutter_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_gutter(event)

    def mousePressEvent(self, event):
        self.editor.gutter_clicked(event)

    def mouseMoveEvent(self, event):
        self.editor.gutter_hover(event)

    def leaveEvent(self, event):
        self.editor.gutter_hover(None)


class Minimap(QWidget):
    """A tiny picture of the whole file; click or drag to scroll there."""

    WIDTH = 70

    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Overview — click to jump")

    def paintEvent(self, event):
        ed = self.editor
        p = QPainter(self)
        pal = ed.palette_colors
        p.fillRect(self.rect(), QColor(pal["editor_bg"]))
        doc = ed.document()
        lines = doc.blockCount()
        if not lines:
            return
        scale = min(3.0, max(1.0, self.height() / max(1, lines)))
        text_color = QColor(pal["text"])
        text_color.setAlpha(70)
        cmd = QColor(pal["syn_cmd"])
        cmd.setAlpha(150)
        block = doc.begin()
        y = 0.0
        while block.isValid() and y < self.height():
            if block.isVisible():
                text = block.text()
                indent = len(text) - len(text.lstrip())
                width = min(self.WIDTH - 6, len(text.strip()) * 0.9)
                if width > 0:
                    word = text.strip().split(" ")[0].lower()
                    p.fillRect(QRectF(3 + indent * 0.9, y, max(2.0, width), max(1.0, scale - 0.6)),
                               cmd if word in ed.language.keywords else text_color)
                y += scale
            block = block.next()
        first = ed.firstVisibleBlock().blockNumber()
        visible = max(1, ed.viewport().height() // max(1, ed.fontMetrics().height()))
        view = QColor(pal["text"])
        view.setAlpha(28)
        p.fillRect(QRectF(0, first * scale, self.width(), visible * scale), view)

    def mousePressEvent(self, event):
        self.jump(event.position().y())

    def mouseMoveEvent(self, event):
        if event.buttons():
            self.jump(event.position().y())

    def jump(self, y):
        ed = self.editor
        lines = ed.document().blockCount()
        scale = min(3.0, max(1.0, self.height() / max(1, lines)))
        line = int(y / scale)
        visible = max(1, ed.viewport().height() // max(1, ed.fontMetrics().height()))
        ed.verticalScrollBar().setValue(max(0, line - visible // 2))


class CompletionDelegate(QStyledItemDelegate):
    """Autocomplete rows: the word, and what it does in a quieter color."""

    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        doc = index.data(Qt.ItemDataRole.UserRole + 1)
        if not doc:
            return
        painter.save()
        color = QColor(self.editor.palette_colors["muted"])
        if option.state & QStyle.StateFlag.State_Selected:
            color = option.palette.highlightedText().color()
        painter.setPen(color)
        font = QFont(option.font)
        font.setPointSizeF(max(8.0, font.pointSizeF() * 0.85))
        painter.setFont(font)
        rect = option.rect.adjusted(int(option.rect.width() * 0.42), 0, -8, 0)
        text = QFontMetricsF(font).elidedText(doc, Qt.TextElideMode.ElideRight, rect.width())
        painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
        painter.restore()

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        return QSize(max(size.width(), 380), size.height() + 4)


SPARKY_SNIPPETS = {
    # prefix: (body with $1 stops, what it is)
    "square": ("repeat 4 times\n\tmove ${1:100}\n\tturn 90\nend", "draw a square"),
    "star": ("repeat 5 times\n\tmove ${1:100}\n\tturn 144\nend", "draw a star"),
    "spiral": ("repeat ${1:60} times\n\tmove repeat_count\n\tturn 91\nend", "a spiral"),
    "gameloop": ("forever\n\tif key \"right\" down then\n\t\tmove 5\n\tend\n\tif key \"left\" down then\n"
                 "\t\tmove -5\n\tend\n\tnext frame\nend", "a smooth game loop"),
    "quiz": ("ask \"${1:What is 6 x 7?}\" into answer\nif answer = ${2:42} then\n\tsay \"Right!\"\n"
             "\tplay \"tada\"\nelse\n\tsay \"Not quite!\"\nend", "a quiz question"),
    "countdown": ("for i from ${1:10} to 1 by -1\n\tsay i\n\twait 1\nend\nsay \"Lift off!\"",
                  "count down"),
    "sprite": ("make sprite ${1:rocket} with costume \"${2:rocket}\"\ntell ${1:rocket}\n\tgoto 0 0\nend",
               "a new sprite"),
    "whenkey": ("when key \"${1:space}\" pressed\n\t$0\nend", "do something when a key is pressed"),
    "teachcmd": ("teach ${1:name} ${2:size}\n\t$0\nend", "teach a new command"),
    "blink": ("forever\n\tpin ${1:13} on\n\twait 0.5\n\tpin ${1:13} off\n\twait 0.5\nend",
              "blink an LED (Sparky for Arduino)"),
}

PAIRS = {"(": ")", "[": "]", "{": "}", '"': '"', "'": "'"}


class CodeEditor(QPlainTextEdit):
    scrubbed = pyqtSignal()                 # a number was dragged (live mode re-runs)
    breakpoints_changed = pyqtSignal()
    problem_changed = pyqtSignal(object)    # SparkyError or None, while typing

    def __init__(self, palette, language=None, path=None, parent=None, document=None):
        super().__init__(parent)
        self.setObjectName("Editor")
        if document is not None:            # a second view of the same file (split editor)
            self.setDocument(document)
        self.palette_colors = palette
        self.running_line = None
        self.error_line = None
        self.problem = None                 # (line, message) found while typing
        self.trail = {}                     # line -> when it last ran
        self.completions_enabled = True
        self.auto_close = True
        self.path = path
        self.title = None           # name shown for files that aren't saved yet
        self.language = language or language_for(path)
        self.snippets = {}          # prefix -> (body, description)
        self.folded = set()         # opener lines that are folded
        self.scrub = None           # (block, start, end, start value, x, text) while dragging
        self.show_minimap = False
        self.hover_line = None

        self.set_font_size(15)

        self.gutter = LineNumberArea(self)
        self.minimap = Minimap(self)
        self.minimap.hide()
        self.blockCountChanged.connect(self.update_gutter_width)
        self.updateRequest.connect(self.on_update_request)
        self.cursorPositionChanged.connect(self.refresh_highlights)
        self.update_gutter_width()

        self.highlighter = CodeHighlighter(self.document(), palette, self.language) \
            if document is None else None

        self.completer = QCompleter(self)
        self.completer.setModel(QStandardItemModel(self.completer))
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.popup().setItemDelegate(CompletionDelegate(self))
        self.completer.activated.connect(self.insert_completion)

        self.check_timer = QTimer(self)
        self.check_timer.setSingleShot(True)
        self.check_timer.setInterval(600)
        self.check_timer.timeout.connect(self.check_code)
        self.textChanged.connect(self.check_timer.start)
        self.viewport().setMouseTracking(True)

    # ---------- language ----------

    @property
    def indent_unit(self):
        return "    " if self.language.id == "python" else "  "

    def set_language(self, language):
        if isinstance(language, str):
            language = BY_ID[language]
        self.language = language
        if self.highlighter is not None:
            self.highlighter.set_language(language)
        self.check_timer.start()

    def display_name(self):
        if self.path:
            return self.path.name
        if self.title:
            return self.title
        return f"untitled{self.language.extensions[0] if self.language.extensions else ''}"

    def lines(self):
        return self.toPlainText().split("\n")

    # ---------- font size / zoom / view ----------

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

    def set_word_wrap(self, on):
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth if on
                             else QPlainTextEdit.LineWrapMode.NoWrap)

    def set_show_spaces(self, on):
        option = self.document().defaultTextOption()
        flags = option.flags()
        if on:
            flags |= QTextOption.Flag.ShowTabsAndSpaces
        else:
            flags &= ~QTextOption.Flag.ShowTabsAndSpaces
        option.setFlags(flags)
        self.document().setDefaultTextOption(option)

    def set_minimap(self, on):
        self.show_minimap = on
        self.minimap.setVisible(on)
        self.update_gutter_width()
        self.resizeEvent(None)

    # ---------- theming ----------

    def apply_palette(self, palette):
        self.palette_colors = palette
        if self.highlighter is not None:
            self.highlighter.set_palette(palette)
        self.refresh_highlights()
        self.gutter.update()
        self.minimap.update()

    # ---------- gutter ----------

    MARK_W = 16       # breakpoints and bookmarks
    FOLD_W = 14

    def gutter_width(self):
        digits = max(2, len(str(self.blockCount())))
        return self.MARK_W + 8 + self.fontMetrics().horizontalAdvance("9") * digits + self.FOLD_W

    def update_gutter_width(self):
        self.setViewportMargins(self.gutter_width(), 0,
                                Minimap.WIDTH if self.show_minimap else 0, 0)

    def on_update_request(self, rect, dy):
        if dy:
            self.gutter.scroll(0, dy)
        else:
            self.gutter.update(0, rect.y(), self.gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_gutter_width()
        if self.show_minimap:
            self.minimap.update()

    def resizeEvent(self, event):
        if event is not None:
            super().resizeEvent(event)
        rect = self.contentsRect()
        self.gutter.setGeometry(QRect(rect.left(), rect.top(), self.gutter_width(), rect.height()))
        self.minimap.setGeometry(QRect(rect.right() - Minimap.WIDTH + 1, rect.top(),
                                       Minimap.WIDTH, rect.height()))

    def block_at_y(self, y):
        block = self.firstVisibleBlock()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        while block.isValid():
            height = self.blockBoundingRect(block).height()
            if block.isVisible() and top <= y < top + height:
                return block
            if block.isVisible():
                top += height
            block = block.next()
        return None

    def paint_gutter(self, event):
        painter = QPainter(self.gutter)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = self.palette_colors
        painter.fillRect(event.rect(), QColor(pal["editor_bg"]))
        foldable = code_tools.foldable(self.lines()) if self.language.id == "sparky" else \
            self.brace_folds()
        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        current = self.textCursor().blockNumber()
        height = self.fontMetrics().height()
        width = self.gutter.width()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                line = number + 1
                data = block_data(block)
                cy = top + height / 2
                if data is not None and data.breakpoint:
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor(pal["danger"]))
                    painter.drawEllipse(QPointF(8, cy), 5, 5)
                elif self.hover_line == line:
                    faint = QColor(pal["danger"])
                    faint.setAlpha(70)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(faint)
                    painter.drawEllipse(QPointF(8, cy), 5, 5)
                if data is not None and data.bookmark:
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor(pal["sky"]))
                    path = QPainterPath()
                    path.moveTo(2, top + 2)
                    path.lineTo(14, top + 2)
                    path.lineTo(14, top + height - 2)
                    path.lineTo(8, top + height - 6)
                    path.lineTo(2, top + height - 2)
                    path.closeSubpath()
                    painter.drawPath(path)
                is_current = number == current
                painter.setPen(QColor(pal["text"] if is_current else pal["gutter"]))
                painter.drawText(0, top, width - self.FOLD_W - 4, height,
                                 Qt.AlignmentFlag.AlignRight, str(line))
                if line in foldable:
                    painter.setPen(QPen(QColor(pal["gutter"]), 1.4))
                    x = width - self.FOLD_W / 2 - 1
                    if line in self.folded:
                        painter.drawPolyline(QPolygonF([QPointF(x - 2, cy - 4), QPointF(x + 2, cy),
                                                        QPointF(x - 2, cy + 4)]))
                    elif self.hover_line is not None:
                        painter.drawPolyline(QPolygonF([QPointF(x - 4, cy - 2), QPointF(x, cy + 2),
                                                        QPointF(x + 4, cy - 2)]))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            number += 1

    def gutter_hover(self, event):
        line = None
        if event is not None:
            block = self.block_at_y(event.position().y())
            line = block.blockNumber() + 1 if block is not None else None
        if line != self.hover_line:
            self.hover_line = line
            self.gutter.update()

    def gutter_clicked(self, event):
        block = self.block_at_y(event.position().y())
        if block is None:
            return
        line = block.blockNumber() + 1
        x = event.position().x()
        if x >= self.gutter.width() - self.FOLD_W - 2:
            self.toggle_fold(line)
        elif x <= self.MARK_W + 2:
            self.toggle_breakpoint(line)
        else:
            self.goto_line(line, center=False)

    # ---------- breakpoints and bookmarks ----------

    def toggle_breakpoint(self, line=None):
        line = line or self.textCursor().blockNumber() + 1
        block = self.document().findBlockByNumber(line - 1)
        data = block_data(block, create=True)
        data.breakpoint = not data.breakpoint
        self.gutter.update()
        self.breakpoints_changed.emit()

    def breakpoints(self):
        out, block = set(), self.document().begin()
        while block.isValid():
            data = block_data(block)
            if data is not None and data.breakpoint:
                out.add(block.blockNumber() + 1)
            block = block.next()
        return out

    def toggle_bookmark(self):
        block = self.textCursor().block()
        data = block_data(block, create=True)
        data.bookmark = not data.bookmark
        self.gutter.update()

    def bookmarks(self):
        out, block = [], self.document().begin()
        while block.isValid():
            data = block_data(block)
            if data is not None and data.bookmark:
                out.append(block.blockNumber() + 1)
            block = block.next()
        return out

    def next_bookmark(self, step=1):
        marks = self.bookmarks()
        if not marks:
            return False
        here = self.textCursor().blockNumber() + 1
        later = [m for m in marks if (m > here if step > 0 else m < here)]
        target = (later[0] if step > 0 else later[-1]) if later else (marks[0] if step > 0 else marks[-1])
        self.goto_line(target)
        return True

    # ---------- folding ----------

    def brace_folds(self):
        """{line with a {: line of its }} for C-like languages."""
        if self.language.id not in ("arduino", "c", "cpp", "javascript", "css", "json"):
            return {}
        folds, stack = {}, []
        for n, text in enumerate(self.lines(), 1):
            code = code_tools._strip_c_strings(text)
            for ch in code:
                if ch == "{":
                    stack.append(n)
                elif ch == "}" and stack:
                    start = stack.pop()
                    if n - start > 1:
                        folds[start] = n
        return folds

    def foldable(self):
        return code_tools.foldable(self.lines()) if self.language.id == "sparky" else self.brace_folds()

    def toggle_fold(self, line):
        folds = self.foldable()
        if line not in folds:
            return
        end = folds[line]
        hide = line not in self.folded
        if hide:
            self.folded.add(line)
        else:
            self.folded.discard(line)
        doc = self.document()
        block = doc.findBlockByNumber(line)          # the line after the opener
        while block.isValid() and block.blockNumber() + 1 < end:
            inner_folded = any(f < block.blockNumber() + 1 for f in self.folded if f != line
                               and f > line and f in folds)
            block.setVisible(not hide and not inner_folded)
            block = block.next()
        doc.markContentsDirty(0, doc.characterCount())
        self.viewport().update()
        self.gutter.update()
        self.update_gutter_width()

    def unfold_all(self):
        for line in sorted(self.folded):
            self.toggle_fold(line)

    # ---------- line highlights ----------

    def set_running_line(self, line):
        if line != self.running_line:
            if line:
                self.trail[line] = time.monotonic()
            self.running_line = line
            self.refresh_highlights()

    def clear_trail(self):
        self.trail = {}
        self.refresh_highlights()

    def set_error_line(self, line):
        self.error_line = line
        self.refresh_highlights()
        if line is not None:
            self.goto_line(line)

    def goto_line(self, line, center=True):
        block = self.document().findBlockByNumber(max(0, line - 1))
        if block.isValid():
            for opener in sorted(self.folded):          # show hidden lines first
                folds = self.foldable()
                if opener < line < folds.get(opener, 0):
                    self.toggle_fold(opener)
            self.setTextCursor(QTextCursor(block))
            if center:
                self.centerCursor()
            self.setFocus()

    def refresh_highlights(self):
        pal = self.palette_colors
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
        sel.format.setBackground(QColor(pal["line_hl"]))
        sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        sel.cursor = self.textCursor()
        sel.cursor.clearSelection()
        selections.append(sel)

        # lines that ran a moment ago fade out (the line trail)
        now = time.monotonic()
        run = QColor(pal["run_hl"])
        for line, when in list(self.trail.items()):
            age = now - when
            if age > 1.2 or line == self.running_line:
                if age > 1.2:
                    self.trail.pop(line, None)
                continue
            faded = QColor(run)
            faded.setAlphaF(max(0.0, run.alphaF() * (1 - age / 1.2) * 0.6))
            line_selection(line, faded)
        if self.running_line:
            line_selection(self.running_line, pal["run_hl"])
        if self.error_line:
            line_selection(self.error_line, pal["err_hl"])

        # the matching opener / end of the block the cursor is on
        if self.language.id == "sparky":
            here = self.textCursor().blockNumber() + 1
            partner = code_tools.matching_line(self.lines(), here)
            if partner:
                match = QColor(pal["accent"])
                match.setAlpha(36)
                for line in (here, partner):
                    block = self.document().findBlockByNumber(line - 1)
                    text = block.text()
                    start = len(text) - len(text.lstrip())
                    word = len(code_tools.first_word(text)) or len(text.strip())
                    sel = QTextEdit.ExtraSelection()
                    sel.format.setBackground(match)
                    sel.cursor = QTextCursor(block)
                    sel.cursor.setPosition(block.position() + start)
                    sel.cursor.setPosition(block.position() + start + word,
                                           QTextCursor.MoveMode.KeepAnchor)
                    selections.append(sel)

        # color swatches: "red" and "#ff8800" get a tint of their own color
        first = self.firstVisibleBlock()
        block, shown = first, 0
        while block.isValid() and shown < 80:
            if block.isVisible():
                for start, end, color in code_tools.colors_in_line(block.text()):
                    tint = QColor(color)
                    tint.setAlpha(110)
                    sel = QTextEdit.ExtraSelection()
                    sel.format.setBackground(tint)
                    sel.cursor = QTextCursor(block)
                    sel.cursor.setPosition(block.position() + start)
                    sel.cursor.setPosition(block.position() + end, QTextCursor.MoveMode.KeepAnchor)
                    selections.append(sel)
                shown += 1
            block = block.next()

        # a problem found while typing: a wavy line under it
        if self.problem and not self.error_line:
            line = self.problem[0]
            block = self.document().findBlockByNumber(line - 1)
            if block.isValid() and block.text().strip():
                text = block.text()
                sel = QTextEdit.ExtraSelection()
                sel.format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
                sel.format.setUnderlineColor(QColor(pal["danger"]))
                sel.cursor = QTextCursor(block)
                sel.cursor.setPosition(block.position() + len(text) - len(text.lstrip()))
                sel.cursor.setPosition(block.position() + len(text.rstrip()),
                                       QTextCursor.MoveMode.KeepAnchor)
                selections.append(sel)

        self.setExtraSelections(selections)
        self.gutter.update()

    # ---------- checking while you type ----------

    def check_code(self):
        if self.language.id != "sparky":
            if self.problem:
                self.problem = None
                self.problem_changed.emit(None)
                self.refresh_highlights()
            return
        from ..lang import SparkyError, parse
        try:
            parse(self.toPlainText())
            problem = None
        except SparkyError as err:
            problem = err if err.line else None
        old = self.problem
        self.problem = (problem.line, problem.pretty()) if problem else None
        if self.problem != old:
            self.refresh_highlights()
            self.problem_changed.emit(problem)

    # ---------- hover help, go to definition, scrubbing, color picking ----------

    def word_at(self, pos):
        cursor = self.cursorForPosition(pos)
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        return cursor.selectedText(), cursor

    def event(self, event):
        if event.type() == QEvent.Type.ToolTip:
            pos = self.viewport().mapFromGlobal(event.globalPos())
            self.show_hover(pos, event.globalPos())
            return True
        return super().event(event)

    def show_hover(self, pos, global_pos):
        line = self.cursorForPosition(pos).blockNumber() + 1
        if self.problem and self.problem[0] == line:
            QToolTip.showText(global_pos, self.problem[1].replace("\n", "<br>"), self)
            return
        word, _ = self.word_at(pos)
        tip = docs.tooltip_html(word) if self.language.id == "sparky" and word else None
        if tip:
            QToolTip.showText(global_pos, tip, self)
        else:
            QToolTip.hideText()

    def mousePressEvent(self, event):
        mods = event.modifiers()
        alt = mods & Qt.KeyboardModifier.AltModifier
        jump = mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)
        if event.button() == Qt.MouseButton.LeftButton and alt:
            cursor = self.cursorForPosition(event.position().toPoint())
            block, col = cursor.block(), cursor.positionInBlock()
            for start, end, color in code_tools.colors_in_line(block.text()):
                if start <= col <= end:
                    self.pick_color(block, start, end, color)
                    return
            found = code_tools.number_at(block.text(), col)
            if found:
                start, end, value = found
                self.scrub = (block, start, end, value, event.position().x(), block.text()[start:end])
                self.viewport().setCursor(Qt.CursorShape.SizeHorCursor)
                return
        if event.button() == Qt.MouseButton.LeftButton and jump:
            word, _ = self.word_at(event.position().toPoint())
            if word and self.go_to_definition(word):
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.scrub is not None:
            block, start, end, value, x0, like = self.scrub
            step = 0.1 if "." in like else 1
            new = value + round((event.position().x() - x0) / 4) * step
            text = code_tools.format_number(new, like)
            cursor = QTextCursor(block)
            cursor.setPosition(block.position() + start)
            cursor.setPosition(block.position() + end, QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(text)
            self.scrub = (block, start, start + len(text), value, x0, like)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.scrub is not None:
            self.scrub = None
            self.viewport().unsetCursor()
            self.scrubbed.emit()
            return
        super().mouseReleaseEvent(event)

    def pick_color(self, block, start, end, color):
        chosen = QColorDialog.getColor(QColor(color), self, "Pick a color")
        if not chosen.isValid():
            return
        cursor = QTextCursor(block)
        cursor.setPosition(block.position() + start)
        cursor.setPosition(block.position() + end, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(chosen.name())

    def go_to_definition(self, word):
        line = code_tools.definition_line(self.lines(), word, self.language.id)
        if line:
            self.goto_line(line)
            return True
        return False

    def rename_symbol(self, old, new):
        if not old or not new or old == new:
            return 0
        comment = self.language.comment or "#"
        text = self.toPlainText()
        renamed = code_tools.rename(text, old, new, comment)
        if renamed == text:
            return 0
        count = len(re.findall(rf"(?<!\w){re.escape(old)}(?!\w)", text)) - \
            len(re.findall(rf"(?<!\w){re.escape(old)}(?!\w)", renamed))
        self.replace_whole_text(renamed)
        return count

    def format_document(self):
        text = self.toPlainText()
        fixed = code_tools.reindent(text, self.language.id, self.indent_unit)
        if fixed != text:
            self.replace_whole_text(fixed)
            return True
        return False

    def replace_whole_text(self, text):
        """Swap the text in one undo step, keeping the cursor's line."""
        line = self.textCursor().blockNumber()
        cursor = QTextCursor(self.document())
        cursor.beginEditBlock()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.insertText(text)
        cursor.endEditBlock()
        block = self.document().findBlockByNumber(min(line, self.blockCount() - 1))
        self.setTextCursor(QTextCursor(block))

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

    def select_next_match(self):
        """Ctrl/Cmd+D: select the word, then its next match."""
        cursor = self.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
            self.setTextCursor(cursor)
            return
        text = cursor.selectedText()
        found = self.document().find(text, cursor.selectionEnd(),
                                     QTextDocument.FindFlag.FindCaseSensitively)
        if found.isNull():
            found = self.document().find(text, 0, QTextDocument.FindFlag.FindCaseSensitively)
        if not found.isNull():
            self.setTextCursor(found)

    # ---------- typing behavior ----------

    def keyPressEvent(self, event):
        popup = self.completer.popup()
        if popup.isVisible() and event.key() in (
                Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab,
                Qt.Key.Key_Escape, Qt.Key.Key_Up, Qt.Key.Key_Down):
            event.ignore()
            return
        key, mods, text = event.key(), event.modifiers(), event.text()
        alt = bool(mods & Qt.KeyboardModifier.AltModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        ctrl = bool(mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier))

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not ctrl:
            self.auto_indent_newline()
            return
        if key == Qt.Key.Key_Tab:
            if self.textCursor().hasSelection():
                self.shift_lines(+1)
            else:
                self.insertPlainText(self.indent_unit)
            return
        if key == Qt.Key.Key_Backtab:
            self.shift_lines(-1)
            return
        if alt and key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            if shift:
                self.duplicate_line(down=key == Qt.Key.Key_Down)
            else:
                self.move_lines(-1 if key == Qt.Key.Key_Up else 1)
            return
        if ctrl and shift and key == Qt.Key.Key_D:
            self.duplicate_line()
            return
        if ctrl and not shift and key == Qt.Key.Key_D:
            self.select_next_match()
            return
        if self.auto_close and text and self.handle_pairs(text, key):
            return

        super().keyPressEvent(event)

        # typing an error away should clear the orange mark
        if self.error_line is not None and text:
            self.set_error_line(None)

        self.maybe_complete(event)

    def handle_pairs(self, text, key):
        """Quotes and brackets close themselves; typing the closer steps over it."""
        cursor = self.textCursor()
        after = self.document().characterAt(cursor.position())
        before = self.document().characterAt(cursor.position() - 1) if cursor.position() else ""
        if key == Qt.Key.Key_Backspace and not cursor.hasSelection():
            if before in PAIRS and PAIRS[before] == after:
                cursor.deletePreviousChar()
                cursor.deleteChar()
                return True
            return False
        if text in (")", "]", "}", '"', "'") and after == text and not cursor.hasSelection():
            if text in "\"'" and self.inside_text(cursor) is False:
                pass
            else:
                cursor.movePosition(QTextCursor.MoveOperation.NextCharacter)
                self.setTextCursor(cursor)
                return True
        if text in PAIRS:
            if cursor.hasSelection():          # wrap the selection
                selected = cursor.selectedText()
                cursor.insertText(text + selected + PAIRS[text])
                return True
            if text in "\"'":
                if (before and (before.isalnum() or before == text)) or self.inside_text(cursor):
                    return False               # an apostrophe, or closing a text
            if after and (after.isalnum() or after == "_"):
                return False
            cursor.insertText(text + PAIRS[text])
            cursor.movePosition(QTextCursor.MoveOperation.PreviousCharacter)
            self.setTextCursor(cursor)
            return True
        return False

    def inside_text(self, cursor):
        line = cursor.block().text()[:cursor.positionInBlock()]
        return line.count('"') % 2 == 1

    def auto_indent_newline(self):
        cursor = self.textCursor()
        block_text = cursor.block().text()
        line = block_text[:cursor.positionInBlock()]
        rest = block_text[cursor.positionInBlock():]
        indent = line[:len(line) - len(line.lstrip())]
        opens = self.language.openers and self.language.openers(line)
        unit = self.indent_unit
        lid = self.language.id
        # Sparky: add the `end` for you (and C-like: the closing brace)
        if lid == "sparky" and opens and not rest.strip():
            lines = self.lines()
            n = cursor.blockNumber() + 1
            if code_tools.needs_end(lines, n):
                cursor.beginEditBlock()
                cursor.insertText("\n" + indent + unit)
                keep = cursor.position()
                cursor.insertText("\n" + indent + "end")
                cursor.setPosition(keep)
                cursor.endEditBlock()
                self.setTextCursor(cursor)
                return
        if lid in ("arduino", "c", "cpp", "javascript", "css", "json") and line.rstrip().endswith("{") \
                and rest.strip().startswith("}"):
            cursor.beginEditBlock()
            cursor.insertText("\n" + indent + unit)
            keep = cursor.position()
            cursor.insertText("\n" + indent)
            cursor.setPosition(keep)
            cursor.endEditBlock()
            self.setTextCursor(cursor)
            return
        cursor.insertText("\n" + indent + (unit if opens else ""))
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

    def move_lines(self, direction):
        """Alt+Up / Alt+Down: move the line (or the selected lines)."""
        blocks = self.selected_blocks()
        first, last = blocks[0], blocks[-1]
        neighbor = first.previous() if direction < 0 else last.next()
        if not neighbor.isValid():
            return
        lines = [b.text() for b in blocks]
        first_number = first.blockNumber()
        cursor = QTextCursor(self.document())
        cursor.beginEditBlock()
        start = (neighbor if direction < 0 else first).position()
        end_block = last if direction < 0 else neighbor
        cursor.setPosition(start)
        cursor.setPosition(end_block.position() + len(end_block.text()), QTextCursor.MoveMode.KeepAnchor)
        moved = (lines + [neighbor.text()]) if direction < 0 else ([neighbor.text()] + lines)
        cursor.insertText("\n".join(moved))
        cursor.endEditBlock()
        new_first = first_number + direction
        sel = QTextCursor(self.document().findBlockByNumber(new_first))
        last_block = self.document().findBlockByNumber(new_first + len(lines) - 1)
        sel.setPosition(last_block.position() + len(last_block.text()), QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(sel)

    def duplicate_line(self, down=True):
        blocks = self.selected_blocks()
        text = "\n".join(b.text() for b in blocks)
        cursor = QTextCursor(blocks[-1])
        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
        cursor.insertText("\n" + text)
        if not down:
            self.setTextCursor(QTextCursor(blocks[0]))
        else:
            self.setTextCursor(cursor)

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

    def all_snippets(self):
        snippets = dict(self.snippets)
        if self.language.id == "sparky":
            for prefix, (body, about) in SPARKY_SNIPPETS.items():
                snippets.setdefault(prefix, (body, about))
        return snippets

    def completion_items(self):
        """(word, what it is) for everything worth suggesting here."""
        lang = self.language
        items = {}
        text = self.toPlainText()
        if lang.id == "sparky":
            taught = set(re.findall(r"^\s*teach\s+(\w+)", text, re.M))
            for name in taught:
                items[name] = "your command"
            for name in re.findall(r"^\s*set\s+(\w+)\s+to\b", text, re.M):
                items.setdefault(name, "your variable")
            for phrase in SPARKY_PHRASES:
                items.setdefault(phrase, "")
        for word in set(lang.keywords) | set(lang.builtins):
            info = docs.lookup(word) if lang.id == "sparky" else None
            items.setdefault(word, info[0] if info else "")
        for prefix, (_body, about) in self.all_snippets().items():
            items[prefix] = "snippet: " + (about or prefix)
        for word in re.findall(r"[^\W\d]\w{2,}", text):
            items.setdefault(word, "")
        return items

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

        model = self.completer.model()
        model.clear()
        for name, about in sorted(self.completion_items().items(), key=lambda kv: kv[0].lower()):
            if name == word:
                continue
            item = QStandardItem(name)
            item.setData(about, Qt.ItemDataRole.UserRole + 1)
            if about:
                item.setToolTip(about)
            model.appendRow(item)
        self.completer.setCompletionPrefix(word)
        if self.completer.completionCount() == 0:
            self.completer.popup().hide()
            return
        rect = self.cursorRect()
        rect.setWidth(max(380, self.completer.popup().sizeHintForColumn(0) + 24))
        self.completer.complete(rect)

    def insert_completion(self, text):
        cursor = self.textCursor()
        word = self.current_word()
        for _ in range(len(word)):
            cursor.deletePreviousChar()
        snippets = self.all_snippets()
        if text in snippets:
            self.setTextCursor(cursor)
            self.insert_snippet_body(snippets[text][0])
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

    # ---------- export ----------

    def export_html(self):
        """The code as a colored web page (ready to print)."""
        pal = self.palette_colors
        out = [f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{html.escape(self.display_name())}"
               "</title><style>body{margin:0;background:" + pal["editor_bg"] + ";color:" + pal["text"] +
               "}pre{font:14px/1.55 'JetBrains Mono',Menlo,Consolas,monospace;padding:24px;margin:0}"
               ".n{color:" + pal["gutter"] + ";user-select:none;display:inline-block;width:3em}"
               "h1{font:600 15px system-ui;padding:16px 24px 0;margin:0}</style></head><body>"
               f"<h1>{html.escape(self.display_name())}</h1><pre>"]
        block = self.document().begin()
        number = 1
        while block.isValid():
            text = block.text()
            formats = sorted(block.layout().formats(), key=lambda r: r.start)
            pos, parts = 0, []
            for r in formats:
                if r.start > pos:
                    parts.append(html.escape(text[pos:r.start]))
                chunk = html.escape(text[r.start:r.start + r.length])
                fmt = r.format
                style = f"color:{fmt.foreground().color().name()}"
                if fmt.fontWeight() >= QFont.Weight.Bold:
                    style += ";font-weight:700"
                if fmt.fontItalic():
                    style += ";font-style:italic"
                parts.append(f"<span style='{style}'>{chunk}</span>")
                pos = r.start + r.length
            parts.append(html.escape(text[pos:]))
            out.append(f"<span class='n'>{number}</span>{''.join(parts)}\n")
            block = block.next()
            number += 1
        out.append("</pre></body></html>")
        return "".join(out)
