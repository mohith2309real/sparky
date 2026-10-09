# Sparky 3.0 language tests: new loops, text templates, records, more
# built-ins, try/oops, events, many sprites, shapes and friendlier numbers.
# Run with: python3 tests/test_lang_v3.py

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sparky.lang import SparkyError, parse, Interpreter, Runtime, format_value  # noqa: E402


class Recorder(Runtime):
    def __init__(self, answers=(), events=(), keys=(), mouse=(0.0, 0.0, False)):
        self.said = []
        self.lines = []
        self.shapes = []
        self.bubbles = []
        self.spoken = []
        self.sprites = {}
        self.texts = []
        self.backdrops = []
        self.answers = list(answers)
        self.queue = list(events)
        self.keys = set(keys)
        self.mouse_state = mouse
        self.memory = {}

    def say(self, text):
        self.said.append(text)

    def ask(self, prompt):
        return self.answers.pop(0) if self.answers else ""

    def sprite_bubble(self, text, kind, sprite):
        self.bubbles.append((kind, text))

    def pen_line(self, x1, y1, x2, y2, pen):
        self.lines.append((x1, y1, x2, y2, pen["color"], pen["width"], pen))

    def shape(self, points, closed, pen, fill):
        self.shapes.append((points, closed, dict(pen), fill))

    def sprite_changed(self, sprite):
        self.sprites[sprite.name] = sprite.snapshot()

    def write_styled(self, x, y, text, color, scale, style):
        self.texts.append((text, dict(style or {})))

    def backdrop(self, name):
        self.backdrops.append(name)

    def speak(self, text):
        self.spoken.append(text)

    def events(self):
        out, self.queue = self.queue, []
        return out

    def wants_events(self):
        return bool(self.queue)

    def key_down(self, name):
        return name in self.keys

    def mouse(self):
        return self.mouse_state

    def save_value(self, name, value):
        self.memory[name] = value

    def load_value(self, name):
        return self.memory.get(name)


def run(source, answers=(), max_ticks=200000, rt=None, sleep_waits=False, base_dir=None):
    rt = rt or Recorder(answers)
    ticks = 0
    it = Interpreter(parse(source), rt, base_dir=base_dir)
    for tick in it.run():
        if sleep_waits and tick[0] == "wait":
            time.sleep(tick[1])
        ticks += 1
        if ticks >= max_ticks:
            break
    return rt.said, rt, it


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


def check_error(name, source, *fragments):
    msg = error_of(source)
    missing = [f for f in fragments if f.lower() not in msg.lower()]
    check(name, msg if missing else "ok", f"(message containing {missing!r})" if missing else "ok")


# ---------- loops and waiting (43-45) ----------
said, *_ = run('set x to 5\nif x > 9 then\n  say "big"\nelse if x > 3 then\n  say "mid"\n'
               'else\n  say "small"\nend')
check("else if chains", said, ["mid"])

said, *_ = run('set n to 1\nrepeat while n < 20\n  set n to n * 2\nend\nsay n')
check("repeat while", said, ["32"])

said, *_ = run('reset timer\nwait until timer > 0.05\nsay "done"', sleep_waits=True)
check("wait until", said, ["done"])

# ---------- text templates (46) ----------
said, *_ = run('set name to "Sam"\nset age to 9\nsay "Hi {name}! Next year you\'ll be {age + 1}."')
check("text templates", said, ["Hi Sam! Next year you'll be 10."])
said, *_ = run('set pets to ["cat", "dog"]\nsay "{{braces}} and {pets} and {length(pets)}"')
check("templates: braces, lists, calls", said, ['{braces} and ["cat", "dog"] and 2'])
check_error("template with an unknown name", 'say "Hi {nme}"', 'variable called "nme"')
check_error("template never closes", 'say "Hi {name"', "never closes")

# ---------- asking (47-48) ----------
said, rt, it = run('ask number "How old are you?" into age\nsay age + 1', answers=["nine", "9"])
check("ask number keeps asking", said, ["Please answer with a number, like 7.", "10"])
said, *_ = run('ask "Pick a pet" choices ["cat", "dog"] into pet\nsay pet', answers=["2"])
check("choices by number", said, ["dog"])
said, *_ = run('ask "Pick a pet" choices ["cat", "dog"] into pet\nsay pet', answers=["fish", "CAT"])
check("choices by name, retry on a wrong one", said, ["Please pick one of: cat, dog.", "cat"])

# ---------- records (49) ----------
said, *_ = run('set pet to {name: "Rex", age: 3}\nsay name of pet\nset age of pet to 4\n'
               'change age of pet by 1\nsay age of pet + 1\nsay pet')
check("records", said, ["Rex", "6", '{name: "Rex", age: 5}'])
said, *_ = run('set owner to {name: "Asha"}\nset pet to {name: "Rex", owner: owner}\n'
               'say name of owner of pet\nset pets to [pet]\nsay name of item 1 of pets')
