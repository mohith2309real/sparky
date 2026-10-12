"""Export native design tokens without importing Qt (usable in site builds)."""
import ast
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def tokens():
    result={}
    for node in ast.parse((ROOT/'sparky/ide/design.py').read_text()).body:
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
            try: result[node.targets[0].id]=ast.literal_eval(node.value)
            except (ValueError,TypeError): pass
        elif isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Tuple):
            try:
                result.update({key.id:value for key,value in zip(node.targets[0].elts,ast.literal_eval(node.value))})
            except (ValueError,TypeError,AttributeError): pass
    return result

def export(site):
    data=tokens(); colors=data['DAYLIGHT']
    values={k.replace('_','-'):v for k,v in colors.items() if isinstance(v,str) and v.startswith('#')}
    values.update({'radius-s':str(data['RADIUS_S'])+'px','radius-m':str(data['RADIUS_M'])+'px','radius-l':str(data['RADIUS_L'])+'px','space':str(data['SPACE'])+'px',
                   'font-ui':','.join('"'+v+'"' for v in data['UI_FONTS']),
                   'font-heading':','.join('"'+v+'"' for v in data['HEADING_FONTS']),
                   'font-code':','.join('"'+v+'"' for v in data['CODE_FONTS'])})
    css='/* Generated from sparky/ide/design.py. */\n:root{'+''.join('--'+k+':'+v+';' for k,v in values.items())+'}\n'
    site=Path(site); (site/'tokens.css').write_text(css)
    (site/'tokens.json').write_text(json.dumps(values,indent=2)+'\n')

if __name__=='__main__': export(ROOT.parent/'mohith-sites/sparky')
