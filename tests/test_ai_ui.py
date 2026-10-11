"""Exercise AI project history, offline guard and code previews without any network."""
import os
import sys
import tempfile
import time
from pathlib import Path
root=Path(tempfile.mkdtemp())
os.environ['QT_QPA_PLATFORM']='offscreen'; os.environ['SPARKY_SETTINGS_FILE']=str(root/'settings.ini'); os.environ['SPARKY_NEW_WINDOW']='1'
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication,QDialog,QPlainTextEdit
from sparky.ide import app as appmod, ai as aimod
from sparky.ide.ai_history import ChatStore
passed=0
def check(name,condition):
    global passed
    assert condition,name
    passed+=1; print('  ok - '+name,flush=True)
class MockWorker(aimod.AIWorker):
    seen=[]
    def run(self):
        self.seen.append((self.system,self.messages))
        time.sleep(.05)
        if not self._cancel: self.chunk.emit('Try this:\n```sparky\nsay "AI preview"\n```')
        self.done.emit()
aimod.AIWorker=MockWorker
qt=QApplication(sys.argv[:1]); prefs=appmod.prefs.open_settings(); prefs.setValue('first_run_done',True); prefs.setValue('start_home',False); prefs.sync()
win=appmod.MainWindow(); win.show(); panel=win.ai_panel
win.sound_bank.enabled=False
folder=win.project_store.create('One'); other=win.project_store.create('Two'); win.open_project(folder)
def pump(seconds=.15):
    end=time.monotonic()+seconds
    while time.monotonic()<end: qt.processEvents(); time.sleep(.005)
panel.ask('A small hint please'); pump()
check('default AI mode asks for hints', 'Tutor mode is on' in MockWorker.seen[0][0])
check('request includes only open file context', 'main.spark' in MockWorker.seen[0][1][-1]['content'])
check('chat persisted with assistant reply', len(ChatStore(win.project_store.root).load(folder))==2)
win.open_project(other); pump()
check('separate project gets separate chat', panel.history==[])
win.open_project(folder); pump()
check('returning to project restores history', len(panel.history)==2)
check('restored code reply offers preview', panel.insert_btn.isEnabled())
before=win.editor.toPlainText()
QTimer.singleShot(0,lambda:qt.activeModalWidget().reject())
panel.insert_code()
check('cancel preview leaves source unchanged', win.editor.toPlainText()==before)
QTimer.singleShot(0,lambda:qt.activeModalWidget().accept())
panel.insert_code()
check('accept preview inserts suggested code', 'AI preview' in win.editor.toPlainText())
seen=[]
def inspect_privacy():
    dialog=qt.activeModalWidget(); seen.append(dialog.findChild(QPlainTextEdit).toPlainText()); dialog.reject()
QTimer.singleShot(0,inspect_privacy); panel.show_privacy()
check('privacy lists context and recipient', 'Destination:' in seen[0] and 'last error' in seen[0] and 'Other projects and files are not attached' in seen[0])
win.settings.setValue('offline',True); count=len(MockWorker.seen); panel.ask('No network'); pump()
check('offline mode blocks AI request',len(MockWorker.seen)==count)
win.settings.setValue('offline',False); win.settings.setValue('ai_provider','Ollama (on this computer)'); win.settings.setValue('ai_model','mock-local')
win.on_error('An example error',0); pump()
check('configured local AI offers error help', not win.fix_ai_button.isHidden())
win.settings.setValue('offline',True); win.refresh_ai_actions()
check('offline hides error AI action', win.fix_ai_button.isHidden())
win.settings.setValue('offline',False)
panel.ask('Pending request'); panel.new_chat(); pump()
check('clear while streaming does not resurrect reply',panel.history==[] and ChatStore(win.project_store.root).load(folder)==[])
panel.ask('Next request'); pump()
check('new request works after cancelled clear',len(panel.history)==2)
store=panel.chat_store; renamed=win.project_store.rename(folder,'One renamed'); store.rename_project(folder,renamed)
check('rename keeps project chat',len(store.load(renamed))==2)
for e in win.editors(): e.document().setModified(False)
win.close(); pump()
print(f'{passed} AI UI checks passed',flush=True)