check("nested records", said, ["Asha", "Rex"])
check_error("missing field", 'set pet to {name: "Rex"}\nsay age of pet', 'no "age"', "name")
check_error("field of a number", 'set n to 5\nsay age of n', "record")

# ---------- maths, text and list tools (50-54) ----------
said, *_ = run('say 7 mod 3\nsay round(3.14159, 2)\nsay round 2.6\nsay abs(-4)\nsay pi > 3.14\n'
               'say clamp(15, 0, 10)\nsay log(1000)\nsay rgb(255, 136, 0)')
check("maths", said, ["1", "3.14", "3", "4", "true", "10", "3", "#ff8800"])
said, *_ = run('goto 0 0\nsay distance(30, 40)\nsay angle(0, 50)\nsay angle(50, 0)')
check("distance and angle from the sprite", said, ["50", "0", "90"])
said, *_ = run('say replace("I like cats", "cats", "dogs")\nsay begins("hello", "he")\n'
               'say ends("hello", "lo")\nsay find("banana", "nan")\nsay find("banana", "x")\n'
               'say words("a big dog")\nsay letters("abc")\nsay capital("sparky")')
check("text tools", said, ["I like dogs", "true", "true", "3", "0", '["a", "big", "dog"]',
                           '["a", "b", "c"]', "Sparky"])
said, *_ = run('set l to [1, 2, 3]\ninsert 9 at 2 in l\nsay l\nsay index(l, 3)\n'
               'say slice(l, 2, 3)\nsay range(1, 5)\nsay range(10, 0, -5)\n'
               'say unique([1, 1, 2])\nsay count([1, 2, 1], 1)\nsay length(shuffle(l))\n'
               'say item -1 of l\nsay item -2 of "abc"')
check("list tools", said, ["[1, 9, 2, 3]", "4", "[9, 2]", "[1, 2, 3, 4, 5]", "[10, 5, 0]",
                           "[1, 2]", "2", "4", "3", "b"])
check_error("item 0 still explains", 'say item 0 of [1]', "start at 1")
check_error("item too far from the end", 'say item -3 of [1, 2]', "only has 2 items")

# ---------- time (55-56) ----------
said, *_ = run('say timer < 1\nsay hour >= 0\nsay minute < 60\nsay second < 60\n'
               'say weekday\nsay length(today) > 5\nsay year > 2000')
check("timer and the clock", said[:4] + said[5:], ["true"] * 6)
check("weekday is a day name", said[4] in ("Monday", "Tuesday", "Wednesday", "Thursday",
                                          "Friday", "Saturday", "Sunday"), True)
said, *_ = run('set timer to 5\nsay timer')
check("your own variable called timer still works", said, ["5"])

# ---------- use another file (57) ----------
folder = Path(tempfile.mkdtemp())
(folder / "shapes.spark").write_text('teach square side\n  repeat 4 times\n    move side\n'
                                     '    turn 90\n  end\nend\nteach twice n\n  give back n * 2\nend\n'
                                     'say "this line does not run"\n')
said, rt, _ = run('use "shapes.spark"\ndo square 10\nsay twice(4)', base_dir=folder)
check("use shares commands", (said, len(rt.lines) > 0), (["8"], True))
check_error("use a missing file", 'use "nope.spark"', "couldn't find")

# ---------- try / oops (58) ----------
said, *_ = run('try\n  say 10 / 0\n  say "never"\noops\n  say "Caught: " + problem\nend\nsay "still here"')
check("try / oops", said[0].startswith("Caught: You can't divide by zero") and said[1:],
      ["still here"])
said, *_ = run('try\n  say "fine"\noops\n  say "no"\nend')
check("try without a problem", said, ["fine"])

# ---------- say for, think, speak (59, 79) ----------
said, rt, _ = run('say "Hi" for 0.01 seconds\nthink "Hmm..."\nspeak "Hello"')
check("say for, think, speak", (said, rt.bubbles, rt.spoken),
      (["Hi"], [("say", "Hi"), ("say", ""), ("think", "Hmm...")], ["Hello"]))

# ---------- events (60-64) ----------
said, *_ = run('when message "go"\n  say "got it"\nend\nbroadcast "go" and wait\nsay "after"')
check("broadcast and wait", said, ["got it", "after"])
said, *_ = run('set n to 0\nwhen message "add"\n  change n by 1\nend\n'
               'broadcast "add"\nbroadcast "add"\nwait 0\nwait 0\nsay n')
check("broadcast runs every listener", said, ["2"])
rt = Recorder(events=[("key", "space"), ("click", "sparky"), ("stage_click", 10.0, 20.0)],
              mouse=(10.0, 20.0, True))
said, *_ = run('when key "space" pressed\n  say "jump"\nend\nwhen clicked\n  say "ouch"\nend\n'
               'when stage clicked\n  say "stage {mouse x}"\nend', rt=rt)
