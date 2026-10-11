# Sparky extensions: drop a .py file in the extensions/ folder and it can
# add new block categories to the palette. Like big-kid editors, but tiny.
#
# An extension looks like this:
#
#     # extensions/my_pack.py
#     NAME = "My Shape Pack"
#     AUTHOR = "you!"
#
#     def register(api):
#         api.add_blocks("MY SHAPES", "accent2", [
#             ("triangle", "repeat 3 times\n  move 80\n  turn 120\nend",
#              "Draws a triangle."),
#         ])
#
# Broken extensions never crash the IDE — they show up in the
# Extensions window with their error instead.

import importlib.util
import json
from pathlib import Path

from ..paths import EXTENSIONS_DIR
from ..lang.parser import RESERVED, STATEMENT_WORDS, NEW_STATEMENT_WORDS, parse
from .projects import atomic_write, read_json, user_root

ACCENTS = ("accent", "accent2", "accent3")


class ExtensionAPI:
    def __init__(self):
        self.block_categories = []  # (category, accent_key, [(label, snippet, tip)])
        self.commands = {}

    def add_command(self, name, params, code, description=''):
        """API v2: define a real command using a bounded-size Sparky body."""
        name = str(name).casefold()
        params = tuple(str(p).casefold() for p in params)
        if (not name.isidentifier() or name in RESERVED or name in STATEMENT_WORDS+NEW_STATEMENT_WORDS
                or name in self.commands or len(params)>12 or len(set(params))!=len(params)
                or any(not p.isidentifier() or p in RESERVED for p in params)):
            raise ValueError('Choose a new command name and distinct valid input names.')
        if not isinstance(code,str) or len(code)>100000:
            raise ValueError('An extension command needs a Sparky body under 100,000 characters.')
        spec = {'params':params, 'code':code, 'description':str(description)}
        self.commands[name] = spec
        try:
            parse(code, self.commands)
        except Exception:
            del self.commands[name]
            raise

    def add_blocks(self, category, accent, blocks):
        if accent not in ACCENTS:
            accent = "accent2"
        clean = []
        for item in blocks:
            label, snippet, tip = (list(item) + ["", "", ""])[:3]
            if label and snippet:
                clean.append((str(label), str(snippet), str(tip)))
        if clean:
            self.block_categories.append((str(category).upper()[:24],
                                          accent, clean))


class LoadedExtension:
    def __init__(self, path, name, author, error=None, blocks_added=0, enabled=True, description='', commands=()):
        self.path = path
        self.name = name
        self.author = author
        self.error = error
        self.blocks_added = blocks_added
        self.enabled, self.description, self.commands = enabled, description, tuple(commands)


class ExtensionManager:
    def __init__(self, folder=None, settings_path=None):
        self.extensions = []
        self.api = ExtensionAPI()
        self.folder = Path(folder) if folder else EXTENSIONS_DIR
        self.settings_path = Path(settings_path) if settings_path else user_root()/'.extensions.json'

    def discover(self):
        self.folder.mkdir(parents=True, exist_ok=True)
        self.extensions = []
        self.api = ExtensionAPI()
        disabled = read_json(self.settings_path,{}).get('disabled',[])
        disabled = disabled if isinstance(disabled,list) else []
        for path in sorted(self.folder.glob("*.py")):
            if path.name.startswith("_"):
                continue
            if path.name in disabled:
                self.extensions.append(LoadedExtension(path,path.stem,'',enabled=False))
            else:
                self.load(path)
        return self.extensions

    def set_enabled(self, path, enabled):
        path = Path(path)
        if path.parent.resolve()!=self.folder.resolve():
            raise ValueError('Choose an extension in the Sparky extensions folder.')
        value = read_json(self.settings_path,{})
        disabled = value.get('disabled',[])
        disabled = set(disabled) if isinstance(disabled,list) else set()
        disabled.discard(path.name) if enabled else disabled.add(path.name)
        atomic_write(self.settings_path,json.dumps({'disabled':sorted(disabled)}))
        self.discover()

    def load(self, path):
        before = len(self.api.block_categories)
        commands_before = dict(self.api.commands)
        try:
            spec = importlib.util.spec_from_file_location(
                f"sparky_extension_{path.stem}", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            register = getattr(module, "register", None)
            if register is None:
                raise ValueError("no register(api) function found")
            register(self.api)
            self.extensions.append(LoadedExtension(
                path,
                getattr(module, "NAME", path.stem),
                getattr(module, "AUTHOR", "unknown"),
                blocks_added=sum(
                    len(blocks) for _, _, blocks
                    in self.api.block_categories[before:]),
                description=str(getattr(module, 'DESCRIPTION', '')),
                commands=set(self.api.commands)-set(commands_before)))
        except Exception as err:  # a bad extension must never kill the IDE
            del self.api.block_categories[before:]
            self.api.commands = commands_before
            self.extensions.append(LoadedExtension(
                path, path.stem, "unknown", error=str(err)))
