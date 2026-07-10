# Sparky language tests — run with: python3 tests/test_lang.py
# No test framework needed, just asserts and a scripted runtime.

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sparky.lang import SparkyError, parse, Interpreter, Runtime  # noqa: E402


class ScriptedRuntime(Runtime):
    """Records everything; answers `ask` from a prepared list."""

    def __init__(self, answers=()):
        self.answers = list(answers)
        self.said = []
        self.lines = []
        self.backgrounds = []
        self.texts = []
        self.stamps = 0
        self.cleared = 0
        self.beeps = 0
        self.sounds = []

    def say(self, text):
        self.said.append(text)

    def ask(self, prompt):
        return self.answers.pop(0) if self.answers else ""

    def line(self, x1, y1, x2, y2, color, width):
        self.lines.append((x1, y1, x2, y2, color, width))

    def background(self, color):
        self.backgrounds.append(color)

    def write_text(self, x, y, text, color, scale):
        self.texts.append(text)

    def stamp(self, x, y, heading, scale):
        self.stamps += 1

    def clear(self):
        self.cleared += 1

    def beep(self):
        self.beeps += 1

    def play_sound(self, name, note, duration):
        self.sounds.append((name, note, duration))


def run(source, answers=(), max_steps=100000):
    rt = ScriptedRuntime(answers)
    interp = Interpreter(parse(source), rt)
    steps = 0
    for _tick in interp.run():
        steps += 1
        if steps >= max_steps:
            break
    return rt, interp


def expect_error(source, fragment):
    try:
        run(source)
    except SparkyError as err:
        message = err.pretty()
        assert fragment.lower() in message.lower(), \
            f"expected {fragment!r} in error, got: {message}"
        return message
    raise AssertionError(f"expected an error mentioning {fragment!r}, "
                         f"but the program ran fine: {source!r}")


passed = 0


def check(name, condition, detail=""):
    global passed
    assert condition, f"FAILED: {name} {detail}"
    passed += 1
    print(f"  ok - {name}")


# ---------- basics ----------

rt, _ = run('say "hello"')
check("say prints", rt.said == ["hello"])

rt, _ = run('set x to 3\nset y to 4\nsay x + y')
check("math + variables", rt.said == ["7"])

rt, _ = run('say 10 / 4')
check("division shows decimals", rt.said == ["2.5"])

rt, _ = run('say 7 mod 3')
check("mod works", rt.said == ["1"])

rt, _ = run('say round 3.7\nsay abs -5')
check("round and abs", rt.said == ["4", "5"])

rt, _ = run('ask "name?" into who\nsay "hi " + who', answers=["Mohith"])
check("ask stores the answer", rt.said == ["hi Mohith"])

rt, _ = run('set n to 0\nchange n by 5\nchange n by -2\nsay n')
check("change by", rt.said == ["3"])

# ---------- control flow ----------

rt, _ = run('set x to 5\nif x > 3 then\n  say "big"\nelse\n  say "small"\nend')
check("if/else true branch", rt.said == ["big"])

rt, _ = run('set x to 1\n'
            'if x = 2 then\n  say "two"\n'
            'else if x = 1 then\n  say "one"\n'
            'else\n  say "other"\nend')
check("else if", rt.said == ["one"])

rt, _ = run('repeat 3 times\n  say "hop"\nend')
check("repeat times", rt.said == ["hop"] * 3)

rt, _ = run('set n to 0\nrepeat until n = 4\n  change n by 1\nend\nsay n')
check("repeat until", rt.said == ["4"])

rt, _ = run('set n to 0\nforever\n  change n by 1\n'
            '  if n = 3 then\n    stop loop\n  end\nend\nsay n')
check("forever + stop loop", rt.said == ["3"])

rt, _ = run('say "a"\nstop program\nsay "b"')
check("stop program halts", rt.said == ["a"])

rt, _ = run('ask "?" into x', answers=["5"])
_rt2, _ = run('ask "?" into x\nif x = 5 then\n  say "match"\nend', answers=["5"])
check("ask answer compares to number", _rt2.said == ["match"])

# ---------- teach / do ----------

rt, _ = run('teach cheer name\n  say "go " + name + "!"\nend\ndo cheer "team"')
check("teach and do with input", rt.said == ["go team!"])

rt, _ = run('teach add a b\n  say a + b\nend\ndo add 2 3')
check("two inputs", rt.said == ["5"])

rt, _ = run('set x to 1\nteach trick x\n  say x\nend\ndo trick 99\nsay x')
check("inputs don't leak out", rt.said == ["99", "1"])

