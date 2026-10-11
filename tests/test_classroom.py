"""Assignment checks, portable hand-ins and enforced native classroom controls."""
import json, os, sys, tempfile, time, zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
root=Path(tempfile.mkdtemp())
os.environ['QT_QPA_PLATFORM']='offscreen'; os.environ['SPARKY_SETTINGS_FILE']=str(root/'settings.ini'); os.environ['SPARKY_NEW_WINDOW']='1'
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from PyQt6.QtCore import QSettings,QTimer
from PyQt6.QtWidgets import QApplication,QLabel
from sparky.ide.classroom import set_pin,verify_pin,blocked,read_task,export_handin,TimeTracker
from sparky.ide.learning import check_program
from sparky.ide import app as appmod
from sparky.ide.settings_dialog import SettingsDialog
from sparky.ide.assignment_ui import AssignmentDialog
from sparky.ide.player import PlayerWindow
from sparky.ide.arduino_panel import LibraryDialog,BoardsDialog,ArduinoPanel
passed=0
def check(name,condition):
    global passed
    assert condition,name
    passed+=1; print('  ok - '+name,flush=True)
def rejects(name,fn):
    try: fn()
    except (ValueError,TypeError): check(name,True)
    else: check(name,False)
qt=QApplication(sys.argv[:1]); prefs=appmod.prefs.open_settings()
set_pin(prefs,'4826'); prefs.sync()
check('PIN is verified after reload',verify_pin(appmod.prefs.open_settings(),'4826'))
check('wrong PIN rejected',not verify_pin(prefs,'4827'))
check('PIN not stored in clear text','4826' not in (root/'settings.ini').read_text())
rejects('short PIN rejected',lambda:set_pin(prefs,'123'))
rejects('non-digit PIN rejected',lambda:set_pin(prefs,'pass'))
prefs.setValue('first_run_done',True); prefs.setValue('start_home',False); prefs.sync()
task=read_task(Path('examples/Assignments/first_square.sparkytask'))
check('bundled assignment loads',task['title']=='My first square')
check('unfinished starter fails checks',not check_program(task,task['starter'])[0])
solution=task['starter'].replace('repeat 3','repeat 4')
check('square solution passes real interpreter',check_program(task,solution)[0])
check('cancelled checks stay bounded',not check_program(task,solution,lambda:True)[0])
check('file imports disabled in checker',not check_program(task,'use "other.spark"')[0])
check('oversized output fails safely',not check_program(dict(task,requires=[],checks={'output':[]}), 'repeat 1002 times\n say "hello"\nend')[0])
base={'product':'sparky-task','schema':1,'title':'Test','instructions':'Test','starter':'say "Hi"','requires':[],'checks':{'output':['Hi']}}
path=root/'task.sparkytask'
for name,changes in [('unknown checks',{'checks':{'shell':'run'}}),('bad case',{'checks':{'cases':[[{},[]]]}}),('bad position',{'checks':{'position':[1]}}),('bad event',{'checks':{'events':[['stage_click',1]]}}),('bad commands',{'requires':'Say'}),('wrong schema',{'schema':2})]:
    path.write_text(json.dumps(dict(base,**changes))); rejects(name+' rejected',lambda:read_task(path))
path.write_text(json.dumps(base).replace('"output": ["Hi"]','"position": [1e999, 0]'))
rejects('overflowing numbers rejected',lambda:read_task(path))
path.write_text(json.dumps(dict(base,checks={'cases':[[[2],['2']]]},starter='ask "Number?" into n\nsay n')))
case=read_task(path); check('numeric test answers work',check_program(case,case['starter'])[0])
project=root/'project'; (project/'assets').mkdir(parents=True)
(project/'main.spark').write_text('old'); (project/'assets'/'picture.png').write_bytes(b'asset')
(project/'.chats.json').write_text('private'); (project/'secret.pem').write_text('excluded'); (project/'link.txt').symlink_to(project/'secret.pem')
out=root/'handin.zip'; export_handin(out,solution,'Learner',task,project,61)
with zipfile.ZipFile(out) as archive:
    check('hand-in keeps unsaved editor code',archive.read('main.spark').decode()==solution)
    check('hand-in includes project assets',archive.read('assets/picture.png')==b'asset')
    check('hand-in excludes hidden and unsupported files and links',set(archive.namelist())=={'main.spark','assets/picture.png','submission.json'})
    info=json.loads(archive.read('submission.json')); check('hand-in records name assignment and local time',info['learner']=='Learner' and info['assignment']==task['title'] and info['time_seconds']==61)
