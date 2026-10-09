# Sparky -> Python: turns a Sparky program into real, readable Python.
#
# Drawing becomes Python's own `turtle` module in "logo" mode, where 0 points
# up and turns go clockwise — the same as Sparky's stage — so a program looks
# the same in both. Only the helpers a program actually uses are included.

import builtins
import keyword

from . import ast_nodes as A
from .interpreter import COLORS
from .parser import parse

PRECEDENCE = {"or": 1, "and": 2, "not": 3, "=": 4, "!=": 4, ">": 4, "<": 4,
              ">=": 4, "<=": 4, "+": 5, "-": 5, "*": 6, "/": 6, "mod": 6}
PY_OPS = {"=": "==", "mod": "%"}
TAKEN = set(keyword.kwlist) | set(dir(builtins)) | {
    "turtle", "random", "math", "time", "ask", "number", "COLORS", "t"}

HELPERS = {
    "ask": '''def ask(question):
    """input() that turns number answers into numbers, like Sparky does."""
    answer = input(question + " ")
    try:
        number = float(answer)
    except ValueError:
        return answer
    return int(number) if number.is_integer() else number''',
    "number": '''def number(value):
    """Turn text like "42" into the number 42."""
    value = float(value)
    return int(value) if value.is_integer() else value''',
    "COLORS": "COLORS = " + repr(COLORS),
    "ask_number": '''def ask_number(question):
    """Keep asking until the answer is a number."""
    while True:
        answer = input(question + " ")
        try:
            number = float(answer)
            return int(number) if number.is_integer() else number
        except ValueError:
            print("Please answer with a number, like 7.")''',
    "ask_choice": '''def ask_choice(question, choices):
    """Show numbered choices and keep asking until one is picked."""
    print(question)
    for i, choice in enumerate(choices, 1):
        print(f"  {i}. {choice}")
    while True:
        answer = input("Your choice: ").strip()
        for choice in choices:
            if str(choice).lower() == answer.lower():
                return choice
        if answer.isdigit() and 1 <= int(answer) <= len(choices):
            return choices[int(answer) - 1]
        print("Please pick one of:", ", ".join(str(c) for c in choices))''',
    "memory": '''import json


def save_value(name, value):
    """Keep a value in sparky_memory.json for next time."""
    try:
        with open("sparky_memory.json") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    data[name] = value
    with open("sparky_memory.json", "w") as f:
        json.dump(data, f)


def load_value(name):
    try:
        with open("sparky_memory.json") as f:
            return json.load(f).get(name, 0)
    except (OSError, ValueError):
        return 0''',
    "shape": '''def draw_shape(points, closed=True, fill=None):
    """Draw a shape around the turtle, like Sparky's circle / star / polygon."""
    x, y = turtle.position()
    h = math.radians(turtle.heading())
    c, s = math.cos(h), math.sin(h)
    spots = [(x + dx * c + dy * s, y - dx * s + dy * c) for dx, dy in points]
    was_down = turtle.isdown()
    turtle.penup()
    turtle.goto(spots[0])
    turtle.pendown()
    if fill:
        turtle.fillcolor(fill)
        turtle.begin_fill()
    for spot in spots[1:] + (spots[:1] if closed else []):
        turtle.goto(spot)
    if fill:
        turtle.end_fill()
    turtle.penup()
    turtle.goto(x, y)
    if was_down:
        turtle.pendown()''',
}

# values Sparky knows by itself, and how Python finds them
SENSORS = {
    "pi": ("math", "math.pi"),
    "timer": ("time", "(time.monotonic() - timer_start)"),
    "hour": ("time", "time.localtime().tm_hour"),
    "minute": ("time", "time.localtime().tm_min"),
    "second": ("time", "time.localtime().tm_sec"),
    "day": ("time", "time.localtime().tm_mday"),
    "month": ("time", "time.localtime().tm_mon"),
    "year": ("time", "time.localtime().tm_year"),
    "weekday": ("time", 'time.strftime("%A")'),
    "today": ("time", 'time.strftime("%d %B %Y").lstrip("0")'),
}

NOT_YET = {
    "When": "when blocks", "Broadcast": "broadcast", "KeyDown": 'key "..." down',
    "Mouse": "the mouse", "MakeSprite": "more sprites", "Tell": "tell",
    "Costume": "costumes", "Ghost": "ghost", "Layer": "layer", "Touching": "touching",
    "DistanceTo": "distance to", "NextFrame": "next frame",
}


