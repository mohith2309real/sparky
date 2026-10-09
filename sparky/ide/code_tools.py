# The editor's brains (Sparky 3), with no Qt in here so they're easy to test:
# block structure (matching end, folding, breadcrumbs, auto end), the outline,
# re-indenting, go to definition, rename, and spotting colors and numbers.

import re

from ..lang.interpreter import COLORS

OPENERS = ("repeat", "forever", "if", "teach", "for", "try", "when", "tell")
MIDDLES = ("else", "oops")
WORD = re.compile(r"[^\W\d]\w*", re.UNICODE)
NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
HEX = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})")


def first_word(line):
    m = WORD.match(line.strip())
    return m.group(0).lower() if m else ""


def code_part(line, comment="#"):
    """The line without its comment (comments can't hide inside quotes here)."""
    out, quote = [], None
    for ch in line:
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == comment[0] and line[len(out):].startswith(comment):
            break
        out.append(ch)
    return "".join(out)


# ---------- Sparky block structure ----------

class Block:
    def __init__(self, start, kind, title):
        self.start = start          # 1-based line of the opener
        self.end = None             # 1-based line of its `end` (None if missing)
        self.kind = kind
        self.title = title
        self.middles = []           # else / oops lines
        self.depth = 0
        self.indent = 0

    def __repr__(self):
        return f"Block({self.kind} {self.start}-{self.end})"


def structure(lines):
    """Every block in a Sparky program, by matching openers with `end`."""
    blocks, stack = [], []
    for n, raw in enumerate(lines, 1):
        word = first_word(code_part(raw))
        indent = len(raw) - len(raw.lstrip())
        if word in ("end",) + MIDDLES:
            # an end lined up with an outer block closes that one: the inner
            # blocks above it are still open (indentation shows what's meant)
            while len(stack) > 1 and stack[-1].indent > indent:
                stack.pop()
        if word in OPENERS:
            block = Block(n, word, " ".join(code_part(raw).split()))
            block.depth = len(stack)
            block.indent = indent
            blocks.append(block)
            stack.append(block)
        elif word in MIDDLES and stack:
            stack[-1].middles.append(n)
        elif word == "end" and stack:
            stack.pop().end = n
    return blocks


def matching_line(lines, n):
    """The line that belongs with line n: an opener's end, an end's opener."""
    for block in structure(lines):
        if block.start == n:
            return block.end
        if block.end == n or n in block.middles:
            return block.start
    return None


def foldable(lines):
    """{opener line: end line} for blocks with something inside to hide."""
    return {b.start: b.end for b in structure(lines) if b.end and b.end - b.start > 1}


def breadcrumbs(lines, n):
    """The blocks around line n, outermost first: ["teach star size", "repeat 5 times"]."""
    out = []
    for block in structure(lines):
        if block.start <= n and (block.end is None or n <= block.end):
            title = block.title
            if title.endswith(" then"):
                title = title[:-5]
            out.append(title if len(title) <= 32 else title[:30] + "…")
    return out


def needs_end(lines, n):
    """After pressing Enter on line n: should Sparky add the `end` for you?"""
    word = first_word(code_part(lines[n - 1]))
    if word not in OPENERS:
        return False
    for block in structure(lines):
        if block.start == n:
            return block.end is None
    return False


# ---------- outline ----------

PY_DEF = re.compile(r"^\s*(def|class)\s+(\w+)")
C_FUNC = re.compile(r"^\s*(?:[\w:<>,*&]+\s+)+\**(\w+)\s*\([^;]*\)\s*(?:const\s*)?\{?\s*$")
JS_FUNC = re.compile(r"^\s*(?:async\s+)?function\s+(\w+)|^\s*(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(")


