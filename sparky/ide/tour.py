# The interactive tour (feature 151).
#
# A see-through layer covers the window, dims everything except one real
# control (the "spotlight"), and a callout explains it. Clicks inside the
# spotlight reach the control underneath, so many steps wait for the kid to
# actually do the thing — type, press Run, click a block — before Next.

from PyQt6.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QRegion
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from . import mascot
from .widgets import text_button

PAD = 8


class Step:
    def __init__(self, key, title, text, target=None, done=None, prepare=None, mood="happy",
                 helper=None, helper_label="Do it for me", when=None):
        self.key = key
        self.title = title
        self.text = text
        self.target = target          # () -> QWidget or None (centered)
        self.done = done              # () -> bool; Next unlocks when True
        self.prepare = prepare        # () -> None, run when the step starts
        self.mood = mood
        self.helper = helper          # () -> None, the "Do it for me" button
        self.helper_label = helper_label
        self.when = when              # () -> bool; skip the step when False


def build_steps(w):
    """Every stop on the tour, in order. w is the MainWindow."""
    def editor():
        return w.editor if w.center_stack.currentIndex() == 1 else None

    hello = 'say "Hello! I made this!"\n'
    square = 'pen color "orange"\nrepeat 4 times\n  move 100\n  turn 90\nend\n'

    def type_text(text):
        w.show_workspace()
        e = w.editor
        e.setPlainText(text)
        e.setFocus()

    start = {}

    def remember(name, value):
        start[name] = value

    return [
        Step("hello", "Hi, I'm Sparky!",
             "I'll show you around. It takes about two minutes, and you'll try "
             "everything yourself. Press Next, or Skip if you've been here before.",
             mood="wow"),
        Step("home", "This is Home",
             "Start a new program, open one you made, learn, or come back to this tour. "
             "The house button on the left always brings you back here.",
             target=lambda: w.home_page.inner, prepare=w.show_home),
        Step("new", "Make a new program",
             "Click <b>New program</b>.",
             target=lambda: w.home_page.action_cards.get("New program"),
             prepare=lambda: (w.show_home(), remember("tabs", w.tabs.count())),
             done=lambda: w.center_stack.currentIndex() == 1 and w.tabs.count() > start.get("tabs", 0),
             helper=w.new_file, helper_label="Click it for me"),
        Step("type", "Type some code",
             f"This is the editor. Type this line:<br><code>{hello.strip()}</code>",
             target=editor, prepare=w.show_workspace,
             done=lambda: "say" in w.editor.toPlainText(),
             helper=lambda: type_text(hello), helper_label="Type it for me"),
        Step("run", "Press Run",
             "Run starts your program. (The shortcut is Ctrl/Cmd + Enter.)",
             target=lambda: w.run_button,
             prepare=lambda: remember("runs", w.run_count),
             done=lambda: w.run_count > start.get("runs", 0),
             helper=w.run_program, helper_label="Press it for me"),
        Step("console", "The console",
             "Everything Sparky says shows up here. When a program asks a question, "
             "you type the answer in the box at the bottom.",
             target=lambda: w.console_card),
        Step("draw", "Now draw something",
             "Let's draw a square. Put this program in the editor, then press Run:"
             f"<br><code>{square.replace(chr(10), '<br>').replace('  ', '&nbsp;&nbsp;')}</code>",
             target=editor, prepare=lambda: (w.show_workspace(), remember("runs2", w.run_count)),
             done=lambda: w.run_count > start.get("runs2", 0) and "repeat" in w.editor.toPlainText(),
             helper=lambda: (type_text(square), w.run_program()), helper_label="Do it for me"),
        Step("stage", "The stage",
             "Drawings happen here. The middle is x 0, y 0. The little spark is me!",
             target=lambda: w.stage_card, mood="wow"),
        Step("tools", "Stage tools",
             "Turn on the <b>grid</b> to see x and y. You can also save a snapshot or "
             "go fullscreen. Try the grid button.",
             target=lambda: w.stage_tools,
             prepare=lambda: remember("grid", w.stage.show_grid),
             done=lambda: w.stage.show_grid != start.get("grid"),
             helper=lambda: w.set_grid(not w.stage.show_grid), helper_label="Click it for me"),
        Step("speed", "Turtle or rabbit?",
             "Drag the slider to change how fast programs run: turtle is slow, rabbit is instant.",
             target=lambda: w.speed,
             prepare=lambda: remember("speed", w.speed.value()),
             done=lambda: w.speed.value() != start.get("speed"),
             helper=lambda: w.speed.setValue(3 if w.speed.value() > 3 else 8),
             helper_label="Move it for me"),
        Step("step", "Step through it",
             "<b>Step</b> runs one line at a time, so you can watch what each line does. "
             "It's the best way to find bugs. Press Step.",
             target=lambda: w.step_button,
             prepare=lambda: remember("steps", w.step_count),
             done=lambda: w.step_count > start.get("steps", 0),
             helper=w.step_program, helper_label="Press it for me", mood="thinking"),
        Step("blocks", "Blocks write code for you",
             "Click any colored block and real code appears in the editor. Try one!",
             target=lambda: w.sidebar, prepare=lambda: (w.show_workspace(), w.show_sidebar_named("blocks"),
                                                       remember("blocks", w.block_count)),
             done=lambda: w.block_count > start.get("blocks", 0)),
        Step("files", "Files",
             "Open a whole folder of projects, and jump between files.",
             target=lambda: w.activity_buttons.get("files"),
             when=lambda: w.mode == "pro"),
        Step("extensions", "Extensions",
             "Add real VS Code color themes and snippets from Open VSX.",
             target=lambda: w.activity_buttons.get("extensions"),
             when=lambda: w.mode == "pro"),
        Step("ai", "The AI helper",
             "Ask for hints when you're stuck. It works with Claude or other AI services "
             "(you add your own key in Settings → AI).",
             target=lambda: w.activity_buttons.get("ai")),
        Step("stage_tools", "Stage tools",
             "Show the grid, see which way sprites point, turn on turbo, pick a costume, save a "
             "picture (even a sharp SVG), or <b>record an animated GIF</b> of your program.",
             target=lambda: w.stage_tools, prepare=w.show_workspace),
        Step("arduino", "Arduino boards",
             "Sparky works like the Arduino IDE too: pick your board and port, press "
             "<b>Upload</b>, and watch the Serial Monitor. You can even write Sparky words like "
             "<b>pin 13 on</b>. Open the Arduino panel.",
             target=lambda: w.activity_buttons.get("arduino"),
             done=lambda: w.sidebar.isVisible() and w.sidebar.currentWidget() is w.arduino_panel,
             helper=lambda: w.show_sidebar_named("arduino"), helper_label="Open it for me"),
        Step("learn", "Learn",
             "Lessons take you from your first program to games and Python.",
             target=lambda: w.activity_buttons.get("learn")),
        Step("commands", "Every command, one place",
             "This box finds any command or setting. The shortcut is Ctrl/Cmd + Shift + P.",
             target=lambda: w.command_button),
        Step("theme", "Light or dark",
             "This button switches between Daylight and Midnight. Try it! More themes are in Settings.",
             target=lambda: w.theme_button,
             prepare=lambda: remember("theme", w.theme_key),
             done=lambda: w.theme_key != start.get("theme"),
             helper=w.toggle_theme, helper_label="Switch it for me"),
        Step("settings", "Settings and updates",
             "Kid mode or Pro mode, sizes, sounds — and updates. Sparky updates itself: when a "
             "new version is ready you'll see <b>Restart to update</b> at the top.",
             target=lambda: w.activity_buttons.get("settings")),
        Step("done", "You're ready!",
             "That's everything for now. You can take this tour again anytime from "
             "<b>Help → Take the tour</b>. Have fun making things!",
             mood="wow"),
    ]


