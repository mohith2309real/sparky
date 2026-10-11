"""Local classroom locks, checked assignments, hand-ins and time on task."""
import datetime
import hashlib
import hmac
import json
import math
import os
import zipfile
from pathlib import Path
from .projects import BUNDLE_SUFFIXES, atomic_write, read_json


def set_pin(settings,pin):
    if not pin.isdigit() or not 4<=len(pin)<=12:
        raise ValueError('Choose a PIN with 4 to 12 digits.')
    salt=os.urandom(16)
    digest=hashlib.pbkdf2_hmac('sha256',pin.encode(),salt,200000)
    settings.setValue('classroom/pin_salt',salt.hex()); settings.setValue('classroom/pin_hash',digest.hex())
    settings.sync()


def verify_pin(settings,pin):
    try:
        salt=bytes.fromhex(settings.value('classroom/pin_salt','',type=str))
        expected=settings.value('classroom/pin_hash','',type=str)
        if len(salt)!=16 or len(expected)!=64: return False
        got=hashlib.pbkdf2_hmac('sha256',pin.encode(),salt,200000).hex()
        return hmac.compare_digest(got,expected)
    except (ValueError,TypeError): return False


def blocked(settings,feature):
    return settings.value('classroom/enabled',False,type=bool) and settings.value('classroom/hide_'+feature,True,type=bool)


def read_task(path):
    path=Path(path)
    if path.stat().st_size>256000: raise ValueError('This assignment is too large.')
    def invalid_constant(value): raise ValueError('Assignment numbers must be finite.')
    def finite_float(value):
        result=float(value)
        if not math.isfinite(result): raise ValueError('Assignment numbers must be finite.')
        return result
    data=json.loads(path.read_text(encoding='utf-8'),parse_constant=invalid_constant,parse_float=finite_float)
    if not isinstance(data,dict) or data.get('product')!='sparky-task' or data.get('schema')!=1:
        raise ValueError('Choose a Sparky assignment file.')
    for key,limit in [('title',200),('instructions',10000),('starter',100000)]:
        if not isinstance(data.get(key),str) or len(data[key])>limit: raise ValueError('Invalid assignment '+key+'.')
    checks=data.get('checks')
    if not isinstance(checks,dict) or not checks or set(checks)-{'output','cases','lines','lengths','position','shapes','filled','stamps','variables','sprites','events','shape_kinds'}:
        raise ValueError('The assignment needs supported checks.')
    for key in ('lines','shapes','filled','stamps'):
        if key in checks and (not isinstance(checks[key],int) or not 0<=checks[key]<=10000): raise ValueError('Invalid drawing check.')
    def output_ok(output): return isinstance(output,list) and len(output)<=100 and all(isinstance(v,str) and len(v)<=10000 for v in output)
    if 'output' in checks and not output_ok(checks['output']): raise ValueError('Console checks need a list of text lines.')
    if 'cases' in checks:
        if not isinstance(checks['cases'],list) or not 1<=len(checks['cases'])<=20: raise ValueError('Use 1 to 20 answer cases.')
        for case in checks['cases']:
            if not isinstance(case,list) or len(case)!=2 or not isinstance(case[0],list) or len(case[0])>20 or not output_ok(case[1]): raise ValueError('Invalid answer case.')
            if any(not isinstance(v,(str,int,float)) for v in case[0]): raise ValueError('Test answers must be text or numbers.')
            case[0]=[str(v) for v in case[0]]
    def numbers(value,count=None):
        return isinstance(value,list) and len(value)<=1000 and (count is None or len(value)==count) and all(isinstance(v,(int,float)) and not isinstance(v,bool) for v in value)
    if 'position' in checks and not numbers(checks['position'],2): raise ValueError('A position needs two numbers.')
    if 'lengths' in checks and not numbers(checks['lengths']): raise ValueError('Line lengths need a list of numbers.')
    for key in ('variables','sprites'):
        if key in checks and (not isinstance(checks[key],dict) or len(checks[key])>100): raise ValueError('Invalid '+key+' check.')
    if 'sprites' in checks and any(not numbers(v,2) for v in checks['sprites'].values()): raise ValueError('Sprite positions need two numbers.')
    if 'shape_kinds' in checks and (not isinstance(checks['shape_kinds'],list) or any(v not in ('circle','rectangle','star','polygon','dot','arc') for v in checks['shape_kinds'])): raise ValueError('Invalid shape names.')
    if 'events' in checks:
        events=checks['events']
        if not isinstance(events,list) or len(events)>20: raise ValueError('Use at most 20 test events.')
        for event in events:
            if not isinstance(event,list) or not event or event[0] not in ('key','click','stage_click'): raise ValueError('Invalid test event.')
            if event[0]=='stage_click' and not numbers(event[1:],2): raise ValueError('Clicks need two coordinates.')
            if event[0] in ('key','click') and (len(event)!=2 or not isinstance(event[1],str)): raise ValueError('Keys and sprites need a name.')
    requires=data.get('requires',[])
    if not isinstance(requires,list) or len(requires)>30 or any(not isinstance(v,str) or len(v)>80 for v in requires): raise ValueError('Invalid required commands.')
    return {'id':'assignment-'+hashlib.sha256(path.read_bytes()).hexdigest()[:16], 'world':'assignment',
            'title':data['title'],'explain':data['instructions'],'goal':data['instructions'],
            'code':data['starter'],'starter':data['starter'],'checks':checks,'requires':requires}


def export_handin(path,code,name,task=None,project=None,seconds=0):
    metadata={'product':'sparky-handin','schema':1,'learner':name[:200], 'assignment':task['title'] if task else '',
              'date':datetime.datetime.now().isoformat(timespec='seconds'),'time_seconds':int(seconds)}
    entries=[]
    if project:
        project=Path(project)
        for item in sorted(project.rglob('*')):
            rel=item.relative_to(project)
            if (item.is_file() and not item.is_symlink() and item.resolve().is_relative_to(project.resolve())
                    and not any(p.startswith('.') for p in rel.parts) and item.suffix.lower() in BUNDLE_SUFFIXES
                    and rel.as_posix() not in ('main.spark','submission.json')):
                entries.append((item,rel.as_posix()))
        if len(entries)>1000 or sum(p.stat().st_size for p,_ in entries)>128*1024*1024:
            raise ValueError('This hand-in is too large.')
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('main.spark',code)
        archive.writestr('submission.json',json.dumps(metadata,ensure_ascii=False,indent=2))
        for item,rel in entries: archive.write(item,rel)


class TimeTracker:
    def __init__(self,path):
        self.path=Path(path); self.data=read_json(path,{})
        value=self.data.get('seconds',0)
        self.seconds=value if isinstance(value,int) and value>=0 else 0
        self.since_break=0

    def advance(self,elapsed,active=True,reminders=False,minutes=20):
        if not active: return False
        elapsed=max(0,min(2,elapsed)); self.seconds+=elapsed; self.since_break+=elapsed
        if reminders and self.since_break>=minutes*60:
            self.since_break=0
            return True
        return False

    def save(self):
        atomic_write(self.path,json.dumps({'seconds':int(self.seconds)}))
