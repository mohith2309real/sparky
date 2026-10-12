# Debugging (Sparky 3): the Debug sidebar — variables, the call stack,
# watches, breakpoints and the run history — and a console that can filter
# what it shows and jump to a line when you click an error.

import html
import re
import time

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QTextCursor,QPainter,QColor
from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QPlainTextEdit, QPushButton, QTreeWidget,
                             QTreeWidgetItem, QVBoxLayout, QWidget)
from . import icons

from ..lang import SparkyError, format_value

LINE_RE = re.compile(r"\bLine (\d+)\b")
LESSON_RE = re.compile(r"📖 Learn about this: (.+?)(?:\s+—|$)")


CONSOLE_KINDS=('info','say','question','answer','error')
class ConsoleGutter(QWidget):
    def paintEvent(self,event):
        view=self.parentWidget(); painter=QPainter(self)
        colors=getattr(view,'palette_colors',{})
        painter.fillRect(self.rect(),QColor(colors.get('editor_bg','#fffefb')))
        block=view.firstVisibleBlock()
        while block.isValid():
            top=view.blockBoundingGeometry(block).translated(view.contentOffset()).top()
            height=view.blockBoundingRect(block).height()
            if top>self.height(): break
            if block.isVisible() and block.userState()>0:
                kind=CONSOLE_KINDS[block.userState()-1]
                name={'info':'info','say':'code','question':'help','answer':'check','error':'error'}[kind]
                role={'info':'muted','say':'text','question':'sky','answer':'success','error':'danger'}[kind]
                painter.drawPixmap(3,int(top+(min(height,view.fontMetrics().height())-16)/2),icons.pixmap(name,colors.get(role,'#6f6d66'),16))
            block=block.next()

class ConsoleView(QPlainTextEdit):
    """The console. Remembers what kind each line is, so it can show only
    the program's words or only problems; click an error to jump to its line."""
    line_clicked = pyqtSignal(int)
    lesson_clicked = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("Console")
        self.setReadOnly(True)
        self.setAccessibleName("Console")
        self.entries = []          # (kind, html)
        self.filter = "all"        # all · say · problems
        self.viewport().setCursor(Qt.CursorShape.IBeamCursor)
        self.setMouseTracking(True)
        self.gutter=ConsoleGutter(self); self.setViewportMargins(22,0,0,0)
        self.updateRequest.connect(lambda *_:self.gutter.update())

    def resizeEvent(self,event):
        super().resizeEvent(event)
        rect=self.contentsRect(); self.gutter.setGeometry(rect.left(),rect.top(),22,rect.height())

    def append_entry(self,kind,body):
        start=0 if self.document().isEmpty() else self.blockCount()
        self.appendHtml(body)
        block=self.document().findBlockByNumber(start)
        if block.isValid(): block.setUserState(CONSOLE_KINDS.index(kind)+1 if kind in CONSOLE_KINDS else 1)
        self.gutter.update()

    def add(self, text, color=None, kind="info"):
        style = f' style="color:{color}"' if color else ""
        body = html.escape(text).replace("  ", "&nbsp; ").replace("\n", "<br>")
        entry = (kind, f"<span{style}>{body}</span>")
        self.entries.append(entry)
        if len(self.entries) > 4000:
            del self.entries[:1000]
        if self.shows(kind):
            self.append_entry(kind,entry[1])
            bar = self.verticalScrollBar()
            bar.setValue(bar.maximum())

    def shows(self, kind):
        return self.filter == "all" or (self.filter == "say" and kind == "say") or \
            (self.filter == "problems" and kind == "error")

    def set_filter(self, name):
        self.filter = name
        super().clear()
        for kind, body in self.entries:
            if self.shows(kind):
                self.append_entry(kind,body)

    def clear(self):
        self.entries = []
        super().clear()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.textCursor().hasSelection():
            return
        cursor = self.cursorForPosition(event.position().toPoint())
        text = cursor.block().text()
        lesson = LESSON_RE.search(text)
        if lesson:
            self.lesson_clicked.emit(lesson.group(1).strip())
            return
        found = LINE_RE.search(text)
        if found:
            self.line_clicked.emit(int(found.group(1)))

    def mouseMoveEvent(self, event):
        text = self.cursorForPosition(event.position().toPoint()).block().text()
        clickable = bool(LINE_RE.search(text) or LESSON_RE.search(text))
        self.viewport().setCursor(Qt.CursorShape.PointingHandCursor if clickable
                                  else Qt.CursorShape.IBeamCursor)
        super().mouseMoveEvent(event)


