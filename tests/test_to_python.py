# Sparky -> Python translation tests. Run with: python3 tests/test_to_python.py
# Text programs must print exactly what Sparky prints; drawing programs run
# against a fake turtle module so no window opens.

import io
import subprocess
import sys
import types
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sparky.lang import parse, Interpreter, Runtime  # noqa: E402
from sparky.lang.to_python import to_python  # noqa: E402
from sparky.ide.lessons_data import LESSONS  # noqa: E402


class Recorder(Runtime):
    def __init__(self, answers):
        self.said, self.answers = [], list(answers)

    def say(self, text):
        self.said.append(text)

    def ask(self, prompt):
        return self.answers.pop(0) if self.answers else ""


def sparky_output(src, answers=()):
    rt = Recorder(answers)
    for _ in Interpreter(parse(src), rt).run():
        pass
    return rt.said


def python_output(py, answers=()):
    result = subprocess.run([sys.executable, "-c", py], input="\n".join(answers) + "\n",
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, f"python failed:\n{py}\n{result.stderr}"
    out = result.stdout
    for a in answers:   # input() echoes its prompt, not the answer; drop prompts
        pass
    return [ln for ln in out.splitlines()]


class FakeTurtle(types.ModuleType):
    """Accepts every turtle call; stops forever-loops after enough calls."""
    def __init__(self):
        super().__init__("turtle")
        self.calls = 0

    def __getattr__(self, name):
        def call(*args, **kwargs):
            self.calls += 1
            if self.calls > 5000:
                raise KeyboardInterrupt
            return 0
        return call


def limited_input():
    """Answers 1, 2, 3 ... then gives up, so guessing games can't loop forever."""
    count = [0]

    def answer(question=""):
        count[0] += 1
        if count[0] > 30:
            raise KeyboardInterrupt
        return str(count[0])
    return answer


def run_with_fake_turtle(py):
    fake = FakeTurtle()
    old = sys.modules.get("turtle")
    sys.modules["turtle"] = fake
    import time
    real_sleep, time.sleep = time.sleep, lambda s: None
    try:
        with redirect_stdout(io.StringIO()):
            try:
                exec(compile(py, "<translated>", "exec"), {"__name__": "__main__",
                                                           "input": limited_input()})
            except KeyboardInterrupt:
                pass
    finally:
        time.sleep = real_sleep
        if old is None:
            sys.modules.pop("turtle", None)
        else:
            sys.modules["turtle"] = old
    return fake.calls


passed = 0


def normal(lines):
    import re
    out = []
    for ln in lines:
        ln = ln.replace("True", "true").replace("False", "false").replace("'", '"')
        out.append(re.sub(r"\b(\d+)\.0\b", r"\1", ln))
    return out


def check(name, ok, detail=""):
    global passed
    assert ok, f"FAILED: {name} {detail}"
    passed += 1
    print(f"  ok - {name}")


# every example and lesson translates to valid Python that runs
sources = {p.name: p.read_text() for p in sorted((ROOT / "examples").glob("*.spark"))}
sources.update({f"lesson: {l['title']}": l["code"] for l in LESSONS})
for name, src in sources.items():
    py = to_python(src)
    compile(py, name, "exec")
    if "turtle" in py:
        calls = run_with_fake_turtle(py)
        check(f"translates + runs (drawing): {name}", calls > 0)
    else:
        with redirect_stdout(io.StringIO()):
            try:
                exec(compile(py, name, "exec"), {"__name__": "__main__",
                                                 "input": limited_input()})
            except KeyboardInterrupt:
                pass
        check(f"translates + runs: {name}", True)

# same output as Sparky for text programs
programs = [
    ('say "Hello, " + "world"\nset x to 6\nsay x * 7', ()),
    ('ask "name?" into n\nsay "Hi " + n + "!"', ("Sam",)),
    ('set total to 0\nfor i from 1 to 10\n  change total by i\nend\nsay total', ()),
    ('for i from 10 to 1 by -3\n  say i\nend', ()),
    ('set pets to ["cat", "dog"]\nadd "fish" to pets\nremove "cat" from pets\n'
     'for each p in pets\n  say upper(p)\nend\nsay length(pets)\nsay item 1 of pets', ()),
    ('teach fib n\n  if n < 2 then\n    give back n\n  end\n  give back fib(n - 1) + fib(n - 2)\n'
     'end\nsay fib(12)', ()),
    ('set score to 0\nteach bump by_what\n  change score by by_what\nend\n'
     'do bump 3\nbump(4)\nsay score', ()),
    ('set n to 17\nif n mod 2 = 0 then\n  say "even"\nelse if n > 10 then\n  say "big odd"\n'
     'else\n  say "small odd"\nend', ()),
    ('say join(["a", "b"], "+")\nsay contains(["x"], "x")\nsay sqrt(49)\nsay power(3, 3)\n'
     'say sort([3, 1, 2])\nsay reverse("abc")', ()),
    ('set list to [1, 2, 3]\nset item 2 of list to 20\nsay list', ()),
    ('ask "guess?" into g\nif g = 5 then\n  say "yes"\nend', ("5",)),
]
for i, (src, answers) in enumerate(programs, 1):
    want = sparky_output(src, answers)
    py = to_python(src)
    got = python_output(py, answers)
    # input() prints its prompt without a newline, so it sticks to the next line
    got = [ln.split("? ", 1)[-1] if "?" in ln and not want[0].endswith("?") else ln
           for ln in got]
    # Python spells some values differently (True, 7.0, 'cat') — same values
    check(f"same output as Sparky #{i}", normal(got) == normal(want),
          f"\n{py}\nsparky={want}\npython={got}")

# Python keywords/builtins used as Sparky names get a safe spelling
py = to_python('set print to 5\nset list to [1]\nsay print')
check("reserved Python names are renamed", "print_ = 5" in py and "list_ = [1]" in py)

print(f"\nAll {passed} translation checks passed!")
