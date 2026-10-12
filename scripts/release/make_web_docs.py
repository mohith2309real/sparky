"""Generate the website reference from the same help data used in the editor."""
import html
import json
import shutil
import sys
from pathlib import Path
from common import REPO, SITES
sys.path.insert(0,str(REPO))
from sparky.ide import docs
from export_design import export

site=SITES/'sparky'
export(site)
fonts=site/'fonts'; fonts.mkdir(exist_ok=True)
for path in (REPO/'assets'/'fonts').iterdir():
    if path.is_file(): shutil.copy2(path,fonts/path.name)
css='''@font-face{font-family:Figtree;src:url(fonts/Figtree.ttf);font-display:swap}
@font-face{font-family:Bricolage;src:url(fonts/BricolageGrotesque.ttf);font-display:swap}
@font-face{font-family:JetBrains;src:url(fonts/JetBrainsMono.ttf);font-display:swap}
:root{--bg:#faf9f5;--ink:#141413;--muted:#6f6d66;--line:#e2ded2;--accent:#9d422b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.65 Figtree,system-ui,sans-serif}
main,nav,footer{max-width:1040px;margin:auto;padding:28px 24px}nav{display:flex;align-items:center;gap:24px;border-bottom:1px solid var(--line)}nav .brand{margin-right:auto;font:800 23px Bricolage,system-ui,sans-serif;color:var(--ink);text-decoration:none}
a{color:var(--accent);text-underline-offset:4px}h1,h2,h3{font-family:Bricolage,system-ui,sans-serif}h1{font-size:clamp(38px,7vw,66px);line-height:1.05;letter-spacing:-2px;margin:20px 0}h2{font-size:29px;margin-top:42px}h3{font-size:22px;margin:0 0 10px}.eyebrow{font-size:13px;letter-spacing:2px;font-weight:700;color:var(--muted)}.lede{max-width:720px;font-size:21px;color:var(--muted)}
pre{background:#eeece5;padding:20px;border-radius:14px;white-space:pre-wrap;overflow-wrap:anywhere}code{font:14px/1.6 JetBrains,ui-monospace,monospace}input{width:100%;font:inherit;padding:15px;border:1px solid var(--line);border-radius:12px;background:#fffefb}.entries{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:22px;margin-top:30px}.entry{border-top:1px solid var(--line);padding:24px 0;scroll-margin-top:24px}.entry p{margin-top:0}.entry[hidden]{display:none}.entry small{color:var(--muted)}details{border-top:1px solid var(--line);padding:22px 0}summary{font-size:23px;font-weight:700;cursor:pointer}footer{border-top:1px solid var(--line);margin-top:48px}a:focus-visible,input:focus-visible,summary:focus-visible{outline:3px solid #006b8f;outline-offset:4px}@media(max-width:650px){.entries{grid-template-columns:1fr}nav{gap:14px;flex-wrap:wrap}main,nav,footer{padding:22px 18px}.lede{font-size:19px}}'''
css='@import url("tokens.css");\n'+css.replace(':root{--bg:#faf9f5;--ink:#141413;--muted:#6f6d66;--line:#e2ded2;--accent:#9d422b}', ':root{--ink:var(--text)}').replace('color:var(--accent);text-underline', 'color:var(--syn-cmd);text-underline')
(site/'docs.css').write_text(css)
def page(title,description,body,script=''):
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(title)+' · Sparky</title><meta name="description" content="'+html.escape(description,quote=True)+'"><link rel="icon" href="logo.png"><link rel="stylesheet" href="docs.css"></head><body><nav><a class="brand" href="/">⚡ Sparky</a><a href="docs">Reference</a><a href="teachers">Teachers</a><a href="faq">FAQ</a><a href="releases">Releases</a></nav><main>'+body+'</main><footer>Made by <a href="https://mohith2309.web.app">Mohith</a> · <a href="verify">Check a download</a></footer>'+script+'</body></html>'
entries=[]; rows=[]
for group,data in [('Commands',docs.COMMANDS),('Functions',docs.FUNCTIONS),('Values',docs.VALUES)]:
    for word,(description,example) in data.items():
        rows.append({'group':group,'word':word,'description':description,'example':example})
        entries.append('<article class="entry" id="'+html.escape(group.lower()+'-'+word,quote=True)+'"><small>'+group+'</small><h3>'+html.escape(word)+'</h3><p>'+html.escape(description)+'</p><pre><code>'+html.escape(example)+'</code></pre></article>')