# ---------- logic & text ----------

rt, _ = run('say true and false\nsay true or false\nsay not true')
check("and/or/not", rt.said == ["false", "true", "false"])

rt, _ = run('say "cat" is "cat"\nsay "cat" is not "dog"\nsay 3 >= 3')
check("is / is not / >=", rt.said == ["true", "true", "true"])

rt, _ = run('set r to random 1 to 5\nsay r >= 1 and r <= 5')
check("random in range", rt.said == ["true"])

# ---------- stage ----------

rt, _ = run('speed 10\nmove 100')
check("move draws a line", len(rt.lines) == 1)
x1, y1, x2, y2, color, width = rt.lines[0]
check("move goes up by default", abs(x2 - x1) < 0.001 and abs(y2 - 100) < 0.001,
      f"got {rt.lines[0]}")

rt, _ = run('speed 10\nturn 90\nmove 50')
check("turn right then move goes east", abs(rt.lines[0][2] - 50) < 0.001)

rt, _ = run('speed 10\npen up\nmove 50\npen down\nmove 50')
check("pen up doesn't draw", len(rt.lines) == 1)

rt, _ = run('pen color "red"\nspeed 10\nmove 10')
check("pen color applies", rt.lines[0][4] == "#e5484d")

rt, _ = run('background "ink"\nclear\nstamp\nwrite "hi"\nbeep')
check("stage commands reach runtime",
      rt.backgrounds == ["#141413"] and rt.cleared == 1
      and rt.stamps == 1 and rt.texts == ["hi"] and rt.beeps == 1)

rt, i = run('goto 30 40\nhome')
check("goto and home", (i.x, i.y) == (0.0, 0.0))

rt, i = run('pen up\ngoto 10 -60')
check("negative goto argument", (i.x, i.y) == (10.0, -60.0))

rt, _ = run('say 5 - 3\nsay 5-3\nset x to -4\nsay x')
check("minus still subtracts with spacing", rt.said == ["2", "2", "-4"])

rt, _ = run('teach spot x y\n  pen up\n  goto x y\n  stamp\nend\n'
            'do spot -20 -30\ndo spot 10 20')
check("negative args to do", rt.stamps == 2)

# ---------- sounds ----------

rt, _ = run('play "pop"\nplay "tada"')
check("named sounds reach runtime",
      rt.sounds == [("pop", 0, 0.0), ("tada", 0, 0.0)])

rt, _ = run('play note 4\nplay note 8 for 0.2')
check("notes with and without duration",
      rt.sounds == [("", 4, 0.4), ("", 8, 0.2)])

expect_error('play "pip"', "i can play: pop")
check("unknown sound lists the options", True)

expect_error('play note 40', "notes go from 1")
check("note range is explained", True)

# ---------- friendly errors ----------

msg = expect_error('mvoe 10', "did you mean")
check("typo suggestion", '"move"' in msg.lower(), msg)

expect_error('say 5 / 0', "divide by zero")
check("divide by zero is friendly", True)

expect_error('repeat 3 times\n  say "x"', 'never found its "end"')
check("missing end is caught", True)

expect_error('say "unclosed', "never closes")
check("unclosed string is caught", True)

expect_error('say bananas', "set bananas to 0")
check("unknown variable teaches set", True)

expect_error('do dance', "teach")
check("unknown do teaches teach", True)

expect_error('pen color "redd"', 'did you mean')
check("color typo suggestion", True)

expect_error('teach f a\n  say a\nend\ndo f 1 2', "needs 1 input")
check("wrong input count", True)

msg = expect_error('set x to 5\nsay y', "line 2")
check("errors carry line numbers", True)

# ---------- example programs run clean ----------

examples = Path(__file__).resolve().parent.parent / "examples"
answers_for = {
    "hello.spark": ["sparky"],
    # guessing game: try every number so one of them must be the secret
    "guess_the_number.spark": [str(n) for n in range(1, 21)],
}
for path in sorted(examples.glob("*.spark")):
    source = path.read_text(encoding="utf-8")
    rt, _ = run(source, answers=answers_for.get(path.name, []),
                max_steps=20000)
    check(f"example runs: {path.name}", True)

# ---------- Learn-panel lesson code parses ----------

from sparky.ide.lessons_data import LESSONS  # noqa: E402  (no Qt needed)

for lesson in LESSONS:
    parse(lesson["code"])
    check(f"lesson code parses: {lesson['title']}", True)

print(f"\nAll {passed} checks passed!")
