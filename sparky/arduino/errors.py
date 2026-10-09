# Arduino compiler errors, explained for kids.
#
# gcc says  Blink.ino:10:3: error: expected ';' before 'delay'
# Sparky says  Line 9 needs a ; at the end.  (with You wrote / Try this)

import difflib
import re
from dataclasses import dataclass

ERROR_RE = re.compile(r"^(?P<file>.+?):(?P<line>\d+):(?:(?P<col>\d+):)?\s*"
                      r"(?P<kind>fatal error|error|warning):\s*(?P<msg>.*)$")

# Arduino words kids type with the wrong capital letters
ARDUINO_WORDS = """setup loop pinMode digitalWrite digitalRead analogWrite analogRead delay
delayMicroseconds millis micros tone noTone Serial HIGH LOW INPUT OUTPUT INPUT_PULLUP
LED_BUILTIN map constrain random randomSeed abs min max pow sqrt sin cos println print
begin available read write attach detach Servo String int float long bool boolean byte char
void unsigned const true false A0 A1 A2 A3 A4 A5 pulseIn shiftOut attachInterrupt""".split()


@dataclass
class Problem:
    line: int           # 1-based line in the sketch (0 = unknown)
    message: str        # friendly
    original: str       # what the compiler said
    wrote: str = ""
    fix: str = ""
    library: str = ""   # a missing library to offer to install

    def pretty(self):
        where = f"Line {self.line}: " if self.line else ""
        text = f"Oops! {where}{self.message}"
        if self.wrote and self.fix and self.wrote != self.fix:
            text += f"\n    You wrote:  {self.wrote}\n    Try this:   {self.fix}"
        return text


def explain(log, sketch_name, source):
    """Friendly problems for one sketch from a compile log (errors in that sketch first)."""
    lines = source.splitlines()
    problems = []
    seen = set()
    for raw in log.splitlines():
        m = ERROR_RE.match(raw.strip())
        if not m or m.group("kind") == "warning":
            continue
        in_sketch = m.group("file").replace("\\", "/").endswith("/" + sketch_name) or \
            m.group("file") == sketch_name
        line = int(m.group("line")) if in_sketch else 0
        msg = m.group("msg").strip()
        key = (line, msg)
        if key in seen:
            continue
        seen.add(key)
        problems.append(friendly(msg, line, lines))
    problems.sort(key=lambda p: (p.line == 0, p.line))
    return problems


def code_at(lines, n):
    return lines[n - 1].rstrip() if 0 < n <= len(lines) else ""


def previous_code_line(lines, n):
    """The line above n that has code on it (skipping blanks and // comments)."""
    k = n - 1
    while k > 0:
        text = lines[k - 1].strip()
        if text and not text.startswith("//"):
            return k
        k -= 1
    return 0


