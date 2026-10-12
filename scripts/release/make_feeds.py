"""Sign the public featured extension catalog with the existing release key."""
import json
from common import SITES, REPO, envelope, version
items=[{'id':'shapes_plus','title':'Shapes+','description':'Real triangle and hexagon commands with a side length.'},
       {'id':'games_pack','title':'Games','description':'Teleport without drawing and celebrate a win.'},
       {'id':'music_plus','title':'Music+','description':'A short piano fanfare and a warm xylophone chime.'}]
projects=[]
for slug,title,description in [
    ('flower','A flower made of loops','Change the turns and colors to grow your own pattern.'),
    ('catch_the_star','Catch the star','Make a small game, then change its rules.'),
    ('music','Make a melody','Try notes, rests and instruments in a short song.')]:
    projects.append(dict(id=slug,title=title,description=description,
                         code=(REPO/'examples'/(slug+'.spark')).read_text(encoding='utf-8')))
news=[dict(id='sparky3',title='Sparky 3 is here',
           description='Explore thirty lessons, make music, build a game, or open a featured project and make it your own.',
           url='https://sparky-code.web.app/releases')]
for kind,entries in [('extensions',items),('projects',projects),('news',news)]:
    payload={'product':'sparky','channel':'feed-'+kind,'version':version(),'kind':kind,'items':entries}
    raw=json.dumps(envelope(payload),indent=1)+'\n'
    for folder in (SITES/'sparky'/'feeds',REPO/'assets'/'feeds'):
        folder.mkdir(parents=True,exist_ok=True)
        path=folder/(kind+'.json'); path.write_text(raw,encoding='utf-8')
        print('Signed catalog:',path)