class TourOverlay(QWidget):
    finished = pyqtSignal(bool)        # True if the kid reached the end

    def __init__(self, window, steps):
        super().__init__(window)
        self.window = window
        self.steps = [s for s in steps if s.when is None or s.when()]
        self.index = 0
        self.hole = QRect()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.callout = QFrame(self)
        self.callout.setObjectName("Card")
        self.callout.setFixedWidth(360)
        box = QVBoxLayout(self.callout)
        box.setContentsMargins(18, 16, 18, 14)
        box.setSpacing(8)
        top = QHBoxLayout()
        self.face = QLabel()
        top.addWidget(self.face)
        heads = QVBoxLayout()
        heads.setSpacing(0)
        self.counter = QLabel()
        self.counter.setObjectName("CardTitle")
        heads.addWidget(self.counter)
        self.title = QLabel()
        self.title.setObjectName("SubHeading")
        self.title.setWordWrap(True)
        heads.addWidget(self.title)
        top.addLayout(heads, 1)
        box.addLayout(top)
        self.text = QLabel()
        self.text.setWordWrap(True)
        self.text.setTextFormat(Qt.TextFormat.RichText)
        box.addWidget(self.text)
        self.status = QLabel()
        self.status.setObjectName("Muted")
        box.addWidget(self.status)
        self.helper = text_button("Do it for me", icon="ai")
        self.helper.clicked.connect(self.run_helper)
        box.addWidget(self.helper, 0, Qt.AlignmentFlag.AlignLeft)
        row = QHBoxLayout()
        self.skip = text_button("Skip tour", object_name="GhostButton")
        self.skip.clicked.connect(lambda: self.finish(False))
        row.addWidget(self.skip)
        row.addStretch(1)
        self.back = text_button("Back")
        self.back.clicked.connect(lambda: self.go(self.index - 1))
        row.addWidget(self.back)
        self.next = text_button("Next", object_name="Primary")
        self.next.clicked.connect(self.advance)
        row.addWidget(self.next)
        box.addLayout(row)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        window.installEventFilter(self)
        self.setGeometry(window.rect())
        self.show()
        self.raise_()
        self.go(0)
        self.timer.start(150)

    # ---------- steps ----------

    def current(self):
        return self.steps[self.index]

    def go(self, index):
        if index < 0:
            return
        if index >= len(self.steps):
            self.finish(True)
            return
        self.index = index
        step = self.current()
        if step.prepare:
            try:
                step.prepare()
            except Exception:
                pass
        self.face.setPixmap(mascot.pixmap(46, step.mood))
        self.counter.setText(f"STEP {index + 1} OF {len(self.steps)}")
        self.title.setText(step.title)
        self.text.setText(step.text)
        self.back.setVisible(index > 0)
        self.helper.setVisible(step.helper is not None)
        self.helper.setText(step.helper_label)
        last = index == len(self.steps) - 1
        self.next.setText("Finish" if last else ("Let's go" if index == 0 else "Next"))
        self.skip.setVisible(not last)
        self.tick()
        self.next.setFocus()

    def advance(self):
        if self.next.isEnabled():
            self.go(self.index + 1)

    def run_helper(self):
        step = self.current()
        if step.helper:
            step.helper()
            QTimer.singleShot(250, self.tick)

    def finish(self, completed):
        self.timer.stop()
        self.window.removeEventFilter(self)
        self.hide()
        self.deleteLater()
        self.finished.emit(completed)

    # ---------- layout ----------

    def target_rect(self):
        step = self.current()
        widget = None
        if step.target:
            try:
                widget = step.target()
            except Exception:
                widget = None
        if widget is None or not widget.isVisible():
            return QRect()
        top_left = widget.mapTo(self.window, QPoint(0, 0))
        return QRect(top_left, widget.size()).adjusted(-PAD, -PAD, PAD, PAD).intersected(self.rect())

    def tick(self):
        if not self.isVisible():
            return
        if self.geometry() != self.window.rect():
            self.setGeometry(self.window.rect())
        hole = self.target_rect()
        step = self.current()
        done = step.done is None or bool(self._safe(step.done))
        self.next.setEnabled(done)
        if step.done is not None:
            self.status.setText("✓ Nice!" if done else "Your turn — the step unlocks when you do it.")
            self.status.show()
        else:
            self.status.hide()
        if hole != self.hole or not self.mask().boundingRect():
            self.hole = hole
            self.update_mask()
            self.place_callout()
            self.update()
        self.raise_()

    @staticmethod
    def _safe(fn):
        try:
            return fn()
        except Exception:
            return False

    def update_mask(self):
        region = QRegion(self.rect())
        if not self.hole.isNull():
            path = QPainterPath()
            path.addRoundedRect(QRectF(self.hole), 12, 12)
            region = region.subtracted(QRegion(path.toFillPolygon().toPolygon()))
        self.setMask(region)

    def place_callout(self):
        self.callout.adjustSize()
        cw, ch = self.callout.width(), self.callout.height()
        W, H = self.width(), self.height()
        hole = self.hole
        if hole.isNull():
            x, y = (W - cw) // 2, (H - ch) // 2
        else:
            gap = 16
            candidates = [
                (hole.right() + gap, hole.top()),                       # right
                (hole.left() - gap - cw, hole.top()),                   # left
                (hole.left(), hole.bottom() + gap),                     # below
                (hole.left(), hole.top() - gap - ch),                   # above
            ]
            x, y = candidates[-1]
            for cx, cy in candidates:
                box = QRect(cx, max(8, min(cy, H - ch - 8)), cw, ch)
                if box.left() >= 8 and box.right() <= W - 8 and not box.intersects(hole):
                    x, y = box.left(), box.top()
                    break
            else:
                x, y = (W - cw) // 2, H - ch - 16
        self.callout.move(max(8, min(x, W - cw - 8)), max(8, min(y, H - ch - 8)))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(10, 10, 12, 150))
        if not self.hole.isNull():
            ring = QRectF(self.hole).adjusted(-3, -3, 3, 3)
            pen = QPen(QColor(self.window.palette_colors["accent"]), 3)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(ring, 14, 14)

    def eventFilter(self, obj, event):
        if obj is self.window and event.type() == QEvent.Type.Resize:
            QTimer.singleShot(0, self.tick)
        return False

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.finish(False)
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.advance()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        event.accept()            # clicks on the dimmed area do nothing


__all__ = ["TourOverlay", "build_steps", "QPointF"]
