"""Native accessibility preferences and core UI translation without changing code."""
import os
import sys
import tempfile
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'; os.environ['SPARKY_SETTINGS_FILE']=str(Path(tempfile.mkdtemp())/'settings.ini'); os.environ['SPARKY_NEW_WINDOW']='1'
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from PyQt6.QtWidgets import QApplication
from sparky.ide import app as appmod
from sparky.ide.i18n import translate
qt=QApplication(sys.argv[:1]); prefs=appmod.prefs.open_settings(); prefs.setValue('first_run_done',True); prefs.setValue('start_home',False); prefs.sync()
win=appmod.MainWindow(); win.show(); win.new_tab('say "नमस्ते తెలుగు"\n'); win.sound_bank.enabled=False
passed=0
def check(name,condition):
    global passed
    assert condition,name
    passed+=1; print('  ok - '+name,flush=True)
original=win.editor.toPlainText(); normal=win.editor.font().pointSizeF()
for key in ('readable','thick_cursor','color_blind','left_handed'): win.settings.setValue(key,True)
win.apply_accessibility(); qt.processEvents()
check('readable mode increases line height',win.editor.font().pointSizeF()>normal)
check('readable mode adds letter spacing',win.editor.font().letterSpacing()>0)
check('thicker cursor visible',win.editor.cursorWidth()==3)
check('stage goes left of editor',win.split.indexOf(win.stage_box)==1)
check('color-blind syntax uses distinguishable palette',win.editor.highlighter.formats['cmd'].foreground().color().name()=='#006b8f')
check('preferences do not change program or dirty state',win.editor.toPlainText()==original and not win.editor.document().isModified())
for language in ('hi','te','en'):
    win.settings.setValue('app_language',language); win.apply_accessibility(); win.set_running(False)
    check('Run button follows '+language,win.run_button.text()==translate('Run',language))
check('translation leaves code untouched',win.editor.toPlainText()==original)
check('icon controls have screen-reader names', all(win.activity_buttons[k].accessibleName() for k in win.activity_buttons))
win.set_theme('contrast')
check('high contrast theme works with accessibility',win.theme_key=='contrast')
said=[]
win.speaker.say=lambda text,volume=1:said.append(text) or True
win.settings.setValue('read_aloud',True); win.console_say('Hello')
check('read-aloud is opt-in',said==['Hello'])
win.settings.setValue('read_aloud',False); win.console_say('Quiet')
check('disabled read-aloud stays quiet',said==['Hello'])
for key in ('readable','thick_cursor','color_blind','left_handed'): win.settings.setValue(key,False)
win.apply_accessibility()
check('normal layout and text restore',win.split.indexOf(win.stage_box)==2 and win.editor.cursorWidth()==1 and abs(win.editor.font().pointSizeF()-normal)<.01)
for e in win.editors(): e.document().setModified(False)
win.close(); qt.processEvents()
print(f'{passed} accessibility checks passed',flush=True)
