"""Small local chat histories, separated by project and never storing credentials."""
import hashlib
import json
import shutil
from pathlib import Path
from .projects import atomic_write, read_json


class ChatStore:
    def __init__(self, root):
        self.root=Path(root)/'.chats'

    def path(self, project):
        key=str(Path(project).resolve()) if project else 'scratch-workspace'
        return self.root/(hashlib.sha256(key.encode()).hexdigest()+'.json')

    def load(self, project):
        value=read_json(self.path(project),{})
        messages=value.get('messages',[])
        if not isinstance(messages,list): return []
        return [{'role':m['role'],'content':m['content'],'shown':m.get('shown',m['content'])}
                for m in messages[-40:] if isinstance(m,dict) and m.get('role') in ('user','assistant')
                and isinstance(m.get('content'),str) and isinstance(m.get('shown',m['content']),str)]

    def save(self, project, messages):
        clean=[{'role':m['role'],'content':m['content'][-30000:],
                'shown':m.get('shown',m['content'])[-30000:]}
               for m in messages[-40:] if m.get('role') in ('user','assistant')]
        atomic_write(self.path(project),json.dumps({'messages':clean},ensure_ascii=False))

    def rename_project(self, old, new):
        source = self.path(old)
        if source.exists():
            self.path(new).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, self.path(new))
