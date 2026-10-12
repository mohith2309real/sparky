"""Final release UI contracts: lazy construction, history and console semantics."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['SPARKY_SETTINGS_FILE'] = str(Path(tempfile.mkdtemp()) / 'settings.ini')
os.environ['SPARKY_NEW_WINDOW'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PyQt6.QtWidgets import QApplication, QPushButton
from sparky.ide import app as appmod
from sparky.ide.debug_panel import CONSOLE_KINDS

qt = QApplication([])
prefs = appmod.prefs.open_settings()
prefs.setValue('first_run_done', True)
prefs.setValue('offline', True)
prefs.setValue('reduce_motion', True)
prefs.sync()
win = appmod.MainWindow()
win.show()
qt.processEvents()
passed = 0

def check(name, condition):
    global passed
    assert condition, name
    passed += 1
    print('  ok -', name)

panels = [getattr(win, name + '_panel') for name in
          ('files', 'ai', 'extensions', 'arduino', 'outline', 'debug', 'assets')]
check('Home does not construct optional panels', all(p._widget is None for p in panels))
check('Reloaded block buttons leave no overlapping stale children', all(
    win.blocks.layout_.indexOf(button) >= 0 for button in win.blocks.inner.findChildren(QPushButton)))
run = dict(file='example.spark', when=0, seconds=1, steps=2, ok=True, output='hello')
win.debug_panel.add_run(run)
check('Run history stays lazy', win.debug_panel._widget is None)
win.show_workspace()
win.show_sidebar_named('debug')
qt.processEvents()
check('Opening Debug constructs Debug', win.debug_panel._widget is not None)
check('Other panels stay lazy', all(p._widget is None for p in panels if p is not win.debug_panel))
check('Queued run history survives opening', win.debug_panel.history == [run])
win.console.clear()
for kind in CONSOLE_KINDS:
    win.console_write(kind, kind=kind)
check('Copy keeps plain message text', win.console.toPlainText().splitlines() == list(CONSOLE_KINDS))
states = [win.console.document().findBlockByNumber(i).userState() for i in range(5)]
check('Each message has its own gutter marker', states == [1, 2, 3, 4, 5])
win.console.set_filter('problems')
check('Filtering preserves error marker', win.console.toPlainText() == 'error' and
      win.console.document().firstBlock().userState() == 5)
win.console.clear()
check('Clear removes message history', not win.console.entries and win.console.document().isEmpty())
win.activity_badges['debug'].show_count('!')
check('Debug badge signals an error', win.activity_badges['debug'].text() == '!')
win.activity_badges['debug'].show_count('')
check('Empty badge is hidden', win.activity_badges['debug'].isHidden())
check('Bundled signed news is available offline', bool(win.home_page.feed_items['news']))
check('Bundled featured projects are available offline', len(win.home_page.feed_items['projects']) == 3)
win.home_page.refresh_feeds()
check('Offline refresh does not start a network worker', win.home_page.feed_worker is None)
item = win.home_page.feed_items['projects'][0]
win.home_page.open_featured(item)
check('Featured project opens as an unsaved copy', win.editor.toPlainText() == item['code'] and win.editor.path is None)
check('Featured project never runs automatically', not win.is_running())
win.confirm_discard = lambda _: True
win.close()
print(f'{passed} final UI checks passed.')
