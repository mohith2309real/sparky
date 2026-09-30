# Sparky 1.1 tests: lists, for loops, functions that give back results,
# built-in functions. Run with: python3 tests/test_lang_v11.py

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sparky.lang import SparkyError, parse, Interpreter, Runtime  # noqa: E402


class Recorder(Runtime):
    def __init__(self, answers=()):
        self.said = []
        self.lines = []
        self.answers = list(answers)

    def say(self, text):
        self.said.append(text)

    def ask(self, prompt):
        return self.answers.pop(0) if self.answers else ""

    def line(self, *args):
        self.lines.append(args)


def run(source, answers=(), max_ticks=200000):
    rt = Recorder(answers)
    ticks = 0
    for _ in Interpreter(parse(source), rt).run():
        ticks += 1
        if ticks >= max_ticks:
            break
    return rt.said, rt, ticks


passed = 0


def check(name, got, want):
    global passed
    assert got == want, f"FAILED: {name}\n  got:  {got!r}\n  want: {want!r}"
    passed += 1
    print(f"  ok - {name}")


def error_of(source):
    try:
        run(source)
    except SparkyError as err:
        return err.pretty()
    raise AssertionError(f"expected an error from: {source!r}")


def check_error(name, source, fragment):
    msg = error_of(source)
    check(name, fragment.lower() in msg.lower(), True) if fragment.lower() in msg.lower() \
        else check(name, msg, f"(message containing {fragment!r})")


# ---------- lists ----------
said, *_ = run('set pets to ["cat", "dog"]\nsay pets\nsay length(pets)')
check("list literal and length", said, ['["cat", "dog"]', "2"])

said, *_ = run('set pets to ["cat", "dog"]\nadd "fish" to pets\nsay item 3 of pets\n'
               'remove "cat" from pets\nsay pets')
check("add / item / remove", said, ["fish", '["dog", "fish"]'])

said, *_ = run('set nums to [5, 6, 7]\nset item 2 of nums to 60\nsay nums\nsay item 1 of "hello"')
check("set item + item of text", said, ["[5, 60, 7]", "h"])

said, *_ = run('set empty to []\nif empty then\n  say "full"\nelse\n  say "empty"\nend')
check("empty list is false", said, ["empty"])

said, *_ = run('set a to [1, 2]\nset b to a + [3]\nsay b\nsay [1, 2] = [1, 2]')
check("list join and compare", said, ["[1, 2, 3]", "true"])

# ---------- for loops ----------
said, *_ = run('set total to 0\nfor i from 1 to 5\n  change total by i\nend\nsay total')
check("for from to", said, ["15"])

said, *_ = run('for i from 10 to 1 by -3\n  say i\nend')
check("for counting down by", said, ["10", "7", "4", "1"])

said, *_ = run('for each pet in ["cat", "dog"]\n  say "I love my " + pet\nend')
check("for each", said, ["I love my cat", "I love my dog"])

said, *_ = run('for each letter in "hi"\n  say upper(letter)\nend')
check("for each letter in text", said, ["H", "I"])

said, *_ = run('for i from 1 to 100\n  if i = 3 then\n    stop loop\n  end\n  say i\nend')
check("stop loop inside for", said, ["1", "2"])

# ---------- functions with results ----------
said, *_ = run('teach double n\n  give back n * 2\nend\nsay double(21)\nsay double(double(5))')
check("give back + nested calls", said, ["42", "20"])

said, *_ = run('teach fib n\n  if n < 2 then\n    give back n\n  end\n'
               '  give back fib(n - 1) + fib(n - 2)\nend\nsay fib(15)')
check("recursion (fibonacci)", said, ["610"])

said, *_ = run('teach fact n\n  if n <= 1 then\n    return 1\n  end\n'
               '  set smaller to fact(n - 1)\n  return n * smaller\nend\nsay fact(10)')
check("return keyword + locals across recursion", said, ["3628800"])

said, *_ = run('set score to 0\nteach bump\n  change score by 5\n  set temp to 1\nend\n'
               'do bump\nbump()\nsay score')
check("globals update, calls as statements", said, ["10"])
check_error("locals stay inside", 'teach f\n  set secret to 1\nend\ndo f\nsay secret',
            'variable called "secret"')

said, *_ = run('teach quiet\n  set x to 1\nend\nsay quiet()')
check("no give back = nothing", said, ["nothing"])

said, *_ = run('teach greet name\n  say "hi " + name\nend\ngreet("Sam")')
check("bare call statement", said, ["hi Sam"])

_, rt, _ = run('teach square s\n  repeat 4 times\n    move s\n    turn 90\n  end\n  give back s * 4\nend\n'
               'speed 10\nsay square(50)')
check("drawing inside a function called in an expression", len(rt.lines), 4)

_, _, ticks = run('teach spin\n  forever\n    turn 1\n  end\nend\nsay spin()', max_ticks=300)
check("a forever inside a call still yields ticks (Stop works)", ticks, 300)

# ---------- built-ins ----------
said, *_ = run('say upper("hi") + lower("YO")\nsay sqrt(81)\nsay power(2, 10)\n'
               'say min(4, 2, 8)\nsay max([3, 9, 1])\nsay sum([1, 2, 3])\nsay round(sin(90))')
check("text + math built-ins", said, ["HIyo", "9", "1024", "2", "9", "6", "1"])

said, *_ = run('say join(["a", "b", "c"], "-")\nsay split("a b c")\nsay split("1,2", ",")\n'
               'say contains(["x", "y"], "y")\nsay contains("hello", "ell")\n'
               'say sort([3, 1, 2])\nsay reverse("abc")\nsay number("4") + 1\nsay text(5) + "!"')
check("list + conversion built-ins", said,
      ["a-b-c", '["a", "b", "c"]', '["1", "2"]', "true", "true", "[1, 2, 3]", "cba", "5", "5!"])

said, *_ = run('set p to pick(["only"])\nsay p\nsay floor(3.7) + ceil(3.2)')
check("pick, floor, ceil", said, ["only", "7"])

said, *_ = run('pen up\ngoto 30 -40\nsay xpos()\nsay ypos()\npoint 90\nsay direction()')
check("sprite position functions", said, ["30", "-40", "90"])

said, *_ = run('set n to 5\nadd 3 to n\nset t to "ab"\nadd "c" to t\nsay n\nsay t')
check("add to a number / text", said, ["8", "abc"])

# ---------- friendly errors ----------
check_error("item past the end", 'set l to [1, 2, 3]\nsay item 5 of l', "only has 3 items")
check_error("items start at 1", 'say item 0 of [1]', "start at 1")
check_error("remove missing", 'set l to [1]\nremove 2 from l', "couldn't find 2")
check_error("unknown function suggests", 'say lenght("hi")', 'did you mean "length"')
check_error("wrong input count", 'say sqrt(1, 2)', "needs 1 input")
check_error("give back outside teach", 'give back 5', "only works inside")
check_error("endless recursion is friendly",
            'teach f n\n  give back f(n + 1)\nend\nsay f(1)', "dizzy")
check_error("list + number explains add", 'say [1] + 2', "add ITEM to LIST")
check_error("unclosed list", 'set l to [1, 2', "never closes")

print(f"\nAll {passed} Sparky 1.1 checks passed!")