def friendly(msg, line, lines):
    text = code_at(lines, line)
    stripped = text.strip()

    # a missing semicolon is reported on the NEXT line
    m = re.match(r"expected '([;,)])' before", msg)
    if m and m.group(1) == ";":
        prev = previous_code_line(lines, line) or line
        prev_text = code_at(lines, prev).strip()
        if prev_text and not prev_text.endswith((";", "{", "}")):
            return Problem(prev, "This line needs a ; at the end. In Arduino code, every "
                           "command ends with a semicolon.", msg, prev_text, prev_text + ";")
        return Problem(line, "Something is missing a ; here.", msg)
    if re.match(r"expected '\)' before", msg):
        opened = stripped.count("(") - stripped.count(")")
        fix = stripped.rstrip(";") + ")" * max(1, opened) + (";" if stripped.endswith(";") else "")
        return Problem(line, "A ( on this line never got its ).", msg, stripped, fix)
    if "expected '}' at end of input" in msg:
        return Problem(line, "A { never got its }. Add a } at the very end (or where the "
                       "block should stop).", msg)
    if "expected declaration before '}'" in msg or "expected unqualified-id before" in msg:
        return Problem(line, "There's an extra } here, or code outside setup() and loop(). "
                       "Code that does things goes inside a function's { }.", msg)
    if "a function-definition is not allowed here" in msg:
        return Problem(line, "The function above this one is missing its closing }.", msg)

    m = re.match(r"'([^']+)' was not declared in this scope", msg)
    if m:
        name = m.group(1)
        known = set(ARDUINO_WORDS) | set(re.findall(r"\b[A-Za-z_]\w*\b", "\n".join(lines)))
        known.discard(name)
        exact = [w for w in ARDUINO_WORDS if w.lower() == name.lower()]
        if exact:
            fix = re.sub(rf"\b{re.escape(name)}\b", exact[0], stripped)
            return Problem(line, f'Arduino words care about BIG and small letters: it\'s '
                           f'"{exact[0]}", not "{name}".', msg, stripped, fix)
        close = difflib.get_close_matches(name, list(known), n=1, cutoff=0.75)
        if close:
            fix = re.sub(rf"\b{re.escape(name)}\b", close[0], stripped)
            return Problem(line, f'Arduino doesn\'t know "{name}". Did you mean "{close[0]}"?',
                           msg, stripped, fix)
        return Problem(line, f'Arduino doesn\'t know "{name}" yet. Make it at the top of '
                       f"your sketch first, like:  int {name} = 0;", msg)
    m = re.match(r"'([^']+)' does not name a type", msg)
    if m:
        name = m.group(1)
        exact = [w for w in ARDUINO_WORDS if w.lower() == name.lower()]
        if exact:
            return Problem(line, f'It\'s "{exact[0]}" (with those capital letters).', msg,
                           stripped, re.sub(rf"\b{re.escape(name)}\b", exact[0], stripped))
        return Problem(line, f'"{name}" isn\'t a type Arduino knows — check the spelling, or '
                       "maybe this command is outside setup() or loop().", msg)
    m = re.match(r"([\w.]+\.h): No such file or directory", msg)
    if m:
        header = m.group(1)
        return Problem(line, f"Your sketch uses the {header} library, which isn't installed. "
                       "Open Libraries and install it (Sparky can do it for you).", msg,
                       library=header[:-2])
    if msg.startswith("stray '\\") or "stray '" in msg:
        fix = (stripped.replace("“", '"').replace("”", '"').replace("‘", "'")
               .replace("’", "'"))
        return Problem(line, "This line has a curly quote or a strange symbol, probably "
                       "copied from a website. Type the quotes again with your keyboard.",
                       msg, stripped, fix)
    if "missing terminating" in msg:
        return Problem(line, 'This text starts with " but never closes. Add a " at the end '
                       "of the text.", msg, stripped,
                       stripped.rstrip(";") + '"' + (";" if stripped.endswith(";") else ""))
    m = re.match(r"redefinition of '(.+?)'", msg)
    if m:
        return Problem(line, f"{m.group(1)} is written twice. A sketch can only have one — "
                       "delete or rename the second one.", msg)
    if "too few arguments to function" in msg:
        return Problem(line, "This command needs more inputs inside its ( ).", msg)
    if "too many arguments to function" in msg:
        return Problem(line, "This command got too many inputs inside its ( ).", msg)
    if "lvalue required as left operand of assignment" in msg:
        return Problem(line, "To compare two things inside if ( ), use == (two equals signs).",
                       msg, stripped, stripped.replace("=", "==", 1) if "==" not in stripped else stripped)
    if "expected initializer before" in msg:
        prev = previous_code_line(lines, line)
        return Problem(prev or line, "The line above this one is probably missing a ; — or "
                       "a word is misspelled.", msg)
    if "invalid conversion from" in msg or "cannot convert" in msg:
        return Problem(line, "This mixes up two kinds of values (like text and a number).", msg)
    if "else' without a previous 'if'" in msg:
        return Problem(line, "This else has no if before it — check the { } around the if.", msg)
    if "expected primary-expression before" in msg:
        return Problem(line, "Something is missing in this line — maybe a value after = or "
                       "inside ( ).", msg)
    if "has no member named" in msg:
        m = re.search(r"has no member named '(\w+)'", msg)
        name = m.group(1) if m else ""
        exact = [w for w in ARDUINO_WORDS if w.lower() == name.lower()]
        if exact:
            return Problem(line, f'It\'s "{exact[0]}" with those capital letters.', msg,
                           stripped, stripped.replace(name, exact[0]))
        return Problem(line, f'"{name}" isn\'t something this can do. Check the spelling.', msg)
    return Problem(line, msg[:1].upper() + msg[1:], msg)


def explain_upload(log):
    """A friendly sentence for a failed upload, or None."""
    low = log.lower()
    if "no such file or directory" in low and ("port" in low or "/dev/" in low):
        return ("Sparky can't find the board on that port. Plug it in again, press "
                "refresh, and pick its port.")
    if "resource busy" in low or "access is denied" in low or "port busy" in low \
            or "could not open port" in low:
        return ("The port is busy. Close the Serial Monitor (or Arduino IDE), then upload again.")
    if "not in sync" in low or "programmer is not responding" in low:
        return ("The board didn't answer. Check that you picked the right board and port, "
                "then press the board's reset button and try again.")
    if "no upload port provided" in low or "port not set" in low:
        return "Pick the port your board is plugged into first."
    if "permission denied" in low:
        return ("This computer won't let Sparky use that port. On Linux, add yourself to the "
                "dialout group, then log out and in again.")
    if "platform not installed" in low:
        return "This board's package isn't installed yet. Open Boards and install it."
    return None
