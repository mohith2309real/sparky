# The IDE's debugging and editor tools, in the real window (offscreen):
# breakpoints, variables, call stack, watches, run history and stats, console
# filters and clickable errors, replay, run selection, outline, split, zen.
# Run with: QT_QPA_PLATFORM=offscreen python3 tests/test_ide_debug.py

import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["SPARKY_SETTINGS_FILE"] = str(Path(tempfile.mkdtemp()) / "settings.ini")
os.environ["SPARKY_NEW_WINDOW"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication  # noqa: E402

qt = QApplication(sys.argv)

from sparky.ide import app as appmod  # noqa: E402

prefs = appmod.prefs.open_settings()
prefs.setValue("first_run_done", True)
prefs.setValue("mode", "pro")
prefs.sync()
win = appmod.MainWindow()
win.resize(1440, 900)
win.show()
passed = 0


def check(name, got, want):
    global passed
    assert got == want, f"FAILED: {name}\n  got:  {got!r}\n  want: {want!r}"
    passed += 1
    print(f"  ok - {name}")


def pump(seconds=0.2):
    end = time.time() + seconds
    while time.time() < end:
        qt.processEvents()
        time.sleep(0.01)


def wait_for(cond, limit=10):
    end = time.time() + limit
    while not cond() and time.time() < end:
        pump(0.05)
    return cond()


pump(0.5)
win.show_workspace()
program = ("teach count_down n\n  if n < 1 then\n    give back 0\n  end\n"
           "  say n\n  give back count_down(n - 1)\nend\n"
           "set pets to [\"cat\", \"dog\"]\nset score to 5\nsay count_down(3)\nsay \"done\"\n")
editor = win.new_tab(program, None, None, "debug.spark")
win.speed.setValue(10)

# a breakpoint inside a recursive command
editor.toggle_breakpoint(5)
win.show_sidebar_named("debug")
win.run_program()
check("pauses at the breakpoint", wait_for(lambda: win.runner and win.runner._paused, 10), True)
pump(0.5)
win.debug_panel.refresh()
values = {}
for i in range(win.debug_panel.vars.topLevelItemCount()):
    top = win.debug_panel.vars.topLevelItem(i)
    for j in range(top.childCount()):
        child = top.child(j)
        values[(top.text(0), child.text(0))] = child.text(1)
check("variables while paused", (values.get(("Program", "score")), values.get(("Program", "pets")),
                                 values.get(("Inside count_down", "n"))), ("5", '["cat", "dog"]', "3"))
check("call stack", win.debug_panel.calls.item(0).text(), "count_down  (called on line 10)")
win.debug_panel.watch_box.setText("score * 2")
win.debug_panel.add_watch()
win.debug_panel.watch_box.setText("length(pets)")
win.debug_panel.add_watch()
check("watches", [win.debug_panel.watch_list.item(i).text() for i in range(2)],
      ["score * 2 = 10", "length(pets) = 2"])
win.runner.resume()
check("pauses again in the next call", wait_for(lambda: win.runner._paused, 5), True)
pump(0.3)
win.debug_panel.refresh()
check("deeper in the call stack", win.debug_panel.calls.count(), 2)
editor.toggle_breakpoint(5)            # remove it while running
win.runner.resume()
check("finishes", wait_for(lambda: not win.is_running(), 10), True)
pump(0.5)
check("run history", win.debug_panel.runs.count() >= 1 and win.debug_panel.runs.item(0).text().startswith("✓"),
      True)
check("run stats", bool(win.last_stats and win.last_stats[0] > 5), True)

# clickable errors, lesson links, filters
win.new_tab("say 1\nsay scroe\n", None, None, "oops.spark")
win.run_program()
wait_for(lambda: not win.is_running(), 10)
pump(0.4)
text = win.console.toPlainText()
check("error offers a lesson", "📖 Learn about this: 3. Remember things" in text, True)
win.editor.goto_line(1)
win.console_line_clicked(2)
check("clicking an error jumps to its line", win.editor.textCursor().blockNumber() + 1, 2)
win.console_filter.setCurrentIndex(1)       # only what it said
pump(0.1)
check("filter: what it said", win.console.toPlainText().strip(), "1")
win.console_filter.setCurrentIndex(2)       # only problems
pump(0.1)
check("filter: problems", win.console.toPlainText().startswith("Oops!"), True)
win.console_filter.setCurrentIndex(0)

# replay
win.new_tab("speed 6\nrepeat 12 times\n  move 60\n  turn 150\nend\n", None, None, "star.spark")
win.speed.setValue(6)
win.run_program()
wait_for(lambda: not win.is_running(), 15)
pump(0.3)
check("replay slider after a run", win.replay_row.isVisible() and win.replay_slider.maximum() > 3, True)
win.replay_slider.setValue(1)
pump(0.1)
check("replaying shows an earlier moment", win.stage.replay is not None and
      win.stage.replay[0] < len(win.stage_model.items), True)
win.replay_slider.setValue(win.replay_slider.maximum())
check("the end returns to live", win.stage.replay, None)

# run selection
sel = win.new_tab('say "first"\nsay "second"\nsay "third"\n', None, None, "sel.spark")
cursor = sel.textCursor()
cursor.setPosition(len('say "first"\n'))
cursor.setPosition(len('say "first"\nsay "second"'), cursor.MoveMode.KeepAnchor)
sel.setTextCursor(cursor)
win.run_selection()
wait_for(lambda: not win.is_running(), 10)
pump(0.3)
check("run selection runs only those lines", [l for l in win.console.toPlainText().split("\n")
                                              if l.strip() and not l.startswith("Ran")], ["second"])

# outline, split, zen, rename/format commands, export
win.tabs.setCurrentWidget(editor)
pump(0.1)
win.show_sidebar_named("outline")
win.outline_panel.refresh()
check("outline lists the program", [win.outline_panel.list.item(i).text() for i in
                                    range(win.outline_panel.list.count())],
      ["◆  count_down n", "▪  pets", "▪  score"])
win.toggle_split()
check("split editor", (win.split_view is not None, win.split_view.toPlainText() == editor.toPlainText()),
      (True, True))
win.toggle_split()
win.toggle_zen()
check("zen hides the extras", (win.activity_bar.isVisible(), win.console_card.isVisible()), (False, False))
win.toggle_zen()
check("zen comes back", (win.activity_bar.isVisible(), win.console_card.isVisible()), (True, True))
check("breadcrumbs", (editor.goto_line(5), win.update_breadcrumbs(), win.crumbs.text())[2],
      "teach count_down n")
# live mode re-runs drawings as you type
live = win.new_tab("repeat 4 times\n  move 50\n  turn 90\nend\n", None, None, "live.spark")
win.live_mode = True
live.insertPlainText("pen color \"red\"\n")
check("live mode re-runs after typing", wait_for(lambda: win.is_running() or
                                                 len(win.stage_model.items) > 0, 5), True)
wait_for(lambda: not win.is_running(), 10)
check("live mode drew it", len(win.stage_model.segments) >= 4, True)
win.live_mode = False

# find in all files
folder = Path(tempfile.mkdtemp())
(folder / "a.spark").write_text("say \"treasure\"\n")
(folder / "sub").mkdir()
(folder / "sub" / "b.py").write_text("x = 1\nprint('treasure map')\n")
from sparky.ide.code_panels import FindInFilesDialog  # noqa: E402
dialog = FindInFilesDialog(win, folder, "treasure")
pump(0.3)
check("find in all files", sorted(dialog.results.item(i).text().split("    ")[0]
                                  for i in range(dialog.results.count())), ["a.spark:1", "sub/b.py:2"])
dialog.open_result(dialog.results.item(0))
pump(0.2)
check("opens the file at that line", (win.editor.display_name() in ("a.spark", "b.py"),), (True,))
dialog.close()

# a loop that never waits gets a friendly tip
hints = []
win.new_tab("forever\n  set x to 1\nend\n", None, None, "busy.spark")
win.run_program()
win.runner.sig_hint.connect(hints.append)
check("tip for a loop that never waits", wait_for(lambda: bool(hints), 30), True)
win.stop_program()
wait_for(lambda: not win.is_running(), 5)

for tab in win.editors():           # nothing to save: don't ask before closing
    tab.document().setModified(False)
win.close()
print(f"\nAll {passed} IDE debugging checks passed!")
