"""Feed integrity, purpose separation and damaged-cache recovery."""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sparky.ide import feeds
from sparky.paths import ASSETS_DIR
from sparky.update.manifest import ManifestError

passed = 0
def check(name, condition):
    global passed
    assert condition, name
    passed += 1
    print('  ok -', name)

raw = (ASSETS_DIR / 'feeds/projects.json').read_bytes()
projects = feeds.read_feed(raw, 'projects')
check('Real signed project source verifies', len(projects) == 3 and all(p['code'] for p in projects))
for label, value, kind in [('wrong purpose', raw, 'news'), ('oversize', b' ' * 524289, 'projects'),
                           ('invalid envelope', b'{}', 'projects')]:
    try: feeds.read_feed(value, kind)
    except ManifestError: rejected = True
    else: rejected = False
    check('Rejects ' + label, rejected)
with tempfile.TemporaryDirectory() as tmp:
    (Path(tmp) / 'projects.json').write_text('{broken')
    check('Damaged cache falls back to verified bundled projects', feeds.cached('projects', tmp) == projects)
    (Path(tmp) / 'projects.json').write_bytes(raw)
    check('Valid cache is reverified', feeds.cached('projects', tmp) == projects)
for change in ({'code': None}, {'code': 'x' * 50001}, {'url': 'https://'}, {'url': 'file:///tmp/a'}):
    entry = dict(projects[0], **change)
    with patch.object(feeds, 'read', return_value={'kind': 'projects', 'items': [entry]}):
        try: feeds.read_feed(b'{}', 'projects')
        except ManifestError: rejected = True
        else: rejected = False
    check('Rejects malformed project ' + next(iter(change)), rejected)
print(f'{passed} feed checks passed.')
