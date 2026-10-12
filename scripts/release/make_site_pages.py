"""Build featured pages from verified feeds; downloads verify the live manifest."""
import html
import sys
from common import REPO,SITES
sys.path.insert(0,str(REPO))
from sparky.ide.feeds import read_feed
site=SITES/'sparky'
def page(title,body,script=''):
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+' · Sparky</title><link rel="icon" href="logo.png"><link rel="stylesheet" href="site.css?v=3.0.0"></head><body><nav class="wrap nav"><a class="brand" href="index.html"><img src="logo.png" alt="">Sparky</a><a href="index.html#playground">Try it</a><a href="projects.html">Projects</a><a href="docs.html">Reference</a><a href="downloads.html">Downloads</a></nav><main class="wrap band">'+body+'</main><footer class="wrap footer"><span>Made by <a href="https://mohith2309.web.app">Mohith</a>.</span><a href="faq.html">FAQ</a><a href="verify.html">Verify a download</a><a href="releases.html">Release notes</a></footer>'+script+'</body></html>'
projects=read_feed((site/'feeds/projects.json').read_bytes(),'projects')
parts=[]
for item in projects:
    name=item['id']+'.spark'; folder=site/'featured'; folder.mkdir(exist_ok=True)
    (folder/name).write_text(item['code'],encoding='utf-8')
    parts.append('<article class="project"><p class="eyebrow">REMIX AN IDEA</p><h2>'+html.escape(item['title'])+'</h2><p>'+html.escape(item['description'])+'</p><pre><code>'+html.escape(item['code'])+'</code></pre><a class="btn" download href="featured/'+name+'">Open in Sparky ↓</a></article>')
body='<p class="eyebrow">A PLACE TO BEGIN</p><h1>Make it your own.</h1><p class="lede">Three little projects with room for your ideas. Download a copy, open it in Sparky, and change something.</p><div class="projects-grid">'+''.join(parts)+'</div><p class="small">These are the same featured projects shown on Home in the app. This page is built from the <a href="feeds/projects.json">verified signed project feed</a>.</p>'
(site/'projects.html').write_text(page('Featured projects',body),encoding='utf-8')
body='''<p class="eyebrow">A STAGE FOR YOUR NEXT IDEA</p><h1>Bring Sparky home.</h1><p class="lede">Choose your computer. The native app includes lessons, examples and everything you need to start writing Sparky programs.</p><p id="release-status" role="status">Checking the signed release information…</p><div class="download-grid" id="downloads"></div><section><h2>Know what you’re opening.</h2><p>Each final release has SHA-256 checksums and an Ed25519 signature. The app verifies its updates automatically. <a href="verify.html">Learn how to check a download →</a></p><p id="checksum-links"></p><p class="small">Mac builds support Apple silicon. Intel Mac support is planned for later. Linux needs Python 3.10 or newer and system graphics libraries. macOS builds are ad-hoc signed and are not notarized.</p><h2>Updates that come to you.</h2><p>Already using Sparky? Check for updates in Settings. Updates are signed, and your projects stay on your computer. <a href="releases.html">Read the release notes →</a></p></section>'''
(site/'downloads.html').write_text(page('Downloads',body,'<script src="downloads.js"></script>'),encoding='utf-8')
print('Generated featured projects and downloads pages.')

from sparky.ide.whats_new import RELEASES, pretty_version
articles=[]
for release in RELEASES:
    articles.append('<article class="release" id="v'+release['version']+'"><p class="eyebrow">'+html.escape(release['date'])+'</p><h2>Sparky '+html.escape(pretty_version(release['version']))+'</h2><h3>'+html.escape(release['title'])+'</h3><ul>'+''.join('<li>'+html.escape(item)+'</li>' for item in release['items'])+'</ul></article>')
(site/'releases.html').write_text(page('Release notes','<p class="eyebrow">THE STORY SO FAR</p><h1>A little more possible.</h1><p class="lede">What changed, what improved, and what you can make next.</p>'+''.join(articles)),encoding='utf-8')
