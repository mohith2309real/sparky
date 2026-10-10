# The real code editor, driven like a kid would: typing, Enter, brackets,
# moving lines, folding, breakpoints, problems while typing, rename, format.
# Run with: QT_QPA_PLATFORM=offscreen python3 tests/test_editor_ui.py

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtCore import QPoint, Qt  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)

from sparky.ide import design  # noqa: E402
from sparky.ide.editor import CodeEditor  # noqa: E402
from sparky.ide.languages import BY_ID  # noqa: E402

passed = 0


def check(name, got, want):
    global passed
    assert got == want, f"FAILED: {name}\n  got:  {got!r}\n  want: {want!r}"
    passed += 1
    print(f"  ok - {name}")


def pump(seconds=0.05):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()


def fresh(text="", lang="sparky"):
    ed = CodeEditor(design.theme("daylight"), BY_ID[lang])
    ed.resize(700, 500)
    ed.show()
    ed.setPlainText(text)
    ed.moveCursor(ed.textCursor().MoveOperation.End)
    pump()
    return ed


def type_text(ed, text):
    for ch in text:
        if ch == "\n":
            QTest.keyClick(ed, Qt.Key.Key_Return)
        else:
            QTest.keyClicks(ed, ch)


# auto end
ed = fresh()
type_text(ed, "repeat 4 times\n")
check("auto end after repeat", ed.toPlainText(), "repeat 4 times\n  \nend")
check("cursor goes inside", ed.textCursor().blockNumber(), 1)
type_text(ed, "move 10")
ed2 = fresh("repeat 4 times\n  move 10\nend")
cursor = ed2.textCursor()
cursor.setPosition(len("repeat 4 times"))
ed2.setTextCursor(cursor)
type_text(ed2, "\n")
check("no second end when it's closed", ed2.toPlainText().count("end"), 1)

# brackets and quotes
ed = fresh()
type_text(ed, 'say length(')
check("bracket closes itself", ed.toPlainText(), "say length()")
type_text(ed, '"hi')
check("quote closes itself", ed.toPlainText(), 'say length("hi")')
type_text(ed, '")')
check("typing the closer steps over it", ed.toPlainText(), 'say length("hi")')
ed = fresh('say "it')
type_text(ed, "'s")
check("apostrophes stay single", ed.toPlainText(), "say \"it's")

# C-like braces get their closing brace on its own line
ed = fresh("void loop() {", "arduino")
type_text(ed, "}")
cursor = ed.textCursor()
cursor.setPosition(len("void loop() {"))
ed.setTextCursor(cursor)
type_text(ed, "\n")
check("brace block opens up", ed.toPlainText(), "void loop() {\n  \n}")

# line tools
ed = fresh("one\ntwo\nthree")
cursor = ed.textCursor()
cursor.setPosition(0)
ed.setTextCursor(cursor)
QTest.keyClick(ed, Qt.Key.Key_Down, Qt.KeyboardModifier.AltModifier)
check("Alt+Down moves the line", ed.toPlainText(), "two\none\nthree")
QTest.keyClick(ed, Qt.Key.Key_Down, Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.ShiftModifier)
check("Shift+Alt+Down duplicates", ed.toPlainText(), "two\none\none\nthree")
ed = fresh("say x\nset x to 1\nchange x by 2")
cursor = ed.textCursor()
cursor.setPosition(4)
ed.setTextCursor(cursor)
ed.select_next_match()
ed.select_next_match()
check("select next match", (ed.textCursor().selectedText(), ed.textCursor().blockNumber()), ("x", 1))

# folding
program = "teach star\n  repeat 5 times\n    move 50\n    turn 144\n  end\nend\nsay 1"
ed = fresh(program)
ed.toggle_fold(1)
pump()
hidden = [ed.document().findBlockByNumber(n).isVisible() for n in range(7)]
check("fold hides the inside", hidden, [True, False, False, False, False, True, True])
ed.goto_line(3)
check("going to a hidden line unfolds", ed.document().findBlockByNumber(2).isVisible(), True)

# breakpoints and bookmarks
ed = fresh(program)
ed.toggle_breakpoint(3)
ed.toggle_breakpoint(7)
check("breakpoints", ed.breakpoints(), {3, 7})
cursor = ed.textCursor()
cursor.setPosition(0)
ed.setTextCursor(cursor)
ed.insertPlainText("# a comment\n")
check("breakpoints move with their lines", ed.breakpoints(), {4, 8})
ed.goto_line(2)
ed.toggle_bookmark()
ed.goto_line(6)
check("next bookmark wraps around", (ed.next_bookmark(), ed.textCursor().blockNumber() + 1), (True, 2))

# problems while typing
ed = fresh('say "hi\n')
ed.check_code()
check("a problem is found while typing", (ed.problem or (None,))[0], 1)
ed.setPlainText('say "hi"\n')
ed.check_code()
check("and goes away when fixed", ed.problem, None)

# matching blocks, rename, format, definition
ed = fresh(program)
ed.goto_line(5)
ed.refresh_highlights()
check("matching block lights up", len(ed.extraSelections()) >= 3, True)
check("rename everywhere", (ed.rename_symbol("star", "spark"), ed.toPlainText().split("\n")[0]),
      (1, "teach spark"))
ed = fresh("repeat 2 times\nmove 10\nend")
ed.format_document()
check("format fixes indentation", ed.toPlainText(), "repeat 2 times\n  move 10\nend")
ed = fresh(program + "\ndo star")
check("go to definition", (ed.go_to_definition("star"), ed.textCursor().blockNumber() + 1), (True, 1))

# number scrubbing (Alt-drag)
ed = fresh("move 100")
start = ed.cursorRect(ed.textCursor()).center()
cursor = ed.textCursor()
cursor.setPosition(6)
ed.setTextCursor(cursor)
pos = ed.cursorRect(cursor).center()
scrubbed = []
ed.scrubbed.connect(lambda: scrubbed.append(True))
QTest.mousePress(ed.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.AltModifier, pos)
QTest.mouseMove(ed.viewport(), pos + QPoint(40, 0))
QTest.mouseRelease(ed.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.AltModifier,
                   pos + QPoint(40, 0))
check("Alt-drag changes the number", (ed.toPlainText(), bool(scrubbed)), ("move 110", True))

# completion with docs, split view, export
ed = fresh("set score to 1\nteach jump\nend\n")
items = ed.completion_items()
check("completion knows what words do", ("Say something" in items["say"], items["score"],
                                         items["jump"], items["gameloop"].startswith("snippet")),
      (True, "your variable", "your command", True))
twin = CodeEditor(design.theme("daylight"), BY_ID["sparky"], document=ed.document())
ed.insertPlainText("say 1\n")
check("split view shares the text", twin.toPlainText(), ed.toPlainText())
page = fresh('say "hi"').export_html()
check("export as colored HTML", ("<span style='color:" in page, "&quot;hi&quot;" in page), (True, True))
ed = fresh("say 1")
ed.set_minimap(True)
ed.set_word_wrap(True)
ed.set_show_spaces(True)
pump(0.1)
check("minimap, wrap and spaces", (ed.minimap.isVisible(), ed.lineWrapMode().name), (True, "WidgetWidth"))

print(f"\nAll {passed} editor checks passed!")