tracker=TimeTracker(root/'activity.json'); tracker.advance(10)
check('timer bounds delayed ticks',tracker.seconds==2)
tracker.advance(1,False); check('inactive timer pauses',tracker.seconds==2)
tracker.since_break=59; check('break reminder fires at interval',tracker.advance(1,True,True,1))
check('break reminder resets',tracker.since_break==0)
tracker.save(); check('time survives restart',TimeTracker(tracker.path).seconds==3)
check('activity stores only seconds',json.loads(tracker.path.read_text())=={'seconds':3})
win=appmod.MainWindow(); win.show(); win.sound_bank.enabled=False; win.set_mode('pro')
prefs=win.settings; prefs.setValue('classroom/enabled',True); win.apply_classroom(); win.refresh_ai_actions()
check('classroom defaults hide both features',blocked(prefs,'ai') and blocked(prefs,'extensions'))
check('classroom removes commands',not win.extension_manager.api.commands)
check('AI and extension menus hidden',not win.menu_actions['view_extensions'].isVisible() and not win.menu_actions['view_ai'].isVisible())
check('classroom activity buttons hidden',win.activity_buttons['ai'].isHidden() and win.activity_buttons['extensions'].isHidden())
with patch.object(win.extensions_panel,'run',side_effect=AssertionError('network called')):
    win.extensions_panel.featured_packs(); win.extensions_panel.search()
check('classroom prevents catalog requests','Classroom' in win.extensions_panel.status.text())
win.extensions_panel.toggle_pack(); check('direct toggle cannot bypass classroom',not win.extension_manager.api.commands)
with patch('sparky.ide.ai.AIWorker',side_effect=AssertionError('AI called')): win.ai_panel.ask('Hi')
check('classroom prevents direct AI request',not win.ai_panel.worker)
player=PlayerWindow('say "Hi"','Test'); check('Player respects classroom extension lock',not player.extensions.api.commands); player.close()
with patch.object(appmod.QInputDialog,'getText',return_value=('0000',True)),patch.object(appmod.SettingsDialog,'exec') as opened:
    win.open_settings(); check('wrong PIN cannot open settings',not opened.called)
with patch.object(appmod.QInputDialog,'getText',return_value=('4826',True)),patch.object(appmod.SettingsDialog,'exec') as opened:
    win.open_settings(); check('teacher PIN opens settings',opened.called)
prefs.setValue('classroom/enabled',False); win.apply_classroom()
check('unlock restores bundled extension commands','triangle' in win.extension_manager.api.commands)
os.environ['SPARKY_SAFE_MODE']='1'; win.apply_classroom()
check('safe mode disables extension commands',not win.extension_manager.api.commands)
player=PlayerWindow('say "Hi"','Safe'); check('Player respects safe mode',not player.extensions.api.commands); player.close()
del os.environ['SPARKY_SAFE_MODE']; win.apply_classroom()
prefs.setValue('offline',True)
stub=SimpleNamespace(main=win,status=QLabel())
for method in (LibraryDialog.find,LibraryDialog.do_install,BoardsDialog.refresh,BoardsDialog.do_install,ArduinoPanel.set_up):
    method(stub); check('offline blocks '+method.__qualname__,'Offline' in stub.status.text())
with patch.object(win.extensions_panel,'run',side_effect=AssertionError('network called')):
    win.extensions_panel.featured_packs(); win.extensions_panel.search()
check('offline prevents extension requests','Offline' in win.extensions_panel.status.text())
win.new_tab(solution); assignment=AssignmentDialog(win,task); assignment.check_work()
end=time.monotonic()+4
while assignment.checker.isRunning() and time.monotonic()<end: qt.processEvents(); time.sleep(.005)
qt.processEvents(); check('native assignment dialog reports success','passed every check' in assignment.result.text()); assignment.close()
settings=SettingsDialog(win)
QTimer.singleShot(0,lambda:qt.activeModalWidget().accept()); settings.teacher_guide()
check('teacher guide opens offline',True); settings.reject()
for editor in win.editors(): editor.document().setModified(False)
win.close(); qt.processEvents()
print(f'{passed} classroom checks passed',flush=True)
