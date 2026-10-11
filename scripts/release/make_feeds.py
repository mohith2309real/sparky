"""Sign the public featured extension catalog with the existing release key."""
import json
from common import SITES, envelope
items=[{'id':'shapes_plus','title':'Shapes+','description':'Real triangle and hexagon commands with a side length.'},
       {'id':'games_pack','title':'Games','description':'Teleport without drawing and celebrate a win.'},
       {'id':'music_plus','title':'Music+','description':'A short piano fanfare and a warm xylophone chime.'}]
path=SITES/'sparky'/'feeds'/'extensions.json'; path.parent.mkdir(parents=True,exist_ok=True)
payload={'product':'sparky','channel':'feed-extensions','version':'1.0.0','kind':'extensions','items':items}
path.write_text(json.dumps(envelope(payload),indent=1)+'\n')
print('Signed catalog:',path)
