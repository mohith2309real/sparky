"""Real lesson outcomes, local progress, version preservation and bundle validation."""
import datetime
import json
import sys
import tempfile
import zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sparky.ide.learning import Progress, check_program, daily_lesson
from sparky.ide.learning_data import LESSONS, WORLDS
from sparky.ide.projects import ProjectStore, read_json

passed = 0
def check(name, condition):
    global passed
    assert condition, name
    passed += 1
    print('  ok - '+name)

for lesson in LESSONS:
    ok, message = check_program(lesson, lesson['code'])
    check('solution: '+lesson['id']+' '+message, ok)
by_id = {l['id']: l for l in LESSONS}
check('cannot fake multiple input cases', not check_program(by_id['ask'], 'ask "Name?" into name\nsay "Hello, Ada!"')[0])
check('wrong square lengths rejected', not check_program(by_id['square'], 'repeat 4 times\nmove 10\nturn 90\nend')[0])
check('three circles do not meet shape challenge', not check_program(by_id['shapes'], 'fill color "red"\ncircle 30\ncircle 30\ncircle 30')[0])
check('checker bounded for endless loops', not check_program(by_id['until'], 'set score to 0\nrepeat until score = 10\nchange score by 3\nend\nsay score')[0])
check('checker can cancel', not check_program(by_id['first-line'], 'move 60', lambda: True)[0])
check('daily challenge stable for same date', daily_lesson(datetime.date(2026,10,10)) == daily_lesson(datetime.date(2026,10,10)))
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    progress = Progress(root/'progress.json')
    progress.complete(by_id['first-line'])
    check('unassisted completion three stars', progress.stars('first-line') == 3)
    progress.hint('square'); progress.hint('square'); progress.complete(by_id['square'])
    check('two hints one star', progress.stars('square') == 1)
    progress.hint('first-line'); progress.complete(by_id['first-line'])
    check('earned stars never reduced', progress.stars('first-line') == 3)
    newly = [progress.complete(l) for l in LESSONS if l['world'] == 'draw']
    check('world completion awarded once', sum(newly) == 1 and not progress.complete(by_id['star-art']))
    for _ in range(100): progress.record_run()
    check('progress survives restart', Progress(progress.path).stars('square') == 1)
    check('achievement milestones recorded', '100 runs' in progress.badges() and 'Draw explorer' in progress.badges())
    check('report escapes learner name', '&lt;script&gt;' in progress.report('<script>') and '<script>' not in progress.report('<script>'))
    progress.path.write_text('{broken')
    check('corrupt progress resets safely', Progress(progress.path).stars('square') == 0)
    store = ProjectStore(root/'user')
    folder = store.create('नया Project', 'Art'); path = folder/'main.spark'
    first = path.read_text(); store.save(path, 'say "new"\n')
    texts = [read_json(p,{})['text'] for p in store.versions(path)]
    check('versions preserve old and new text', first in texts and 'say "new"\n' in texts)
    before = len(texts); store.save(path,'say "new"\n')
    check('unchanged save does not duplicate version', len(store.versions(path)) == before)
    (folder/'assets'/'sound.wav').write_bytes(b'RIFFsample')
    outside = root/'outside.txt'; outside.write_text('private')
    (folder/'assets'/'link.txt').symlink_to(outside)
    copy = store.duplicate(folder)
    check('duplicate has code and excludes symlinks', (copy/'main.spark').read_text() == path.read_text() and not (copy/'assets'/'link.txt').exists())
    renamed = store.rename(folder, 'Renamed'); path = renamed/'main.spark'
    check('rename retains version history', len(store.versions(path)) == before)
    bundle = store.bundle(renamed, root/'demo.sparky'); imported = store.import_bundle(bundle)
    check('bundle roundtrip includes assets', (imported/'assets'/'sound.wav').read_bytes() == b'RIFFsample' and (imported/'main.spark').read_text() == path.read_text())
    check('bundle excludes external symlink', not (imported/'assets'/'link.txt').exists())
    for label, entries in [('traversal', [('main.spark','say 1'),('../escape.txt','bad')]),
                           ('case collision',[('main.spark','say 1'),('MAIN.spark','say 2')]),
                           ('file folder collision',[('main.spark','say 1'),('assets/a.txt','a'),('assets/a.txt/b.txt','b')]),
                           ('assets is file',[('main.spark','say 1'),('assets','a')])]:
        bad = root/(label+'.sparky')
        with zipfile.ZipFile(bad,'w') as z:
            for name,text in entries: z.writestr(name,text)
        count = len(store.list())
        try: store.import_bundle(bad)
        except ValueError: rejected = True
        else: rejected = False
        check(label+' rejected before project creation', rejected and len(store.list()) == count)
    store.save_recovery([{'text':'unsaved'}], active=0)
    check('recovery survives new store instance', ProjectStore(store.root).load_recovery()['tabs'][0]['text'] == 'unsaved')
    bad = root/'not-a-zip.sparky'; bad.write_text('broken')
    try: store.import_bundle(bad)
    except ValueError: rejected=True
    else: rejected=False
    check('damaged bundle gives a friendly error', rejected)
print(f'{passed} learning and project checks passed')
