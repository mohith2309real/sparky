"""Check music execution, validation, synthesis and real Qt piano insertion."""
import os
import sys
import tempfile
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ['SPARKY_SETTINGS_FILE']=str(Path(tempfile.mkdtemp())/'settings.ini')
os.environ['SPARKY_NEW_WINDOW']='1'
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from sparky.lang import Interpreter, Runtime, SparkyError, parse
from sparky.lang.music import INSTRUMENTS, SOUND_NAMES, parse_notes, frequency
from sparky.lang.to_python import to_python
from sparky.ide.sounds import RATE, synthesize
passed=0
def check(name,condition):
    global passed
    assert condition,name
    passed+=1; print('  ok - '+name,flush=True)
class Capture(Runtime):
    def __init__(self): super().__init__(); self.music=[]; self.old=[]
    def play_music(self,instrument,notes,duration): self.music.append((instrument,notes,duration))
    def play_sound(self,name,note,duration): self.old.append((name,note,duration))
def run(source):
    runtime=Capture(); ticks=list(Interpreter(parse(source),runtime).run()); return runtime,ticks
runtime,ticks=run('tempo 60\ninstrument "flute"\nplay song "C D R E"\nrest 2\nplay chord "C4 E4 G4" for 0.2')
check('song notes and rest preserve order',runtime.music[:3]==[('flute',[60],1),('flute',[62],1),('flute',[64],1)])
check('chord notes played together',runtime.music[3]==('flute',[60,64,67],.2))
check('tempo controls notes and beat rests', [t[1] for t in ticks if t[0]=='wait' and t[-1] is not None]==[1,1,1,1,2,.2])
check('accidentals and octaves parsed',parse_notes('C#4 Db4 A5 C0 B8')==[61,61,81,12,119])
check('concert A frequency',abs(frequency(69)-440)<.001)
runtime,_=run('play note 4 for 0.25')
check('old numeric notes keep runtime API',runtime.old==[('',4,.25)])
runtime,_=run('instrument "organ"\nplay note 8')
check('numeric notes honor chosen instrument',runtime.music==[('organ',[72],.4)])
for source in ['tempo 0','tempo 400','rest -1','rest 100','instrument "kazoo"','play song "H"','play chord "C D E F G A B C D"','play song "C" for 20','play song 42']:
    try: run(source)
    except SparkyError: bad=True
    else: bad=False
    check('friendly invalid music: '+source,bad)
check('twenty additional sounds',len(SOUND_NAMES)==27)
for sound in SOUND_NAMES:
    samples=synthesize(sound)
    check('audible bounded samples: '+sound,bool(samples) and any(samples) and max(samples)<=32767 and min(samples)>=-32768)
voices=[]
for instrument in INSTRUMENTS:
    samples=synthesize(('music',instrument,(60,64,67),.1))
    check('chord synthesis: '+instrument,len(samples)==int(RATE*.1) and any(samples) and max(map(abs,samples))<=30000)
    voices.append(samples)
check('five distinct instrument waveforms',len({tuple(v) for v in voices})==5)
code=to_python('tempo 120\ninstrument "piano"\nplay song "C R E" for 0.01\nplay chord "C E G" for 0.01\nrest 0')
compile(code,'music translation','exec')
check('music translates to standalone Python', 'time.sleep' in code and '.split()' in code)
from PyQt6.QtWidgets import QApplication
from sparky.ide import app as appmod
from sparky.ide.music_panel import MusicDialog
qt=QApplication(sys.argv[:1]); prefs=appmod.prefs.open_settings(); prefs.setValue('first_run_done',True); prefs.setValue('start_home',False); prefs.sync()
win=appmod.MainWindow(); win.sound_bank.enabled=False
win.new_file(); dialog=MusicDialog(win); dialog.show(); qt.processEvents()
dialog.instrument.setCurrentText('guitar'); dialog.duration.setValue(.3); dialog.play_note('C#4')
check('piano inserts playable code',win.editor.toPlainText()=='instrument "guitar"\nplay song "C#4" for 0.3\n')
runtime,_=run(win.editor.toPlainText())
check('piano-generated code runs',runtime.music==[('guitar',[61],.3)])
dialog.insert.setChecked(False); before=win.editor.toPlainText(); dialog.play_note('D4')
check('preview without changing code',win.editor.toPlainText()==before)
dialog.list.setCurrentRow(SOUND_NAMES.index('coin')); dialog.insert_sound()
check('library inserts chosen sound', 'play "coin"' in win.editor.toPlainText())
shots=Path('build/alpha5-checks/screenshots'); shots.mkdir(parents=True,exist_ok=True); dialog.grab().save(str(shots/'piano.png'))
dialog.close()
for editor in win.editors(): editor.document().setModified(False)
win.close(); qt.processEvents()
print(f'{passed} music checks passed',flush=True)