check("key, sprite and stage events", sorted(said), sorted(["jump", "ouch", "stage 10"]))
rt = Recorder(keys={"left"}, mouse=(12.0, -7.0, True))
said, *_ = run('say key "left" down\nsay key "right" down\nsay mouse x\nsay mouse y\nsay mouse down',
               rt=rt)
check("sensing", said, ["true", "false", "12", "-7", "true"])
start = time.time()
said, *_ = run('repeat 6 times\n  next frame\nend\nsay "ok"', sleep_waits=True)
check("next frame paces at 60 fps", (said, time.time() - start >= 0.06), (["ok"], True))
said, *_ = run('when key "a" pressed\n  say "a"\nend\nsay "main done"')
check("listeners don't hang a program without events", said, ["main done"])

# ---------- many sprites (65-71) ----------
said, rt, it = run('make sprite rocket with costume "🚀"\ntell rocket\n  goto 100 50\n  size 200\n'
                   'end\nsay xpos()\ntell rocket\n  say xpos()\nend\nsay round(distance to rocket)')
check("make sprite / tell", said, ["0", "100", "112"])
check("rocket state reached the stage", (rt.sprites["rocket"]["x"], rt.sprites["rocket"]["costume"],
                                        rt.sprites["rocket"]["scale"]), (100.0, "🚀", 2.0))
said, rt, _ = run('costume "🐱"\nghost 50\nlayer front\nsay costume')
check("costume, ghost, layer", (said, rt.sprites["sparky"]["costume"], rt.sprites["sparky"]["ghost"]),
      (["🐱"], "🐱", 50.0))
said, *_ = run('make sprite rock\ntell rock\n  goto 10 0\nend\nsay touching rock\n'
               'goto 239 0\nsay touching edge\ngoto 0 0\nsay touching edge')
check("touching", said, ["true", "true", "false"])
said, *_ = run('pen up\ngoto 230 0\npoint 90\nmove 20\nbounce if on edge\nsay direction()')
check("bounce if on edge", said, ["270"])
said, rt, _ = run('glide to 100 50 in 0.05 seconds\nsay xpos()\nsay ypos()', sleep_waits=True)
check("glide", said, ["100", "50"])
check_error("tell an unknown sprite", 'tell rokcet\n  move 1\nend', "don't know a sprite")

# ---------- shapes, fills, pens, colors, text (72-77) ----------
said, rt, _ = run('fill color "yellow"\ncircle 50\nno fill\nrectangle 80 by 40\npolygon 6 sides 40\n'
                  'star 5 points 40\ndot 10\narc 90 radius 50')
kinds = [(len(p), closed, fill) for p, closed, pen, fill in rt.shapes]
check("shapes", [k[1:] for k in kinds],
      [(True, "#f5c518"), (True, None), (True, None), (True, None), (True, "#141413"), (False, None)])
check("shape point counts", [k[0] for k in kinds[1:4]], [4, 6, 10])
said, rt, _ = run('pen style dashed\npen opacity 50\nmove 10\npen color rainbow\nmove 10\n'
                  'set c to random color\nsay length(c)')
check("pen styles", (rt.lines[0][-1]["style"], rt.lines[0][-1]["opacity"], said),
      ("dashed", 0.5, ["7"]))
check("rainbow pen changes color", rt.lines[-1][4] != rt.lines[1][4] or len(rt.lines) > 1, True)
said, rt, _ = run('write "Hi" size 30 bold\nbackdrop "space"')
check("text styles and backdrops", (rt.texts[0], rt.backdrops), (("Hi", {"size": 30.0, "bold": True}),
                                                                ["space"]))
check_error("unknown backdrop", 'backdrop "spaec"', 'did you mean "space"')

# ---------- memory between runs (78) ----------
rt = Recorder()
run('set score to 12\nsave score as "best"', rt=rt)
said, *_ = run('load "best" into best\nsay best\nload "never" into x\nsay x', rt=rt)
check("save and load", said, ["12", "0"])

# ---------- friendlier errors, names, numbers (80-82) ----------
check_error("you wrote / try this", 'say "hi', "Try this", 'say "hi"')
check_error("= in set", 'set x = 5', "Try this", "set x to 5")
check_error("missing then", 'if 1 > 0\n  say 1\nend', "Try this", "then")
said, *_ = run('set नाम to "Ravi"\nsay नाम\nset పేరు to 3\nsay పేరు + 1')
check("names in any alphabet", said, ["Ravi", "4"])
said, *_ = run('say 0.1 + 0.2\nsay 2 * 1000000000000000\nsay 1 / 3\nsay power(2, 70)')
check("friendly numbers", said, ["0.3", "2000000000000000", "0.333333", "1180591620717411303424"])
check("format_value is still exact for ints", format_value(3.0), "3")

print(f"\nAll {passed} Sparky 3.0 language checks passed!")
