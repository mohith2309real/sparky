# Languages Sparky's editor understands: how to color them, how to indent
# them, and how to run them. Sparky programs run on Sparky's own stage;
# everything else runs as a normal program with its output in the console.

import builtins
import keyword
import os
import shutil
import subprocess
import sys
from pathlib import Path

from ..lang.interpreter import BUILTINS as SPARKY_BUILTINS
from ..lang.parser import HELPER_WORDS, STATEMENT_WORDS

IS_WINDOWS = sys.platform.startswith("win")
FROZEN = getattr(sys, "frozen", False)


class Language:
    def __init__(self, id, name, extensions, comment=None, quotes="\"'",
                 multiline=(), keywords=(), builtins=(), openers=None,
                 closers=(), runner=None):
        self.id = id
        self.name = name
        self.extensions = extensions
        self.comment = comment          # line comment prefix, like "#"
        self.quotes = quotes
        self.multiline = multiline      # (start, end, "string" | "comment")
        self.keywords = set(keywords)
        self.builtins = set(builtins)
        self.openers = openers          # line -> should the next line indent?
        self.closers = closers          # words that end a block (dedent)
        self.runner = runner            # "stage", "python", "node", "browser"


def _sparky_opens(line):
    first = line.strip().split(" ")[0].lower() if line.strip() else ""
    return first in ("repeat", "forever", "if", "teach", "else", "for")


JS_KEYWORDS = """break case catch class const continue debugger default delete do else
export extends false finally for function if import in instanceof let new null of
return static super switch this throw true try typeof undefined var void while with
yield async await""".split()
JS_BUILTINS = """console Math JSON Array Object String Number Boolean Promise Date
RegExp Map Set Symbol Error parseInt parseFloat isNaN setTimeout setInterval
clearTimeout clearInterval require module exports process document window
fetch alert""".split()

LANGUAGES = [
    Language("sparky", "Sparky", [".spark"], comment="#",
             keywords=STATEMENT_WORDS, builtins=list(HELPER_WORDS) + ["mod"] +
             list(SPARKY_BUILTINS), openers=_sparky_opens,
             closers=("end", "else"), runner="stage"),
    Language("python", "Python", [".py", ".pyw"], comment="#",
             multiline=(('"""', '"""', "string"), ("'''", "'''", "string")),
             keywords=keyword.kwlist + ["match", "case", "self"],
             builtins=[n for n in dir(builtins) if n.islower() and not n.startswith("_")],
             openers=lambda line: line.split("#")[0].rstrip().endswith(":"),
             runner="python"),
    Language("javascript", "JavaScript", [".js", ".mjs", ".cjs"], comment="//",
             multiline=(("/*", "*/", "comment"), ("`", "`", "string")),
             keywords=JS_KEYWORDS, builtins=JS_BUILTINS,
             openers=lambda line: line.split("//")[0].rstrip().endswith(("{", "(", "[")),
             runner="node"),
    Language("html", "HTML", [".html", ".htm"],
             multiline=(("<!--", "-->", "comment"),), runner="browser"),
    Language("css", "CSS", [".css"], multiline=(("/*", "*/", "comment"),),
             openers=lambda line: line.rstrip().endswith("{")),
    Language("json", "JSON", [".json"], keywords=["true", "false", "null"],
             openers=lambda line: line.rstrip().endswith(("{", "["))),
    Language("markdown", "Markdown", [".md", ".markdown"], quotes=""),
    Language("text", "Plain text", [".txt"], quotes=""),
]
BY_ID = {lang.id: lang for lang in LANGUAGES}


def language_for(path):
    """Pick a language from a file name (Sparky for new files)."""
    if path is None:
        return BY_ID["sparky"]
    suffix = Path(path).suffix.lower()
    for lang in LANGUAGES:
        if suffix in lang.extensions:
            return lang
    return BY_ID["text"]


def open_dialog_filter():
    code = " ".join("*" + e for lang in LANGUAGES for e in lang.extensions)
    parts = [f"Code files ({code})", "All files (*)"]
    for lang in LANGUAGES:
        parts.append(f"{lang.name} ({' '.join('*' + e for e in lang.extensions)})")
    return ";;".join(parts)


# ---------- finding programs to run code with ----------

def _usable(path):
    return path and Path(path).is_file() and os.access(path, os.X_OK) and \
        "WindowsApps" not in str(path)   # Windows' fake "get Python" stub


def python_candidates():
    """Pythons on this computer, best first."""
    found = []

    def add(cmd):
        if cmd and cmd not in found:
            found.append(cmd)

    for name in ("python3", "python"):
        path = shutil.which(name)
        if _usable(path):
            add([path])
    if IS_WINDOWS and shutil.which("py"):
        add([shutil.which("py"), "-3"])
    for path in ("/opt/homebrew/bin/python3", "/usr/local/bin/python3",
                 "/Library/Frameworks/Python.framework/Versions/Current/bin/python3",
                 "/usr/bin/python3"):
        if _usable(path):
            add([path])
    if not FROZEN:
        exe = Path(sys.executable)
        console = exe.with_name("python.exe")   # pythonw.exe has no console
        add([str(console)] if IS_WINDOWS and console.exists() else [str(exe)])
    return found


def node_candidates():
    found = []
    for path in (shutil.which("node"), "/opt/homebrew/bin/node", "/usr/local/bin/node",
                 r"C:\Program Files\nodejs\node.exe"):
        if _usable(path) and [path] not in found:
            found.append([path])
    return found


def has_turtle(python_cmd):
    """Does this Python have turtle graphics (tkinter)?"""
    try:
        result = subprocess.run(python_cmd + ["-c", "import tkinter"], capture_output=True,
                                timeout=15)
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def run_command(lang, path, settings):
    """The command list that runs `path`, or (None, reason)."""
    if lang.runner == "python":
        chosen = settings.value("python_path", "", type=str)
        cmd = [chosen] if chosen and Path(chosen).exists() else \
            (python_candidates() or [None])[0]
        if not cmd:
            return None, ("I couldn't find Python on this computer. Install it from "
                          "python.org, or pick one in Settings → Languages.")
        return cmd + ["-u", str(path)], None
    if lang.runner == "node":
        chosen = settings.value("node_path", "", type=str)
        cmd = [chosen] if chosen and Path(chosen).exists() else \
            (node_candidates() or [None])[0]
        if not cmd:
            return None, ("Running JavaScript needs Node.js. Install it from "
                          "nodejs.org, or pick it in Settings → Languages.")
        return cmd + [str(path)], None
    custom = custom_commands(settings).get(Path(path).suffix.lower())
    if custom:
        import shlex
        return [part.replace("{file}", str(path)) for part in shlex.split(custom)], None
    return None, (f"Sparky doesn't know how to run {Path(path).suffix or 'this'} files "
                  "yet. Add a run command in Settings → Languages.")


DEFAULT_CUSTOM = """.rb = ruby {file}
.go = go run {file}
.lua = lua {file}
.sh = sh {file}
.php = php {file}"""


def custom_commands(settings):
    text = settings.value("run_commands", DEFAULT_CUSTOM, type=str)
    commands = {}
    for line in text.splitlines():
        if "=" in line:
            ext, cmd = line.split("=", 1)
            ext = ext.strip().lower()
            if not ext.startswith("."):
                ext = "." + ext
            commands[ext] = cmd.strip()
    return commands
