# Kid-friendly errors for Sparky.
# Every error carries a line number and speaks plain English —
# no tracebacks, no jargon, and a "did you mean...?" when we can guess.
# Sparky 3: the most common mistakes also get a "You wrote / Try this" example.

import difflib
import re


class SparkyError(Exception):
    def __init__(self, message, line=None, example=None):
        super().__init__(message)
        self.message = message
        self.line = line
        self.example = example        # (what you wrote, what to try) or None

    def pretty(self):
        where = f"Line {self.line}: " if self.line else ""
        text = f"Oops! {where}{self.message}"
        if self.example:
            wrote, fixed = self.example
            fixed = fixed.replace("\n", "\n              ")
            text += f"\n    You wrote:  {wrote}\n    Try this:   {fixed}"
        return text


def did_you_mean(word, choices):
    """Return a friendly suggestion string like ' Did you mean "move"?' or ''."""
    matches = difflib.get_close_matches(word, list(choices), n=1, cutoff=0.7)
    if matches:
        return f' Did you mean "{matches[0]}"?'
    return ""


def attach_example(err, source):
    """Give an error a "You wrote / Try this" example when we know the fix."""
    if err.example or not err.line or not source:
        return err
    lines = source.splitlines()
    if 0 < err.line <= len(lines):
        fix = suggest(err.message, lines[err.line - 1])
        if fix and fix[0] != fix[1]:
            err.example = fix
    return err


# words from other languages, and what Sparky calls them
OTHER_WORDS = {
    "print": "say", "echo": "say", "display": "say", "puts": "say", "console": "say",
    "def": "teach", "function": "teach", "func": "teach", "define": "teach", "fn": "teach",
    "elif": "else if", "elseif": "else if", "elsif": "else if",
    "input": "ask", "prompt": "ask", "let": "set", "var": "set", "const": "set",
    "sleep": "wait", "forward": "move", "fd": "move", "bk": "back", "rt": "turn right",
    "lt": "turn left", "setx": "goto", "colour": "color", "while": "repeat while",
    "loop": "forever", "break": "stop loop", "exit": "stop program", "quit": "stop program",
}


def suggest(message, line_text):
    """(what you wrote, what to try) for a common mistake, or None."""
    text = line_text.strip()
    if not text:
        return None
    words = text.split()
    first = words[0].lower()
    m = message

    def fix(new):
        return text, new

    # text that never closes: add the missing quote
    if "never closes" in m and "text starts with" in m:
        quote = '"' if text.count('"') % 2 else "'"
        return fix(text + quote)
    # colons from Python: forever:  if x then:  else:
    if text.endswith(":") and ("expected this line to end" in m or ":" in m):
        return fix(text[:-1].rstrip())
    # == and != and && and ||
    if "==" in text:
        return fix(text.replace("==", "="))
    if "!=" in text:
        return fix(text.replace("!=", " is not ").replace("  ", " "))
    if "&&" in text or "||" in text:
        return fix(text.replace("&&", "and").replace("||", "or"))
    # x = 5   x += 1   x++
    m_assign = re.match(r"^([A-Za-z_]\w*)\s*(\+\+|--|\+=|-=|=)\s*(.*)$", text)
    if m_assign and first not in ("set", "change", "for", "if"):
        name, op, rest = m_assign.groups()
        if op == "++":
            return fix(f"change {name} by 1")
        if op == "--":
            return fix(f"change {name} by -1")
        if op == "+=":
            return fix(f"change {name} by {rest}")
        if op == "-=":
            return fix(f"change {name} by -{rest}")
        return fix(f"set {name} to {rest}")
    # set x = 5
    if first == "set" and 'word "to"' in m and "=" in text:
        return fix(re.sub(r"\s*=\s*", " to ", text, count=1))
    # for i = 1 to 10   /   for i in range(10)
    if first == "for" and 'word "from"' in m:
        if "=" in text:
            return fix(re.sub(r"\s*=\s*", " from ", text, count=1))
        rng = re.match(r"for\s+(\w+)\s+in\s+range\((.*)\)", text, re.I)
        if rng:
            parts = [p.strip() for p in rng.group(2).split(",")]
            if len(parts) == 1:
                return fix(f"for {rng.group(1)} from 1 to {parts[0]}")
            return fix(f"for {rng.group(1)} from {parts[0]} to {parts[1]} - 1")
        if " in " in text:
            return fix(text.replace("for ", "for each ", 1))
    # missing then / times / into / by
    if 'word "then"' in m:
        return fix(text + " then")
    if 'word "times"' in m:
        return fix(text + " times")
    if 'word "into"' in m and first == "ask" and len(words) > 2:
        return fix(" ".join(words[:-1]) + " into " + words[-1])
    if 'word "by"' in m and first == "change" and len(words) > 2:
        return fix(" ".join(words[:-1]) + " by " + words[-1])
    # if x > 3 then say "hi"   (all on one line)
    if first == "if" and " then " in text and "expected this line to end" in m:
        head, _, tail = text.partition(" then ")
        return fix(f"{head} then\n  {tail.strip()}\nend")
    # end if / end repeat
    if first == "end" and len(words) > 1:
        return fix("end")
    # turn 90 right
    tr = re.match(r"turn\s+(\S+)\s+(left|right)$", text, re.I)
    if tr:
        return fix(f"turn {tr.group(2).lower()} {tr.group(1)}")
    # goto(10, 20)
    gt = re.match(r"goto\s*\(\s*(.+?)\s*,\s*(.+?)\s*\)$", text, re.I)
    if gt:
        return fix(f"goto {gt.group(1)} {gt.group(2)}")
    # teach square(size)
    tp = re.match(r"teach\s+(\w+)\s*\((.*)\)\s*$", text, re.I)
    if tp:
        params = " ".join(p.strip() for p in tp.group(2).split(",") if p.strip())
        return fix(f"teach {tp.group(1)} {params}".rstrip())
    # say "Score: " score   (a missing +)
    if first in ("say", "think", "write") and "expected this line to end" in m:
        joined = re.sub(r'"\s+(?=[A-Za-z_(])', '" + ', text)
        joined = re.sub(r'(?<=[\w)\]])\s+"', ' + "', joined)
        if joined != text:
            return fix(joined)
    # words from Python, JavaScript and Logo
    if "don't know the command" in m:
        word = re.match(r"[A-Za-z_]+", text)
        if word and word.group(0).lower() in OTHER_WORDS:
            new = OTHER_WORDS[word.group(0).lower()]
            rest = text[len(word.group(0)):]
            if new == "say" and rest.startswith("(") and rest.endswith(")"):
                rest = " " + rest[1:-1]
            return fix(new + rest)
        glued = re.match(r"^([A-Za-z]+)(-?\d+(?:\.\d+)?)(.*)$", text)
        if glued:                                   # move10 -> move 10
            return fix(f"{glued.group(1)} {glued.group(2)}{glued.group(3)}")
    if "colour" in text.lower():
        return fix(re.sub("colour", "color", text, flags=re.I))
    # say hi  ->  say "hi"  (a word that isn't a variable)
    unknown = re.search(r'variable called "([^"]+)"', m)
    if unknown and first in ("say", "think", "write", "speak") and len(words) == 2:
        return fix(f'{first} "{words[1]}"')
    return None
