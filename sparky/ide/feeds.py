"""Small signed catalogs. No downloaded extension code is executed."""
import urllib.request
from ..update.manifest import ManifestError, read
from .vscode import ssl_context
SITE='https://sparky-code.web.app'
KINDS=('extensions','news','projects')


def read_feed(raw,kind,keys=None):
    if kind not in KINDS or len(raw)>512*1024:
        raise ManifestError('Unknown or oversized feed.')
    data=read(raw,'feed-'+kind,keys)
    if data.get('kind')!=kind or not isinstance(data.get('items'),list) or len(data['items'])>100:
        raise ManifestError('Invalid feed contents.')
    items=[]
    for item in data['items']:
        if not isinstance(item,dict) or any(not isinstance(item.get(k),str) for k in ('id','title','description')):
            raise ManifestError('Invalid feed item.')
        url=item.get('url','')
        if url and (not isinstance(url,str) or not url.startswith('https://')):
            raise ManifestError('Feed links must use HTTPS.')
        if any(len(item[k])>10000 for k in ('id','title','description')):
            raise ManifestError('Feed text is too long.')
        items.append(dict(item))
    return items


def fetch(kind):
    if kind not in KINDS:
        raise ValueError('Unknown feed.')
    request=urllib.request.Request(SITE+'/feeds/'+kind+'.json',headers={'User-Agent':'Sparky/catalog'})
    with urllib.request.urlopen(request,context=ssl_context(),timeout=12) as response:
        raw=response.read(512*1024+1)
    return read_feed(raw,kind)