body='<p class="eyebrow">THE SPARKY LANGUAGE</p><h1>Small words.<br>Big possibilities.</h1><p class="lede">The same reference you see when you hover over code in Sparky. Search a command, find an example, and try it in the app.</p><label for="find">Find a command, function or value</label><input id="find" type="search" placeholder="Try repeat, sprite, song or Arduino" autocomplete="off"><p id="count" role="status">'+str(len(rows))+' entries</p><div class="entries">'+''.join(entries)+'</div><p>Examples show command syntax. A block opener such as <code>if</code> needs its body and <code>end</code>; an expression needs a command such as <code>say</code> to display its result.</p>'
script='''<script>const entries=[...document.querySelectorAll('.entry')],find=document.querySelector('#find'),count=document.querySelector('#count');find.addEventListener('input',()=>{const term=find.value.trim().toLowerCase();let shown=0;for(const row of entries){row.hidden=!row.textContent.toLowerCase().includes(term);if(!row.hidden)shown++}count.textContent=shown+' entries'});</script>'''
(site/'docs.html').write_text(page('Language reference','Search Sparky commands, functions and values with examples generated from the app.',body,script))
(site/'reference.json').write_text(json.dumps({'product':'sparky-reference','entries':rows},ensure_ascii=False,indent=1)+'\n')
questions=[
('What is Sparky?','An English-like programming language and native coding app made by Mohith. Programs draw on a stage, tell stories, make games and music, or control Arduino boards.'),
('Does it cost money or need an account?','Sparky is free and does not require a student account. Built-in lessons and coding work offline. Optional AI providers may have their own accounts and costs; local AI is an alternative.'),
('Which computers can use it?','The downloads cover Apple silicon Macs, Windows x86_64, and Linux x86_64 or arm64. The Linux package needs Python 3.10 or later and system graphics libraries. Intel Mac support is planned for later.'),
('Does it work without internet?','Lessons, coding, assignment checks and hand-ins work offline. Offline mode pauses AI, updates, extension catalogs and Arduino downloads. Install board packages and optional tools before going offline.'),
('What happens to my programs?','Projects and learning progress stay on your computer. Autosave keeps drafts, saved versions preserve older files, and project bundles include code and assets. Hand-ins are local ZIPs until you share them yourself.'),
('Is AI required?','No. The tutor defaults to hints. You can see what will be sent and preview suggested code before inserting it. Provider requests include the open file, relevant error and chat context. Local AI presets include Ollama and LM Studio.'),
('Can I use Python or Arduino?','Yes. Sparky includes a Python track, a Sparky-to-Python export, and an Arduino workspace with Verify, Upload and serial tools. Some stage features do not translate to Python; the exporter explains unsupported commands.'),
('What is Classroom mode?','A teacher PIN locks Settings and can hide AI and disable extensions. It is a local app lock, not an operating-system security boundary. Assignments contain instructions, starter code and bounded checks.'),
('Why does macOS say the app is from an unidentified developer?','Sparky uses ad-hoc macOS signing and is not notarized. Verify the download and use the normal macOS controls for opening an app you trust. Release signatures and checksums are documented on the verification page.'),
('How do beta updates work?','Sparky verifies signed manifests and downloads. Small code packs use the existing runtime; a runtime change requires a full app update. The app can roll back a pack that repeatedly fails to start.'),
('What has been tested?','Automated language and native UI checks, frozen Mac update and rollback tests, Python 3.10 compatibility, Linux arm64 and x86_64, and Windows under Wine. Physical Arduino uploads and the Windows installer on a real PC remain unverified.'),
]
body='<p class="eyebrow">A FEW USEFUL ANSWERS</p><h1>Before you press Run.</h1><p class="lede">How Sparky works, where your files live, and what to expect from the app.</p>'+''.join('<details><summary>'+html.escape(q)+'</summary><p>'+html.escape(a)+'</p></details>' for q,a in questions)
(site/'faq.html').write_text(page('FAQ','Answers about Sparky, offline coding, AI privacy, classroom use and supported computers.',body))
print('Generated',len(rows),'reference entries and',len(questions),'FAQ answers.')