class Translator:
    def __init__(self):
        self.imports = set()
        self.helpers = []
        self.uses_turtle = False
        self.global_names = set()   # set at the top level of the program
        self.list_names = set()     # variables that start life as a list
        self.in_function = False
        self.assigned = set()
        self.uses_timer = False
        self.uses_fill = False

    # ---------- names & helpers ----------

    def name(self, sparky_name):
        return sparky_name + "_" if sparky_name in TAKEN else sparky_name

    def need(self, helper):
        if helper not in self.helpers:
            self.helpers.append(helper)

    def turtle(self, call):
        self.uses_turtle = True
        return f"turtle.{call}"

    # ---------- expressions ----------

    def expr(self, node, parent_prec=0):
        text, prec = self.expr_prec(node)
        return f"({text})" if prec < parent_prec else text

    def expr_prec(self, node):
        if isinstance(node, A.Num):
            v = node.value
            return (str(int(v)) if float(v).is_integer() else repr(v)), 9
        if isinstance(node, A.Str):
            return repr(node.value), 9
        if isinstance(node, A.Bool):
            return ("True" if node.value else "False"), 9
        if isinstance(node, A.Nothing):
            return "None", 9
        if isinstance(node, A.Var):
            if node.name in SENSORS and node.name not in self.assigned:
                module, text = SENSORS[node.name]
                self.imports.add(module)
                if node.name == "timer":
                    self.uses_timer = True
                return text, 9
            return self.name(node.name), 9
        if isinstance(node, A.Template):
            out = []
            for part in node.parts:
                if isinstance(part, str):
                    out.append(part.replace("{", "{{").replace("}", "}}")
                               .replace("\\", "\\\\").replace('"', '\\"'))
                else:
                    out.append("{" + self.expr(part) + "}")
            return 'f"' + "".join(out) + '"', 9
        if isinstance(node, A.RecordLit):
            return "{" + ", ".join(f"{k!r}: {self.expr(v)}" for k, v in node.pairs) + "}", 9
        if isinstance(node, A.Field):
            if node.name == "length":
                return f"len({self.expr(node.target)})", 9
            return f"{self.expr(node.target, 9)}[{node.name!r}]", 9
        if isinstance(node, A.RandomColor):
            self.imports.add("random")
            return 'f"#{random.randrange(0x1000000):06x}"', 9
        if isinstance(node, A.ListLit):
            return "[" + ", ".join(self.expr(i) for i in node.items) + "]", 9
        if isinstance(node, A.Index):
            return f"{self.expr(node.target, 9)}[{self.index(node.index)}]", 9
        if isinstance(node, A.Random):
            self.imports.add("random")
            return f"random.randint({self.expr(node.low)}, {self.expr(node.high)})", 9
        if isinstance(node, A.UnOp):
            if node.op == "-":
                return f"-{self.expr(node.operand, 8)}", 8
            if node.op == "not":
                return f"not {self.expr(node.operand, 3)}", 3
            return f"{node.op}({self.expr(node.operand)})", 9
        if isinstance(node, A.Call):
            return self.call(node), 9
        if isinstance(node, A.BinOp):
            if node.op == "+" and self.is_text_join(node):
                return self.fstring(node), 9
            prec = PRECEDENCE[node.op]
            op = PY_OPS.get(node.op, node.op)
            left = self.expr(node.left, prec)
            right = self.expr(node.right, prec + 1)
            return f"{left} {op} {right}", prec
        raise self.not_yet(node)

    def not_yet(self, node):
        from .errors import SparkyError
        what = NOT_YET.get(type(node).__name__, type(node).__name__)
        return SparkyError(f"Show as Python can't translate {what} yet. Everything else "
                           "in Sparky 3 works — try it on a program without them.",
                           getattr(node, "line", None))

    def index(self, node):
        if isinstance(node, A.Num) and float(node.value).is_integer():
            return str(int(node.value) - 1)
        return f"int({self.expr(node)}) - 1"

    def plus_parts(self, node):
        if isinstance(node, A.BinOp) and node.op == "+":
            return self.plus_parts(node.left) + self.plus_parts(node.right)
        return [node]

    def is_text_join(self, node):
        return any(isinstance(p, A.Str) for p in self.plus_parts(node))

    def fstring(self, node):
        out = []
        for part in self.plus_parts(node):
            if isinstance(part, A.Str):
                out.append(part.value.replace("{", "{{").replace("}", "}}")
                           .replace("\\", "\\\\").replace('"', '\\"'))
            else:
                out.append("{" + self.expr(part) + "}")
        return 'f"' + "".join(out) + '"'

    def call(self, node):
        a = [self.expr(arg) for arg in node.args]
        n = node.name
        simple = {"length": "len", "min": "min", "max": "max", "sum": "sum",
                  "text": "str", "sort": "sorted"}
        if n in simple:
            return f"{simple[n]}({', '.join(a)})"
        if n in ("upper", "lower"):
            return f"str({a[0]}).{n}()"
        if n == "trim":
            return f"str({a[0]}).strip()"
        if n in ("sqrt", "floor", "ceil"):
            self.imports.add("math")
            return f"math.{n}({a[0]})"
        if n == "power":
            return f"{self.expr(node.args[0], 8)} ** {self.expr(node.args[1], 8)}"
        if n in ("sin", "cos", "tan"):
            self.imports.add("math")
            return f"math.{n}(math.radians({a[0]}))"
        if n == "join":
            sep = a[1] if len(a) > 1 else '""'
            return f"{sep}.join(str(item) for item in {a[0]})"
        if n == "split":
            return f"{a[0]}.split({a[1]})" if len(a) > 1 else f"{a[0]}.split()"
        if n == "contains":
            return f"{self.expr(node.args[1], 4)} in {self.expr(node.args[0], 4)}"
        if n == "pick":
            self.imports.add("random")
            return f"random.choice({a[0]})"
        if n == "reverse":
            return f"{self.expr(node.args[0], 9)}[::-1]"
        if n == "number":
            self.need("number")
            return f"number({a[0]})"
        if n == "round":
            return f"round({', '.join(a)})"
        if n == "abs":
            return f"abs({a[0]})"
        if n == "capital":
            return f"{self.expr(node.args[0], 9)}[:1].upper() + {self.expr(node.args[0], 9)}[1:]"
        if n in ("log", "ln"):
            self.imports.add("math")
            return f"math.{'log10' if n == 'log' else 'log'}({a[0]})"
        if n == "clamp":
            return f"max({a[1]}, min({a[2]}, {a[0]}))"
        if n == "rgb":
            return f'"#%02x%02x%02x" % (int({a[0]}), int({a[1]}), int({a[2]}))'
        if n == "replace":
            return f"{self.expr(node.args[0], 9)}.replace({a[1]}, {a[2]})"
        if n == "begins":
            return f"{self.expr(node.args[0], 9)}.startswith({a[1]})"
        if n == "ends":
            return f"{self.expr(node.args[0], 9)}.endswith({a[1]})"
        if n == "find":
            return f"{self.expr(node.args[0], 9)}.find({a[1]}) + 1"
        if n == "words":
            return f"{self.expr(node.args[0], 9)}.split()"
        if n == "letters":
            return f"list({a[0]})"
        if n == "index":
            return f"({self.expr(node.args[0], 9)}.index({a[1]}) + 1)"
        if n == "slice":
            end = a[2] if len(a) > 2 else ""
            return f"{self.expr(node.args[0], 9)}[{a[1]} - 1:{end}]"
        if n == "range":
            step = f", {a[2]}" if len(a) > 2 else ""
            return f"list(range({a[0]}, {a[1]} + 1{step}))"
        if n == "shuffle":
            self.imports.add("random")
            return f"random.sample({a[0]}, len({a[0]}))"
        if n == "unique":
            return f"list(dict.fromkeys({a[0]}))"
        if n == "count":
            return f"{self.expr(node.args[0], 9)}.count({a[1]})"
        if n == "keys":
            return f"list({a[0]})"
        if n in ("distance", "angle") and len(a) == 2:
            return self.turtle(f"{'distance' if n == 'distance' else 'towards'}({a[0]}, {a[1]})")
        if n == "distance":
            self.imports.add("math")
            return f"math.dist(({a[0]}, {a[1]}), ({a[2]}, {a[3]}))"
        if n in ("xpos", "ypos", "direction"):
            return self.turtle({"xpos": "xcor()", "ypos": "ycor()",
                                "direction": "heading()"}[n])
        return f"{self.name(n)}({', '.join(a)})"

    def color(self, node):
        if isinstance(node, A.Str):
            name = node.value.strip().lower()
            return repr(COLORS.get(name, node.value))
        self.need("COLORS")
        value = self.expr(node)
        return f"COLORS.get({value}, {value})"

    # ---------- statements ----------

    def block(self, body, depth):
        lines = []
        for stmt in body:
            lines.extend(self.stmt(stmt, depth))
        return lines or ["    " * depth + "pass"]

    def stmt(self, s, d):
        pad = "    " * d
        e = self.expr
        if isinstance(s, A.Say):
            out = [f"{pad}print({e(s.value)})"]
            if s.duration is not None:
                self.imports.add("time")
                out.append(f"{pad}time.sleep({e(s.duration)})")
            return out
        if isinstance(s, A.Think):
            return [f'{pad}print("💭", {e(s.value)})']
        if isinstance(s, A.Speak):
            return [f'{pad}print("🔊", {e(s.value)})  # Python has no built-in voice']
        if isinstance(s, A.Ask):
            target = self.name(s.target)
            if s.choices is not None:
                self.need("ask_choice")
                return [f"{pad}{target} = ask_choice({e(s.prompt)}, {e(s.choices)})"]
            if s.mode == "number":
                self.need("ask_number")
                return [f"{pad}{target} = ask_number({e(s.prompt)})"]
            self.need("ask")
            return [f"{pad}{target} = ask({e(s.prompt)})"]
        if isinstance(s, A.SetField):
            return [f"{pad}{e(s.target, 9)}[{s.name!r}] = {e(s.value)}"]
        if isinstance(s, A.ChangeField):
            return [f"{pad}{e(s.target, 9)}[{s.name!r}] += {e(s.amount)}"]
        if isinstance(s, A.RepeatWhile):
            return [f"{pad}while {e(s.condition)}:"] + self.block(s.body, d + 1)
        if isinstance(s, A.WaitUntil):
            self.imports.add("time")
            return [f"{pad}while not ({e(s.condition)}):", f"{pad}    time.sleep(1 / 60)"]
        if isinstance(s, A.InsertAt):
            return [f"{pad}{self.name(s.name)}.insert({self.index(s.index)}, {e(s.value)})"]
        if isinstance(s, A.ResetTimer):
            self.imports.add("time")
            self.uses_timer = True
            return [f"{pad}timer_start = time.monotonic()"]
        if isinstance(s, A.Use):
            module = s.path.value.rsplit("/", 1)[-1].replace(".spark", "") \
                if isinstance(s.path, A.Str) else "other_file"
            return [f"{pad}from {module} import *  # translate {module}.spark too"]
        if isinstance(s, A.Try):
            out = [f"{pad}try:"] + self.block(s.body, d + 1)
            out += [f"{pad}except Exception as error:", f"{pad}    problem = str(error)"]
            return out + (self.block(s.oops_body, d + 1) if s.oops_body else [])
        if isinstance(s, A.Save):
            self.need("memory")
            return [f"{pad}save_value({e(s.name)}, {e(s.value)})"]
        if isinstance(s, A.Load):
            self.need("memory")
            return [f"{pad}{self.name(s.target)} = load_value({e(s.name)})"]
        if isinstance(s, A.SetVar):
            return [f"{pad}{self.name(s.name)} = {e(s.value)}"]
        if isinstance(s, A.ChangeVar):
            return [f"{pad}{self.name(s.name)} += {e(s.amount)}"]
        if isinstance(s, A.RepeatTimes):
            count = e(s.count)
            if not (isinstance(s.count, A.Num) and float(s.count.value).is_integer()):
                count = f"int({count})"
            return [f"{pad}for _ in range({count}):"] + self.block(s.body, d + 1)
        if isinstance(s, A.RepeatUntil):
            return [f"{pad}while not ({e(s.condition)}):"] + self.block(s.body, d + 1)
        if isinstance(s, A.Forever):
            return [f"{pad}while True:"] + self.block(s.body, d + 1)
        if isinstance(s, A.ForEach):
            return [f"{pad}for {self.name(s.name)} in {e(s.iterable)}:"] + \
                self.block(s.body, d + 1)
        if isinstance(s, A.ForRange):
            return [f"{pad}for {self.name(s.name)} in {self.range(s)}:"] + \
                self.block(s.body, d + 1)
        if isinstance(s, A.If):
            out = []
            for i, (cond, body) in enumerate(s.branches):
                out.append(f"{pad}{'if' if i == 0 else 'elif'} {e(cond)}:")
                out += self.block(body, d + 1)
            if s.else_body is not None:
                out.append(f"{pad}else:")
                out += self.block(s.else_body, d + 1)
            return out
        if isinstance(s, A.Wait):
            self.imports.add("time")
            return [f"{pad}time.sleep({e(s.seconds)})"]
        if isinstance(s, A.StopLoop):
            return [f"{pad}break"]
        if isinstance(s, A.StopProgram):
            return [f"{pad}raise SystemExit"]
        if isinstance(s, A.Teach):
            return self.function(s, d)
        if isinstance(s, A.Do):
            return [f"{pad}{self.name(s.name)}({', '.join(e(a) for a in s.args)})"]
        if isinstance(s, A.ExprStatement):
            return [f"{pad}{e(s.expr)}"]
        if isinstance(s, A.Return):
            return [f"{pad}return {e(s.value)}"]
        if isinstance(s, A.AddTo):
            # Sparky's add works on lists, numbers and text; lists are the
            # common case, and += covers numbers and text in Python
            if s.name in self.list_names:
                return [f"{pad}{self.name(s.name)}.append({e(s.value)})"]
            return [f"{pad}{self.name(s.name)} += {e(s.value)}"]
        if isinstance(s, A.RemoveFrom):
            return [f"{pad}{self.name(s.name)}.remove({e(s.value)})"]
        if isinstance(s, A.SetItem):
            return [f"{pad}{self.name(s.name)}[{self.index(s.index)}] = {e(s.value)}"]
        return self.drawing(s, pad)

    def range(self, s):
        e = self.expr
        a, b = const_int(s.start), const_int(s.stop)
        step = const_int(s.step) if s.step is not None else None
        if a is not None and b is not None and (s.step is None or step is not None):
            if step is None:
                step = 1 if a <= b else -1
            end = b + (1 if step > 0 else -1)
            return f"range({a}, {end})" if step == 1 else f"range({a}, {end}, {step})"
        start, stop = f"int({e(s.start)})", f"int({e(s.stop)})"
        if s.step is None:
            return (f"range({start}, {stop} + 1) if {start} <= {stop} "
                    f"else range({start}, {stop} - 1, -1)")
        step_text = f"int({e(s.step)})"
        return (f"range({start}, {stop} + (1 if {step_text} > 0 else -1), "
                f"{step_text})")

    def function(self, s, d):
        pad = "    " * d
        params = ", ".join(self.name(p) for p in s.params)
        out = ([""] if d == 0 else []) + [f"{pad}def {self.name(s.name)}({params}):"]
        assigned = sorted({x.name for x in walk(s.body)
                           if isinstance(x, (A.SetVar, A.ChangeVar))} &
                          (self.global_names - set(s.params)))
        if assigned:
            out.append(f"{pad}    global {', '.join(self.name(n) for n in assigned)}")
        was = self.in_function
        self.in_function = True
        out += self.block(s.body, d + 1)
        self.in_function = was
        return out + [""]

    def drawing(self, s, pad):
        e, t = self.expr, self.turtle
        if isinstance(s, A.Move):
            if isinstance(s.distance, A.UnOp) and s.distance.op == "-":
                return [f"{pad}{t(f'backward({e(s.distance.operand)})')}"]
            return [f"{pad}{t(f'forward({e(s.distance)})')}"]
        if isinstance(s, A.Turn):
            way = "right" if s.direction > 0 else "left"
            return [f"{pad}{t(f'{way}({e(s.degrees)})')}"]
        if isinstance(s, A.Point):
            return [f"{pad}{t(f'setheading({e(s.heading)})')}"]
        if isinstance(s, A.Goto):
            return [f"{pad}{t(f'goto({e(s.x)}, {e(s.y)})')}"]
        if isinstance(s, A.Home):
            return [f"{pad}{t('home()')}"]
        if isinstance(s, A.Pen):
            call = {"up": "penup()", "down": "pendown()"}.get(s.mode)
            if call:
                return [f"{pad}{t(call)}"]
            if s.mode in ("style", "opacity"):
                return [f"{pad}# pen {s.mode}: Python's turtle can't do this one"]
            if s.mode == "color" and isinstance(s.value, A.Str) and s.value.value == "rainbow":
                coral = t('pencolor("#d97757")')
                return [f"{pad}{coral}  # Python's turtle has no rainbow pen"]
            if s.mode == "color":
                return [f"{pad}{t(f'pencolor({self.color(s.value)})')}"]
            return [f"{pad}{t(f'pensize({e(s.value)})')}"]
        if isinstance(s, A.Clear):
            return [f"{pad}{t('clear()')}"]
        if isinstance(s, A.Glide):
            self.imports.add("time")
            secs = e(s.seconds)
            return [f"{pad}start_x, start_y = {t('position()')}",
                    f"{pad}for step in range(1, 31):",
                    f"{pad}    {t(f'goto(start_x + ({e(s.x)} - start_x) * step / 30, start_y + ({e(s.y)} - start_y) * step / 30)')}",
                    f"{pad}    time.sleep({secs} / 30)"]
        if isinstance(s, A.Bounce):
            return [f"{pad}if abs({t('xcor()')}) > 222:",
                    f"{pad}    {t('setheading(360 - turtle.heading())')}",
                    f"{pad}if abs({t('ycor()')}) > 162:",
                    f"{pad}    {t('setheading(180 - turtle.heading())')}"]
        if isinstance(s, A.Fill):
            self.uses_fill = True
            return [f"{pad}fill_color = {self.color(s.value) if s.value is not None else 'None'}"]
        if isinstance(s, A.Shape):
            self.need("shape")
            self.imports.add("math")
            self.uses_turtle = True
            return [f"{pad}{self.shape_call(s)}"]
        if isinstance(s, A.Backdrop):
            colors = {"space": "#141a40", "night": "#1a2850", "ocean": "#4fa9d8",
                      "grass": "#bfe3ff", "sunset": "#e86f6f", "grid": "#fbfaf6", "none": "white"}
            name = s.value.value.lower() if isinstance(s.value, A.Str) else ""
            if name in colors:
                return [f"{pad}{t(f'bgcolor({colors[name]!r})')}  # the {name} backdrop's color"]
            return [f"{pad}{t(f'bgpic({e(s.value)})')}"]
        if isinstance(s, A.HideShow):
            return [f"{pad}{t('showturtle()' if s.visible else 'hideturtle()')}"]
        if isinstance(s, A.Stamp):
            return [f"{pad}{t('stamp()')}"]
        if isinstance(s, A.Background):
            return [f"{pad}{t(f'bgcolor({self.color(s.color)})')}"]
        if isinstance(s, A.Speed):
            if isinstance(s.value, A.Num):
                v = int(s.value.value)
                return [f"{pad}{t(f'speed({0 if v >= 10 else max(1, v)})')}"]
            v = e(s.value)
            return [f"{pad}{t(f'speed(0 if {v} >= 10 else {v})')}"]
        if isinstance(s, A.WriteText):
            size = e(s.style["size"]) if "size" in s.style else "13"
            weight = " ".join(w for w in ("bold", "italic") if s.style.get(w)) or "normal"
            call = "write(" + e(s.value) + f', font=("Arial", int({size}), "{weight}"))'
            return [f"{pad}{t(call)}"]
        if isinstance(s, A.SpriteSize):
            return [f"{pad}{t(f'shapesize({self.expr(s.percent, 6)} / 100)')}"]
        if isinstance(s, A.Beep):
            return [f'{pad}print("\\a", end="")  # beep']
        if isinstance(s, A.PlaySound):
            if s.kind == "note":
                self.imports.add("time")
                secs = e(s.duration) if s.duration is not None else "0.4"
                return [f'{pad}print("♪ note", {e(s.value)})  # Python has no built-in sound',
                        f"{pad}time.sleep({secs})"]
            return [f'{pad}print("♪", {e(s.value)})  # Python has no built-in sound']
        raise self.not_yet(s)

    def shape_call(self, s):
        e = self.expr
        fill = "fill_color" if self.uses_fill else "None"
        a = [e(x) for x in s.args]
        if s.kind == "circle":
            pts = f"[({a[0]} * math.sin(i * math.pi / 36), {a[0]} * math.cos(i * math.pi / 36)) for i in range(72)]"
            return f"draw_shape({pts}, True, {fill})"
        if s.kind == "dot":
            return self.turtle(f"dot({a[0]})")
        if s.kind == "rectangle":
            return (f"draw_shape([(-{a[0]} / 2, {a[1]} / 2), ({a[0]} / 2, {a[1]} / 2), "
                    f"({a[0]} / 2, -{a[1]} / 2), (-{a[0]} / 2, -{a[1]} / 2)], True, {fill})")
        if s.kind == "polygon":
            pts = (f"[({a[1]} * math.sin(2 * math.pi * i / {a[0]}), "
                   f"{a[1]} * math.cos(2 * math.pi * i / {a[0]})) for i in range(int({a[0]}))]")
            return f"draw_shape({pts}, True, {fill})"
        if s.kind == "star":
            pts = (f"[({a[1]} * (1 if i % 2 == 0 else 0.45) * math.sin(math.pi * i / {a[0]}), "
                   f"{a[1]} * (1 if i % 2 == 0 else 0.45) * math.cos(math.pi * i / {a[0]})) "
                   f"for i in range(2 * int({a[0]}))]")
            return f"draw_shape({pts}, True, {fill})"
        pts = (f"[({a[1]} * math.sin(math.radians({a[0]} * i / 18)), "
               f"{a[1]} * math.cos(math.radians({a[0]} * i / 18))) for i in range(19)]")
        return f"draw_shape({pts}, False)"

    # ---------- whole program ----------

    def program(self, body):
        top = list(walk(body, top_only=True))
        self.global_names = {x.name for x in top
                             if isinstance(x, (A.SetVar, A.ForEach, A.ForRange))}
        self.global_names |= {x.target for x in top if isinstance(x, A.Ask)}
        self.list_names = {x.name for x in walk(body)
                           if isinstance(x, A.SetVar) and isinstance(x.value, A.ListLit)}
        self.assigned = {x.name for x in walk(body) if isinstance(x, (A.SetVar, A.ForEach,
                                                                       A.ForRange))}
        self.assigned |= {x.target for x in walk(body) if isinstance(x, (A.Ask, A.Load))}
        self.uses_fill = any(isinstance(x, A.Fill) for x in walk(body))
        lines = self.block(body, 0)
        head = ["# Translated from Sparky into Python.",
                "# Run it with:  python3 this_file.py", ""]
        imports = sorted(self.imports | ({"turtle"} if self.uses_turtle else set()))
        head += [f"import {m}" for m in imports]
        if imports:
            head.append("")
        if self.uses_turtle:
            head += ['turtle.mode("logo")   # 0 points up and turns go clockwise, like Sparky',
                     'turtle.shape("turtle")', "turtle.speed(6)", ""]
        if self.uses_timer:
            head += ["timer_start = time.monotonic()", ""]
        if self.uses_fill:
            head += ["fill_color = None", ""]
        for h in self.helpers:
            head += [HELPERS[h], ""]
        body_lines = list(lines)
        while body_lines and body_lines[-1] == "":
            body_lines.pop()
        tail = ["", "turtle.done()   # keep the drawing window open"] if self.uses_turtle else []
        return "\n".join(head + body_lines + tail) + "\n"


def const_int(node):
    """The whole number a node stands for, or None (handles -3 too)."""
    if isinstance(node, A.Num) and float(node.value).is_integer():
        return int(node.value)
    if isinstance(node, A.UnOp) and node.op == "-":
        inner = const_int(node.operand)
        return -inner if inner is not None else None
    return None


def walk(body, top_only=False):
    """Every statement in a block (and nested blocks unless top_only)."""
    for s in body:
        yield s
        if top_only and isinstance(s, A.Teach):
            continue
        for attr in ("body", "else_body", "oops_body"):
            inner = getattr(s, attr, None)
            if isinstance(inner, list):
                yield from walk(inner, top_only)
        if isinstance(s, A.If):
            for _, b in s.branches:
                yield from walk(b, top_only)


def to_python(source):
    """Translate Sparky source code into Python source code."""
    return Translator().program(parse(source))
