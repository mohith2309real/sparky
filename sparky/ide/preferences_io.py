"""Portable appearance/editor preferences; credentials and locks are excluded."""
import json
from pathlib import Path
from .projects import atomic_write
KEYS={'theme','mode','font_size','code_font','ui_scale','reduce_motion','readable','thick_cursor',
      'color_blind','left_handed','read_aloud','app_language','mascot_color','stage_grid',
      'stage_color','volume','sounds','autosave','start_home','sound_events/run','sound_events/done','sound_events/error'}
LIMITS={'font_size':(10,28),'ui_scale':(90,150),'volume':(0,100)}
BOOLS={'reduce_motion','readable','thick_cursor','color_blind','left_handed','read_aloud',
       'stage_grid','sounds','autosave','start_home','sound_events/run','sound_events/done','sound_events/error'}


def export_settings(settings,path):
    values={key:settings.value(key,type=bool if key in BOOLS else int if key in LIMITS else str)
            for key in KEYS if settings.contains(key)}
    values={key:value for key,value in values.items() if isinstance(value,(str,int,float,bool))}
    atomic_write(path,json.dumps({'product':'sparky-settings','schema':1,'values':values},ensure_ascii=False,indent=2))


def import_settings(settings,path):
    if Path(path).stat().st_size>100000:
        raise ValueError('This settings file is too large.')
    value=json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(value,dict) or value.get('product')!='sparky-settings' or value.get('schema')!=1 or not isinstance(value.get('values'),dict):
        raise ValueError('Choose a Sparky settings file.')
    clean={}
    for key,item in value['values'].items():
        if key not in KEYS: continue
        if key in LIMITS:
            if isinstance(item,bool) or not isinstance(item,int) or not LIMITS[key][0]<=item<=LIMITS[key][1]:
                raise ValueError('Invalid value for '+key+'.')
        elif key in BOOLS:
            if not isinstance(item,bool): raise ValueError('Invalid toggle for '+key+'.')
        elif not isinstance(item,str) or len(item)>200:
            raise ValueError('Invalid preference '+key+'.')
        clean[key]=item
    for key,item in clean.items(): settings.setValue(key,item)
    settings.sync()
