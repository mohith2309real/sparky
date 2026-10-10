"""Exercise alpha4 in the real Qt window using isolated project/settings files."""
import hashlib
import os
import sys
import tempfile
import time
from pathlib import Path
root = Path(tempfile.mkdtemp())
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['SPARKY_SETTINGS_FILE'] = str(root/'settings.ini')
os.environ['SPARKY_NEW_WINDOW'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QColor
from PyQt6.QtWidgets import QApplication
from sparky.ide import app as appmod
from sparky.ide.export import build_app
from sparky.ide.learning_data import LESSONS
from sparky.ide.learn import LearnDialog
from sparky.ide.player import PlayerWindow
from sparky.ide.project_ui import NewProjectDialog, VersionHistoryDialog, share_image
from sparky.ide.projects import TEMPLATES

qt = QApplication(sys.argv[:1])
prefs = appmod.prefs.open_settings()
prefs.setValue('first_run_done', True)
prefs.setValue('start_home', False)
prefs.sync()
win = appmod.MainWindow(); win.resize(1280,800); win.show()
passed = 0
def check(name, condition):
    global passed
    assert condition, name
    passed += 1; print('  ok - '+name, flush=True)
def pump(seconds=.1):
    end = time.monotonic()+seconds
    while time.monotonic()<end:
        qt.processEvents(); time.sleep(.005)
shots = Path('build/alpha4-checks/screenshots'); shots.mkdir(parents=True,exist_ok=True)
folder = win.project_store.create('My drawing', 'Art'); win.open_project(folder)
editor = win.editor; editor.setPlainText('say "autosaved"\n'); editor.document().setModified(True)
win.autosave()
check('autosave writes real editor and clears dirty state', (folder/'main.spark').read_text() == 'say "autosaved"\n' and not editor.document().isModified())
editor.setPlainText('say "draft"\n'); editor.document().setModified(True)
(folder/'main.spark').write_text('say "external"\n')
win.autosave()
check('outside edit preserved', (folder/'main.spark').read_text() == 'say "external"\n' and editor.document().isModified())
check('conflicting draft preserved', any(t['text']=='say "draft"\n' for t in win.project_store.load_recovery()['tabs']))
win.recovery_timer.stop(); win.autosave_timer.stop()
recovered = appmod.MainWindow(); recovered.recovery_timer.stop(); recovered.autosave_timer.stop()
check('crash session restores unsaved draft', any(e.toPlainText()=='say "draft"\n' and e.document().isModified() for e in recovered.editors()))
recovered.autosave()
check('recovered draft still protects outside edit', (folder/'main.spark').read_text() == 'say "external"\n')
for e in recovered.editors(): e.document().setModified(False)
recovered.close()
learn = LearnDialog(win); win.learn_dialog = learn; learn.show(); pump()
check('five worlds each with six lessons', learn.list.topLevelItemCount()==5 and all(learn.list.topLevelItem(i).childCount()==6 for i in range(5)))
learn.select_lesson('first-line'); learn.load_code()
check('Try it opens a new tab', win.editor.toPlainText()=='move 60\n' and win.editor is not editor)
learn.check_work()
end=time.monotonic()+5
while learn.checker.isRunning() and time.monotonic()<end: pump(.02)
pump()
check('worker checks program and persists stars', win.learning_progress.stars('first-line')==3 and 'passed every check' in learn.result.text())
learn.show_hint(); learn.show_hint(); learn.show_hint()
check('three progressive hints', 'Hint 3 of 3' in learn.hint_text.toPlainText())
learn.search.setText('square'); pump()
check('lesson search filters tree', sum(learn.list.topLevelItem(i).childCount() for i in range(5)) < 30)
learn.search.clear(); learn.select_lesson('first-line'); pump(); learn.grab().save(str(shots/'learn.png'))
learn.select_lesson('hello'); learn.show_python(); pump()
check('Python track shows translated code', not learn.python_body.isHidden() and 'print' in learn.python_body.toPlainText())
learn.grab().save(str(shots/'python-track.png'))
learn.show_reference(); learn.search.setText('repeat'); pump()
check('reference searches offline docs', 'repeat' in learn.body.toPlainText().lower())
learn.search.clear(); learn.show_glossary(); pump()
check('glossary has coding definitions', 'variable' in learn.body.toPlainText().lower())
learn.show_achievements(); pump(); learn.grab().save(str(shots/'achievements.png'))
check('achievements shows earned badge', 'First program' in learn.body.toPlainText())
learn.show_quiz()
from sparky.ide.learning_data import QUIZZES
learn.quiz_options.setCurrentIndex(QUIZZES[learn.quiz_index % len(QUIZZES)][2]); learn.grade_quiz()
check('prediction quiz grades the answer', 'You got it!' in learn.result.text())
learn.select_lesson('square'); learn.export_certificate()
check('incomplete world cannot export certificate', 'Complete all six' in learn.result.text())
learn.close()
win.open_project(folder); editor.document().setModified(False)
history=VersionHistoryDialog(win, win.editor)
index=next(i for i in range(history.list.count()) if history.list.item(i).data(Qt.ItemDataRole.UserRole)=='say "autosaved"\n')
win.editor.setPlainText('say "newer unsaved work"\n'); win.editor.document().setModified(True)
history.list.setCurrentRow(index); history.restore_selected()
check('version restore updates disk and editor', (folder/'main.spark').read_text()=='say "autosaved"\n' and win.editor.toPlainText()=='say "autosaved"\n')
check('restore keeps newer unsaved work in history', any('newer unsaved work' in p.read_text() for p in win.project_store.versions(win.editor.path)))
win.editor.setPlainText('say "after restore"\n'); win.editor.document().setModified(True); win.autosave()
check('autosave works after restore', (folder/'main.spark').read_text()=='say "after restore"\n')
win.start_tour(['new','type','step','debug']); pump()
check('individual tour replays selected steps', {s.key for s in win.tour.steps}.issubset({'new','type','step','debug','done'}) and any(s.key=='debug' for s in win.tour.steps))
win.tour.finish(False)
image=QImage(32,32,QImage.Format.Format_ARGB32); image.fill(QColor('orange')); image.save(str(folder/'assets'/'orange.png'))
win.assets_panel.refresh()
check('asset panel lists project image', win.assets_panel.list.count()==1)
win.assets_panel.list.setCurrentRow(0); win.assets_panel.insert_path()
check('asset insertion uses portable path', 'assets/orange.png' in win.editor.toPlainText())
win.editor.document().setModified(False)
share=share_image(win); share.save(str(shots/'share-card.png'))
check('share card exports drawing and code', share.width()==1600 and share.height()==1000)
cert=learn.certificate_image('Ada', 'Draw'); cert.save(str(shots/'certificate.png'))
check('certificate exports full image', cert.width()==1200 and not cert.isNull())
dialog=NewProjectDialog(win); dialog.show(); pump(); dialog.grab().save(str(shots/'new-project.png'))
check('new project has all six templates', dialog.template.count()==6); dialog.close()
win.stage.render_image(1).save(str(folder/'thumbnail.png')); win.show_home(); pump(); win.grab().save(str(shots/'home.png'))
export=build_app(root/'export','Ada’s Game','say "hello"',folder/'assets'/'orange.png',folder/'assets')
check('app includes custom icon and assets', (export/'icon.png').exists() and (export/'assets'/'orange.png').exists())
check('all launchers request fullscreen and icon', all('--fullscreen' in p.read_text() and '--icon' in p.read_text() for p in export.iterdir() if p.suffix in {'.command','.sh','.bat'}))
player=PlayerWindow('ask "Pick" choices ["red", "blue"] into answer\nsay answer','My Game',export)
player.showFullScreen(); pump(.5)
check('player supports answer buttons', player.choice_bar.isVisible())
player.choice_bar.pick('blue'); pump(.5)
check('player answers run through interpreter', 'blue' in player.console.toPlainText())
check('player resolves project assets', player.runner.base_dir==export)
player.exit_fullscreen.activated.emit(); pump()
check('Escape leaves fullscreen', not player.isFullScreen())
player.close()
game=PlayerWindow(TEMPLATES['Game'], 'Rocket Game', export); game.show(); pump(.4)
game.stage_model.push_event(('key','right')); pump(.6)
check('player handles real sprite key events', abs(game.stage_model.sprites['rocket']['x']-10)<.01)
game.close()
for e in win.editors(): e.document().setModified(False)
win.close(); pump()
print(f'{passed} learning UI checks passed', flush=True)
