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

from ..paths import EXTENSIONS_DIR

ACCENTS = ("accent", "accent2", "accent3")


class ExtensionAPI:
    def __init__(self):
        self.block_categories = []  # (category, accent_key, [(label, snippet, tip)])

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
    def __init__(self, path, name, author, error=None, blocks_added=0):
        self.path = path
        self.name = name
        self.author = author
        self.error = error
        self.blocks_added = blocks_added


class ExtensionManager:
    def __init__(self):
        self.extensions = []
        self.api = ExtensionAPI()

    def discover(self):
        EXTENSIONS_DIR.mkdir(parents=True, exist_ok=True)
        self.extensions = []
        self.api = ExtensionAPI()
        for path in sorted(EXTENSIONS_DIR.glob("*.py")):
            if path.name.startswith("_"):
                continue
            self.load(path)
        return self.extensions

    def load(self, path):
        before = len(self.api.block_categories)
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
                    in self.api.block_categories[before:])))
        except Exception as err:  # a bad extension must never kill the IDE
            del self.api.block_categories[before:]
            self.extensions.append(LoadedExtension(
                path, path.stem, "unknown", error=str(err)))
