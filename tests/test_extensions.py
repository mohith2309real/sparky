"""Real extension commands, isolation, enable controls and signed catalogs."""
import base64
import json
import shutil
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from sparky.lang import Interpreter, Runtime, SparkyError, parse
from sparky.ide.extension_manager import ExtensionAPI, ExtensionManager
from sparky.ide.feeds import read_feed
from sparky.update.manifest import ManifestError
passed=0
def check(name,condition):
    global passed
    assert condition,name
    passed+=1; print('  ok - '+name,flush=True)
class Capture(Runtime):
    def __init__(self): super().__init__(); self.lines=[]; self.output=[]; self.music=[]
    def line(self,*args): self.lines.append(args)
    def say(self,text): self.output.append(text)
    def play_music(self,*args): self.music.append(args)
def run(source,commands):
    runtime=Capture(); interpreter=Interpreter(parse(source,commands),runtime,commands=commands); interpreter.speed=10
    list(interpreter.run()); return interpreter,runtime
api=ExtensionAPI(); api.add_command('triangle',('side',),'repeat 3 times\nmove side\nturn 120\nend')
interpreter,runtime=run('set side to 12\ntriangle 80',api.commands)
check('new command draws real triangle',len(runtime.lines)==3 and abs(interpreter.x)<.01 and abs(interpreter.y)<.01)
check('command input does not overwrite globals',interpreter.globals['side']==12)
try: run('triangle',api.commands)
except SparkyError as error: good='input' in error.message and error.line==1
else: good=False
check('wrong command arity explained at caller line',good)
api.add_command('नमस्ते',('नाम',),'say नाम')
_,runtime=run('नमस्ते "Ada"',api.commands)
check('extension names and inputs support Unicode',runtime.output==['Ada'])
api.add_command('broken',(),'move missing')
try: run('say "start"\nbroken',api.commands)
except SparkyError as error: good='Inside extension command broken' in error.message and error.line==2
else: good=False
check('extension failures identify caller and command',good)
for name,params,body in [('say',(),'say 1'),('triangle',(),'say 1'),('bad name',(),'say 1'),('foo',('x','x'),'say 1'),('bar',(),'not_a_command')]:
    before=dict(api.commands)
    try: api.add_command(name,params,body)
    except (ValueError,SparkyError): rejected=True
    else: rejected=False
    check('invalid registration keeps prior commands: '+name,rejected and api.commands==before)
with tempfile.TemporaryDirectory() as tmp:
    folder=Path(tmp)/'extensions'; folder.mkdir()
    for path in Path('extensions').glob('*.py'): shutil.copy2(path,folder/path.name)
    settings=Path(tmp)/'enabled.json'
    manager=ExtensionManager(folder,settings); manager.discover()
    check('bundled packs all load',len(manager.extensions)==4 and not any(e.error for e in manager.extensions))
    for source,name in [('triangle 40','triangle'),('hexagon 20','hexagon'),('teleport 30 40','teleport'),('win','win'),('fanfare','fanfare'),('chime','chime')]:
        interpreter,runtime=run(source,manager.api.commands)
        check('bundled command runs: '+name, interpreter is not None)
    manager.set_enabled(folder/'shapes_plus.py',False)
    check('disable removes commands', 'triangle' not in manager.api.commands and any(not e.enabled for e in manager.extensions))
    manager=ExtensionManager(folder,settings); manager.discover()
    check('disable survives restart', 'triangle' not in manager.api.commands)
    manager.set_enabled(folder/'shapes_plus.py',True)
    check('enable restores command', 'triangle' in manager.api.commands)
    (folder/'bad.py').write_text('def register(api):\n api.add_command("temporary",(),"say 1")\n raise ValueError("oops")')
    manager.discover()
    check('broken pack rolls back partial registration', 'temporary' not in manager.api.commands and any(e.error for e in manager.extensions))
raw=(Path(__file__).parent/'fixtures'/'extensions.json').read_bytes()
check('signed catalog verifies', [i['id'] for i in read_feed(raw,'extensions')]==['shapes_plus','games_pack','music_plus'])
value=json.loads(raw); value['signed']=base64.b64encode(b'changed').decode()
for label,payload,kind in [('tampering',json.dumps(value).encode(),'extensions'),('wrong purpose',raw,'news'),('oversize',b' '*524289,'extensions')]:
    try: read_feed(payload,kind)
    except ManifestError: rejected=True
    else: rejected=False
    check('catalog rejects '+label,rejected)
print(f'{passed} extension checks passed',flush=True)