class DebugPanel(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.watches = []
        self.history = []          # newest first: dicts with file, when, seconds, steps, ok, output

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 10)
        layout.setSpacing(6)
        title = QLabel("DEBUG")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        self.status = QLabel("Run a program, or click next to a line number to add a breakpoint.")
        self.status.setObjectName("CardText")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        layout.addWidget(self.heading("Variables"))
        self.vars = QTreeWidget()
        self.vars.setHeaderLabels(["Name", "Value"])
        self.vars.setColumnWidth(0, 110)
        self.vars.setAccessibleName("Variables")
        self.vars.setMinimumHeight(150)
        layout.addWidget(self.vars, 3)

        layout.addWidget(self.heading("Call stack"))
        self.calls = QListWidget()
        self.calls.setMaximumHeight(80)
        self.calls.itemDoubleClicked.connect(self.jump_to_item)
        layout.addWidget(self.calls)

        layout.addWidget(self.heading("Watch"))
        row = QHBoxLayout()
        self.watch_box = QLineEdit()
        self.watch_box.setObjectName("Field")
        self.watch_box.setPlaceholderText("x * 2,  length(pets)…")
        self.watch_box.returnPressed.connect(self.add_watch)
        row.addWidget(self.watch_box, 1)
        add = QPushButton("Add")
        add.clicked.connect(self.add_watch)
        row.addWidget(add)
        layout.addLayout(row)
        self.watch_list = QListWidget()
        self.watch_list.setMaximumHeight(90)
        self.watch_list.setToolTip("Double-click a watch to remove it")
        self.watch_list.itemDoubleClicked.connect(self.remove_watch)
        layout.addWidget(self.watch_list)

        breakpoints_row = QHBoxLayout()
        breakpoints_row.addWidget(self.heading("Breakpoints"))
        breakpoints_row.addStretch(1)
        clear = QPushButton("Remove all")
        clear.setObjectName("LinkButton")
        clear.clicked.connect(self.clear_breakpoints)
        breakpoints_row.addWidget(clear)
        layout.addLayout(breakpoints_row)
        self.breaks = QListWidget()
        self.breaks.setMaximumHeight(80)
        self.breaks.itemDoubleClicked.connect(self.jump_to_item)
        layout.addWidget(self.breaks)

        layout.addWidget(self.heading("Run history"))
        self.runs = QListWidget()
        self.runs.setToolTip("Double-click a run to see what it printed")
        self.runs.itemDoubleClicked.connect(self.show_run)
        layout.addWidget(self.runs, 2)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)

    @staticmethod
    def heading(text):
        label = QLabel(text.upper())
        label.setObjectName("SectionTitle")
        return label

    def showEvent(self, event):
        self.refresh()
        self.timer.start(400)
        super().showEvent(event)

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    # ---------- live values ----------

    def interpreter(self):
        runner = self.main.runner
        return getattr(runner, "interpreter", None) if runner is not None else None

    def refresh(self):
        self.refresh_breakpoints()
        it = self.interpreter()
        runner = self.main.runner
        running = bool(runner and runner.isRunning())
        if it is None:
            return
        if running and runner._paused:
            self.status.setText(f"Paused at line {runner._pause_line}. Press Continue or Step.")
        elif running:
            self.status.setText("Running…")
        else:
            self.status.setText("Finished. These are the values at the end.")
        snap = it.snapshot()
        if snap is None:
            return
        self.vars.clear()
        groups = [("Program", snap["globals"])]
        if snap["calls"]:
            groups.append((f"Inside {snap['calls'][-1][0]}", snap["locals"]))
        for title, values in groups:
            top = QTreeWidgetItem([title, f"{len(values)}"])
            for name, value in sorted(values.items()):
                child = QTreeWidgetItem([name, format_value(value, quoted=True)])
                child.setToolTip(1, format_value(value, quoted=True))
                if isinstance(value, (list, dict)):
                    for key, inner in (enumerate(value, 1) if isinstance(value, list) else value.items()):
                        child.addChild(QTreeWidgetItem([f"item {key}" if isinstance(value, list) else key,
                                                        format_value(inner, quoted=True)]))
                top.addChild(child)
            self.vars.addTopLevelItem(top)
            top.setExpanded(True)
        sprites = snap["sprites"]
        if len(sprites) > 1 or any(s["x"] or s["y"] for s in sprites.values()):
            top = QTreeWidgetItem(["Sprites", f"{len(sprites)}"])
            for name, s in sprites.items():
                top.addChild(QTreeWidgetItem([name, f"x {s['x']:.0f}, y {s['y']:.0f}, "
                                                    f"pointing {s['heading']:.0f}"]))
            self.vars.addTopLevelItem(top)
        self.calls.clear()
        for name, line in reversed(snap["calls"]):
            item = QListWidgetItem(f"{name}  (called on line {line})")
            item.setData(Qt.ItemDataRole.UserRole, line)
            self.calls.addItem(item)
        if not snap["calls"]:
            self.calls.addItem("(the main program)")
        self.refresh_watches(it)

    def refresh_watches(self, it=None):
        it = it or self.interpreter()
        self.watch_list.clear()
        for text in self.watches:
            if it is None:
                value = "—"
            else:
                try:
                    value = format_value(it.watch(text), quoted=True)
                except SparkyError as err:
                    value = "⚠ " + err.message
                except Exception:
                    value = "—"
            self.watch_list.addItem(f"{text} = {value}")

    def add_watch(self):
        text = self.watch_box.text().strip()
        if text and text not in self.watches:
            self.watches.append(text)
        self.watch_box.clear()
        self.refresh_watches()

    def remove_watch(self, item):
        index = self.watch_list.row(item)
        if 0 <= index < len(self.watches):
            del self.watches[index]
        self.refresh_watches()

    # ---------- breakpoints ----------

    def refresh_breakpoints(self):
        editor = self.main.editor
        lines = sorted(editor.breakpoints()) if editor is not None else []
        current = [self.breaks.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.breaks.count())]
        if current == lines:
            return
        self.breaks.clear()
        for line in lines:
            block = editor.document().findBlockByNumber(line - 1)
            item = QListWidgetItem(f"Line {line}:  {block.text().strip()[:40]}")
            item.setData(Qt.ItemDataRole.UserRole, line)
            self.breaks.addItem(item)

    def clear_breakpoints(self):
        editor = self.main.editor
        if editor is None:
            return
        for line in editor.breakpoints():
            editor.toggle_breakpoint(line)
        self.refresh_breakpoints()

    def jump_to_item(self, item):
        line = item.data(Qt.ItemDataRole.UserRole)
        if line and self.main.editor is not None:
            self.main.editor.goto_line(int(line))

    # ---------- run history ----------

    def add_run(self, record):
        self.history.insert(0, record)
        del self.history[10:]
        self.runs.clear()
        for run in self.history:
            mark = "✓" if run["ok"] else "✗"
            when = time.strftime("%H:%M", time.localtime(run["when"]))
            steps = f" · {run['steps']:,} steps" if run.get("steps") else ""
            self.runs.addItem(f"{mark} {when}  {run['file']}{steps} · {run['seconds']:.1f} s")

    def show_run(self, item):
        index = self.runs.row(item)
        if not 0 <= index < len(self.history):
            return
        run = self.history[index]
        dialog = QDialog(self.main)
        dialog.setWindowTitle(f"Run of {run['file']}")
        dialog.resize(560, 420)
        col = QVBoxLayout(dialog)
        text = QPlainTextEdit()
        text.setObjectName("Console")
        text.setReadOnly(True)
        text.setPlainText(run["output"] or "(nothing was printed)")
        col.addWidget(text)
        close = QPushButton("Close")
        close.clicked.connect(dialog.accept)
        col.addWidget(close)
        dialog.exec()