def outline(lines, lang_id="sparky"):
    """[(line, kind, name)] — commands, events, sprites and functions to jump to."""
    out = []
    if lang_id == "sparky":
        seen = set()
        for n, raw in enumerate(lines, 1):
            text = " ".join(code_part(raw).split())
            word = first_word(text)
            if word == "teach":
                parts = text.split()
                if len(parts) > 1:
                    out.append((n, "command", parts[1] + (" " + " ".join(parts[2:]) if len(parts) > 2 else "")))
            elif word == "when":
                out.append((n, "event", text))
            elif text.startswith("make sprite "):
                out.append((n, "sprite", text.split()[2] if len(text.split()) > 2 else "?"))
            elif word == "set" and raw == raw.lstrip():
                name = text.split()[1] if len(text.split()) > 1 else ""
                if name and name not in seen and name not in ("item",):
                    seen.add(name)
                    out.append((n, "variable", name))
    elif lang_id == "python":
        for n, raw in enumerate(lines, 1):
            m = PY_DEF.match(raw)
            if m:
                indent = len(raw) - len(raw.lstrip())
                out.append((n, "class" if m.group(1) == "class" else "function",
                            "  " * (indent // 4) + m.group(2)))
    elif lang_id in ("arduino", "c", "cpp"):
        for n, raw in enumerate(lines, 1):
            m = C_FUNC.match(raw)
            if m and m.group(1) not in ("if", "for", "while", "switch", "return", "else"):
                out.append((n, "function", m.group(1)))
    elif lang_id == "javascript":
        for n, raw in enumerate(lines, 1):
            m = JS_FUNC.match(raw)
            if m:
                out.append((n, "function", m.group(1) or m.group(2)))
    return out


# ---------- re-indent ----------

def reindent(text, lang_id="sparky", unit="  "):
    """Fix the indentation: Sparky by its blocks, C-like languages by their braces."""
    lines = text.split("\n")
    out = []
    depth = 0
    if lang_id == "sparky":
        for raw in lines:
            stripped = raw.strip()
            word = first_word(code_part(stripped))
            if not stripped:
                out.append("")
                continue
            if word in ("end",) + MIDDLES:
                depth = max(0, depth - 1)
            out.append(unit * depth + stripped)
            if word in OPENERS or word in MIDDLES:
                depth += 1
        return "\n".join(out)
    if lang_id in ("arduino", "c", "cpp", "javascript", "css", "json"):
        in_block_comment = False
        for raw in lines:
            stripped = raw.strip()
            if not stripped:
                out.append("")
                continue
            if in_block_comment:
                out.append(unit * depth + " " + stripped if stripped.startswith("*") else unit * depth + stripped)
                if "*/" in stripped:
                    in_block_comment = False
                continue
            code = _strip_c_strings(stripped)
            leading_close = len(code) - len(code.lstrip("}])"))
            out.append(unit * max(0, depth - leading_close) + stripped)
            depth = max(0, depth + code.count("{") + code.count("[") + code.count("(")
                        - code.count("}") - code.count("]") - code.count(")"))
            if "/*" in code and "*/" not in code[code.index("/*"):]:
                in_block_comment = True
        return "\n".join(out)
    return text


def _strip_c_strings(line):
    """Code without strings, chars and // comments (so braces in them don't count)."""
    out, i, n = [], 0, len(line)
    while i < n:
        ch = line[i]
        if line.startswith("//", i):
            break
        if ch in "\"'":
            j = i + 1
            while j < n and line[j] != ch:
                j += 2 if line[j] == "\\" else 1
            i = j + 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


# ---------- definitions and rename ----------

def definition_line(lines, word, lang_id="sparky"):
    """Where a name is made: `teach NAME`, the first `set NAME to`, `def NAME`..."""
    word_l = word.lower()
    if lang_id == "sparky":
        patterns = [rf"^\s*teach\s+{re.escape(word_l)}\b", rf"^\s*make\s+sprite\s+{re.escape(word_l)}\b",
                    rf"^\s*set\s+{re.escape(word_l)}\s+to\b", rf"\binto\s+{re.escape(word_l)}\s*$",
                    rf"^\s*for\s+(each\s+)?{re.escape(word_l)}\b"]
        for pattern in patterns:
            for n, raw in enumerate(lines, 1):
                if re.search(pattern, code_part(raw).lower()):
                    return n
        for n, raw in enumerate(lines, 1):           # an input of a taught command
            text = code_part(raw).lower().split()
            if text[:1] == ["teach"] and word_l in text[2:]:
                return n
        return None
    if lang_id == "python":
        for n, raw in enumerate(lines, 1):
            if re.match(rf"^\s*(def|class)\s+{re.escape(word)}\b", raw) or \
                    re.match(rf"^\s*{re.escape(word)}\s*=", raw):
                return n
        return None
    for n, raw in enumerate(lines, 1):
        if re.match(rf"^\s*(?:[\w:<>,*&]+\s+)+\**{re.escape(word)}\s*[(=;\[]", raw):
            return n
    return None


def rename(text, old, new, comment="#"):
    """Rename a word everywhere it's code: not inside text or comments — except
    the {names} inside Sparky's text templates, which are code too."""
    old_l = old.lower()
    out, i, n = [], 0, len(text)

    def swap(chunk):
        return re.sub(rf"(?<![\w]){re.escape(old)}(?![\w])", new, chunk, flags=re.IGNORECASE) \
            if old_l == old else re.sub(rf"(?<![\w]){re.escape(old)}(?![\w])", new, chunk)

    code_start = 0
    while i < n:
        ch = text[i]
        if text.startswith(comment, i):
            out.append(swap(text[code_start:i]))
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(text[i:j])
            i = code_start = j
            continue
        if ch in "\"'":
            out.append(swap(text[code_start:i]))
            j = i + 1
            while j < n and text[j] != ch and text[j] != "\n":
                j += 1
            literal = text[i:j + 1]
            out.append(re.sub(r"\{([^{}]*)\}", lambda m: "{" + swap(m.group(1)) + "}", literal))
            i = code_start = j + 1
            continue
        i += 1
    out.append(swap(text[code_start:]))
    return "".join(out)


# ---------- colors and numbers ----------

def colors_in_line(line):
    """[(start, end, "#rrggbb")] for color names and hex colors in quotes."""
    out = []
    for m in re.finditer(r"\"([^\"\n]*)\"|'([^'\n]*)'", line):
        value = (m.group(1) if m.group(1) is not None else m.group(2)).strip()
        low = value.lower()
        if low in COLORS:
            out.append((m.start() + 1, m.end() - 1, COLORS[low]))
        elif HEX.fullmatch(value):
            if len(value) == 4:
                value = "#" + "".join(c * 2 for c in value[1:])
            out.append((m.start() + 1, m.end() - 1, value.lower()))
    return out


def number_at(line, col):
    """(start, end, value) for the number under column col, or None."""
    for m in NUMBER.finditer(line):
        if m.start() <= col <= m.end():
            if m.start() > 0 and (line[m.start() - 1].isalnum() or line[m.start() - 1] == "_"):
                continue
            before = line[:m.start()]
            if before.count('"') % 2 == 1:      # inside text
                return None
            return m.start(), m.end(), float(m.group(0))
    return None


def format_number(value, like):
    """Keep the style of the number being changed (whole numbers stay whole)."""
    if "." in like:
        places = len(like.split(".")[1])
        return f"{value:.{places}f}"
    return str(int(round(value)))
