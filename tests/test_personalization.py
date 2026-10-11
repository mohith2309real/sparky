"""Qt theme preview, extension toggles, fonts and credential-free settings."""
import json
import os
import sys
import tempfile
from pathlib import Path
root=Path(tempfile.mkdtemp()); os.environ['QT_QPA_PLATFORM']='offscreen'; os.environ['SPARKY_SETTINGS_FILE']=str(root/'settings.ini'); os.environ['SPARKY_NEW_WINDOW']='1'
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from PyQt6.QtCore import QTimer,Qt,QSettings
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication
from sparky.ide import app as appmod, mascot
from sparky.ide.settings_dialog import SettingsDialog
from sparky.ide.preferences_io import export_settings, import_settings
from sparky.ide.extension_manager import ExtensionManager
import shutil
qt=QApplication(sys.argv[:1]); prefs=appmod.prefs.open_settings(); prefs.setValue('first_run_done',True); prefs.setValue('start_home',False); prefs.sync()
win=appmod.MainWindow(); win.show(); win.sound_bank.enabled=False
passed=0
def check(name,condition):
    global passed
    assert condition,name
    passed+=1; print('  ok - '+name,flush=True)
folder=root/'packs'; folder.mkdir()
for p in Path('extensions').glob('*.py'): shutil.copy2(p,folder/p.name)
win.extension_manager=ExtensionManager(folder,root/'enabled.json'); win.extension_manager.discover(); win.refresh_extension_commands(); win.extensions_panel.refresh_installed()
index=next(i for i in range(win.extensions_panel.installed.count()) if 'Shapes+' in win.extensions_panel.installed.item(i).text())
win.extensions_panel.installed.setCurrentRow(index); win.extensions_panel.toggle_pack()
check('UI disables a pack', 'triangle' not in win.extension_manager.api.commands)
index=next(i for i in range(win.extensions_panel.installed.count()) if 'shapes_plus' in win.extensions_panel.installed.item(i).text())
win.extensions_panel.installed.setCurrentRow(index); win.extensions_panel.toggle_pack()
check('UI re-enables a pack', 'triangle' in win.extension_manager.api.commands)
win.new_tab('triangle 40'); win.editor.check_code()
check('live checker understands extension commands',win.editor.problem is None)
win.extensions_panel.show_featured([{'id':'music_plus','title':'Music+','description':'A chime'}])
check('featured list presents signed catalog entries',win.extensions_panel.results.count()==1)
dialog=SettingsDialog(win); original=win.theme_key; dialog.theme.setCurrentIndex(dialog.theme.findData('midnight'))
seen=[]
def capture_preview():
    modal=qt.activeModalWidget(); seen.append(modal.windowTitle()); modal.reject()
QTimer.singleShot(0,capture_preview); dialog.preview_theme()
check('theme preview does not change working theme',win.theme_key==original and seen==['Theme preview'])
dialog.code_font.setCurrentFont(QFont('Courier New')); dialog.mascot_color='#4d8ac9'; dialog.apply_and_close()
check('font choice applied to editors',win.code_font==win.editor.font().family())
check('mascot color applied',mascot.BODY=='#4d8ac9')
win.settings.setValue('ai_key','test-credential-not-exported'); win.settings.setValue('classroom/pin_hash','test-lock-not-exported')
win.settings.setValue('readable',True); win.settings.setValue('font_size',19); win.settings.sync()
path=root/'prefs.json'; export_settings(win.settings,path)
check('settings export excludes credentials and locks','test-credential' not in path.read_text() and 'test-lock' not in path.read_text())
other=QSettings(str(root/'other.ini'),QSettings.Format.IniFormat); import_settings(other,path)
check('settings roundtrip keeps typed values',other.value('font_size',type=int)==19 and other.value('readable',type=bool))
bad={'product':'sparky-settings','schema':1,'values':{'font_size':99,'mode':'pro'}}; path.write_text(json.dumps(bad))
try: import_settings(other,path)
except ValueError: rejected=True
else: rejected=False
check('invalid import applies nothing',rejected and other.value('font_size',type=int)==19)
for e in win.editors(): e.document().setModified(False)
win.close(); qt.processEvents()
print(f'{passed} personalization checks passed',flush=True)
