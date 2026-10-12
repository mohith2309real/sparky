"""Small signed catalogs. No downloaded extension code is executed."""
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit
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
        if not isinstance(url,str) or (url and (urlsplit(url).scheme != 'https' or not urlsplit(url).hostname)):
            raise ManifestError('Feed links must use HTTPS.')
        if any(len(item[k])>10000 for k in ('id','title','description')):
            raise ManifestError('Feed text is too long.')
        if kind=='projects' and (not isinstance(item.get('code'),str) or not 0<len(item['code'])<=50000):
            raise ManifestError('Featured projects need bounded Sparky source.')
        items.append(dict(item))
    return items


def fetch(kind,cache_dir=None):
    if kind not in KINDS:
        raise ValueError('Unknown feed.')
    request=urllib.request.Request(SITE+'/feeds/'+kind+'.json',headers={'User-Agent':'Sparky/catalog'})
    with urllib.request.urlopen(request,context=ssl_context(),timeout=12) as response:
        raw=response.read(512*1024+1)
    items=read_feed(raw,kind)
    if cache_dir is not None:
        from .projects import atomic_write
        try:
            folder=Path(cache_dir); folder.mkdir(parents=True,exist_ok=True)
            atomic_write(folder/(kind+'.json'),raw.decode('utf-8'))
        except OSError:
            pass  # A read-only disk must not discard a verified response.
    return items


def cached(kind,cache_dir=None):
    """Reverify local envelopes; damaged caches fall back to bundled content."""
    from ..paths import ASSETS_DIR
    paths=([Path(cache_dir)/(kind+'.json')] if cache_dir is not None else [])
    paths.append(ASSETS_DIR/'feeds'/(kind+'.json'))
    for path in paths:
        try:
            with path.open('rb') as stream: raw=stream.read(512*1024+1)
            return read_feed(raw,kind)
        except (OSError,ValueError,ManifestError):
            continue
    return []
