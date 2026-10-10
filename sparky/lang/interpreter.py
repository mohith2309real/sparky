# Sparky interpreter: walks the AST and makes things happen.
#
# It runs as a GENERATOR — after (almost) every statement it yields a small
# tick tuple. Whoever drives the generator (the IDE or the console runner)
# uses those ticks to animate the stage, pace the program, and stop it.
#
# Tick shapes:
#   ("step", line)          — a logic statement ran
#   ("visual", line)        — something on the stage changed
#   ("wait", seconds, line) — the program asked to pause (line may be None)
#
# Expressions are generators too (`yield from self.eval(node)`), so a
# command you taught can be called inside an expression — `say double(21)`
# — and still animate, pause and stop like everything else.
#
# Sparky 3: `when` blocks and `broadcast` run several scripts side by side.
# Each script is a Thread (a generator with its own local variables and its
# own current sprite); the scheduler takes turns between them. A program
# without events runs exactly like before: one thread, waits passed straight
# to the driver.

import colorsys
import datetime
import math
import random
import sys
import time
from pathlib import Path

from . import ast_nodes as A
from .errors import SparkyError, attach_example, did_you_mean

COLORS = {
    "red": "#e5484d", "orange": "#d97757", "yellow": "#f5c518",
    "green": "#788c5d", "blue": "#6a9bcc", "purple": "#8e7cc3",
    "pink": "#e58fb1", "brown": "#8d6748", "black": "#141413",
    "white": "#faf9f5", "gray": "#b0aea5", "grey": "#b0aea5",
    "cyan": "#4cc2c4", "magenta": "#c65ca8", "lime": "#9fbf3b",
    "navy": "#2d4a6b", "cream": "#faf9f5", "ink": "#141413",
    "gold": "#e0a526", "teal": "#2f8f83", "sky": "#9cc9e8", "coral": "#d97757",
}

# costumes: a name kids can type, and the emoji drawn on the stage
COSTUMES = {
    "cat": "🐱", "dog": "🐶", "fox": "🦊", "panda": "🐼", "frog": "🐸", "monkey": "🐵",
    "lion": "🦁", "tiger": "🐯", "unicorn": "🦄", "dragon": "🐉", "dino": "🦖",
    "octopus": "🐙", "fish": "🐟", "shark": "🦈", "turtle": "🐢", "bee": "🐝",
    "butterfly": "🦋", "bird": "🐦", "penguin": "🐧", "owl": "🦉", "ghost": "👻",
    "robot": "🤖", "alien": "👽", "rocket": "🚀", "ufo": "🛸", "car": "🚗",
    "bus": "🚌", "plane": "✈️", "ball": "⚽", "basketball": "🏀", "star": "⭐",
    "heart": "❤️", "sun": "☀️", "moon": "🌙", "cloud": "☁️", "tree": "🌳",
    "flower": "🌸", "apple": "🍎", "pizza": "🍕", "cake": "🎂",
}
COSTUME_ORDER = list(COSTUMES.values())

BACKDROPS = ("space", "ocean", "grass", "sunset", "night", "grid", "none")
IMAGE_TYPES = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")

STAGE_HALF_W = 240.0     # the stage is 480 x 360, origin in the middle
STAGE_HALF_H = 180.0
SPRITE_RADIUS = 18.0     # how big a sprite is for touching and bouncing
FRAME = 1 / 60

MAX_CALL_DEPTH = 150

# built-in sound effects for `play "name"`
SOUND_NAMES = ("pop", "ding", "boing", "laser", "drum", "tada", "jump")

KEY_NAMES = ("space", "left", "right", "up", "down", "enter", "any")

_MISSING = object()

BOARD_ONLY = ('"{what}" works on an Arduino board, not on the stage. Plug in your board, '
              'open the Arduino panel and press Upload.')


class BreakLoop(Exception):
    pass


class HaltProgram(Exception):
    pass


class ReturnValue(Exception):
    def __init__(self, value):
        super().__init__()
        self.value = value


def format_value(value, quoted=False):
    """How Sparky shows values to kids: 3.0 prints as 3, True as true,
    0.1 + 0.2 as 0.3, and big whole numbers in full."""
    if value is None:
        return "nothing"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value != value:
            return "not a number"
        if value in (math.inf, -math.inf):
            return "infinity" if value > 0 else "-infinity"
        if value.is_integer() and abs(value) < 1e16:
            return str(int(value))
        if abs(value) >= 1e16:
            return f"{value:.15g}"
        if abs(value) >= 1e-4:
            return str(round(value, 6))
        return f"{value:.6g}"
    if isinstance(value, list):
        return "[" + ", ".join(format_value(v, quoted=True) for v in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{k}: {format_value(v, quoted=True)}"
                               for k, v in value.items()) + "}"
    if quoted and isinstance(value, str):
        return f'"{value}"'
    return str(value)


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def hex_color(r, g, b):
    return "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, int(round(c)))) for c in (r, g, b)))


class Sprite:
    """One thing on the stage. Sparky himself is the sprite called "sparky"."""

    def __init__(self, name, costume=None, pen_down=True):
        self.name = name
        self.x = 0.0
        self.y = 0.0
        self.heading = 0.0
        self.pen_down = pen_down
        self.pen_color = "#141413"
        self.pen_size = 3.0
        self.pen_style = "solid"
        self.pen_opacity = 1.0
        self.rainbow = False
        self.hue = 0.0
        self.fill = None
        self.visible = True
        self.scale = 1.0
        self.costume = costume      # None = the Sparky mascot
        self.ghost = 0.0
        self.layer = 0

    @property
    def radius(self):
        return SPRITE_RADIUS * self.scale

    def snapshot(self):
        return {"name": self.name, "x": self.x, "y": self.y, "heading": self.heading,
                "visible": self.visible, "scale": self.scale, "costume": self.costume,
                "ghost": self.ghost, "layer": self.layer}

    def pen(self):
        return {"color": self.pen_color, "width": self.pen_size,
                "style": self.pen_style, "opacity": self.pen_opacity}


class Thread:
    """One script running: the main program, or a `when` block."""

    def __init__(self, gen, sprite, handler=None):
        self.gen = gen
        self.sprite = sprite
        self.handler = handler
        self.frames = []
        self.calls = []           # (command name, line it was called from) — the call stack
        self.wake = 0.0
        self.done = False


def _sprite_attr(name):
    return property(lambda self: getattr(self.sprite, name),
                    lambda self, value: setattr(self.sprite, name, value))


class Interpreter:
    def __init__(self, program, runtime, base_dir=None, source=None):
        self.program = program
        self.runtime = runtime
        self.base_dir = Path(base_dir) if base_dir else None
        self.source = source
        self.globals = {}
        self.frames = []          # local scopes for commands you taught
        self.functions = {}
        self.handlers = []        # (When node, event value)
        self.speed = 5            # 1 (slow) .. 10 (instant)
        self.main_sprite = Sprite("sparky")
        self.sprites = {"sparky": self.main_sprite}
        self.sprite = self.main_sprite     # the sprite the running script controls
        self.threads = []
        self.current = None
        self.timer_start = time.monotonic()
        self.last_frame = None
        self.used_files = set()
        self.top_layer = 0
        self.calls = []                    # the running thread's call stack
        self.break_lines = frozenset()     # breakpoints: pause before these lines

    # Sparky 2 code (and the IDE) read these straight off the interpreter;
    # they belong to whichever sprite is being told what to do.
    x = _sprite_attr("x")
    y = _sprite_attr("y")
    heading = _sprite_attr("heading")
    pen_down = _sprite_attr("pen_down")
    pen_color = _sprite_attr("pen_color")
    pen_size = _sprite_attr("pen_size")
    visible = _sprite_attr("visible")
    scale = _sprite_attr("scale")

    # ---------- for the debugger ----------

    def snapshot(self):
        """Variables, the call stack and sprites, copied for the Debug panel.
        Called from the window while the program runs, so it copies carefully."""
        for _ in range(3):
            try:
                frames = [dict(f) for f in self.frames]
                return {"globals": dict(self.globals),
                        "locals": frames[-1] if frames else {},
                        "calls": list(self.calls),
                        "sprites": {n: s.snapshot() for n, s in list(self.sprites.items())},
                        "threads": sum(1 for t in self.threads if not t.done)}
            except RuntimeError:          # changed size while copying: try again
                continue
        return None

    def watch(self, text):
        """Evaluate a watch expression (like x * 2) without running any commands."""
        from .parser import Parser
        parser = Parser(text)
        node = parser.parse_expression()
        if self.has_call(node):
            raise SparkyError("Watches can't call your commands (they might change things).", None)
        return self.eval_now(node)

    def has_call(self, node):
        if isinstance(node, A.Call) and node.name in self.functions:
            return True
        for value in vars(node).values():
            if isinstance(value, A.Node) and self.has_call(value):
                return True
            if isinstance(value, list) and any(isinstance(v, A.Node) and self.has_call(v) for v in value):
                return True
        return False

    # ---------- variables ----------

    def get_var(self, name, line):
        if self.frames and name in self.frames[-1]:
            return self.frames[-1][name]
        if name in self.globals:
            return self.globals[name]
        sensed = self.sense(name)
        if sensed is not _MISSING:
            return sensed
        known = list(self.globals) + (list(self.frames[-1]) if self.frames else [])
        hint = did_you_mean(name, known + list(self.functions))
        raise SparkyError(f'I don\'t know a variable called "{name}".{hint} '
                          f'You can make it with: set {name} to 0', line)

    def set_var(self, name, value):
        # Inside a command you taught, new variables belong to that command,
        # but an existing program-wide variable (like a score) is updated.
        if self.frames:
            frame = self.frames[-1]
            if name in frame or name not in self.globals:
                frame[name] = value
                return
        self.globals[name] = value

    def sense(self, name):
        """Values Sparky knows without being told: timer, the clock, pi..."""
        if name == "timer":
            return round(time.monotonic() - self.timer_start, 3)
        if name == "pi":
            return math.pi
        if name in ("hour", "minute", "second", "day", "month", "year", "today", "weekday"):
            now = datetime.datetime.now()
            if name == "today":
                return f"{now.day} {now.strftime('%B')} {now.year}"
            if name == "weekday":
                return now.strftime("%A")
            return float(getattr(now, name))
        if name == "costume":
            return self.sprite.costume or "sparky"
        if name == "size":
            return self.sprite.scale * 100.0
        return _MISSING

    # ---------- expressions ----------

    def eval(self, node):
        """Evaluate an expression. A generator: use `yield from self.eval(n)`."""
        if isinstance(node, (A.Num, A.Str, A.Bool)):
            return node.value
            yield  # pragma: no cover (makes this a generator)
        if isinstance(node, A.Nothing):
            return None
        if isinstance(node, A.Var):
            return self.get_var(node.name, node.line)
        if isinstance(node, A.Template):
            out = []
            for part in node.parts:
                out.append(part if isinstance(part, str)
                           else format_value((yield from self.eval(part))))
            return "".join(out)
        if isinstance(node, A.ListLit):
            items = []
            for item in node.items:
                items.append((yield from self.eval(item)))
            return items
        if isinstance(node, A.RecordLit):
            record = {}
            for key, value in node.pairs:
                record[key] = yield from self.eval(value)
            return record
        if isinstance(node, A.Field):
            target = yield from self.eval(node.target)
            return self.get_field(target, node.name, node.target, node.line)
        if isinstance(node, A.Index):
            target = yield from self.eval(node.target)
            index = yield from self.eval(node.index)
            return self.get_item(target, index, node.line)
        if isinstance(node, A.Call):
            return (yield from self.call(node.name, node.args, node.line))
        if isinstance(node, A.Random):
            low = self.as_number((yield from self.eval(node.low)), node.line, "random")
            high = self.as_number((yield from self.eval(node.high)), node.line, "random")
            if low > high:
                low, high = high, low
            if low == int(low) and high == int(high):
                return float(random.randint(int(low), int(high)))
            return random.uniform(low, high)
        if isinstance(node, A.RandomColor):
            r, g, b = colorsys.hsv_to_rgb(random.random(), 0.65, 0.92)
            return hex_color(r * 255, g * 255, b * 255)
        if isinstance(node, A.UnOp):
            value = yield from self.eval(node.operand)
            return self.unop(node, value)
        if isinstance(node, A.BinOp):
            return (yield from self.eval_binop(node))
        if isinstance(node, A.KeyDown):
            key = format_value((yield from self.eval(node.key))).strip().lower()
            return bool(self.runtime.key_down(key))
        if isinstance(node, A.Mouse):
            mx, my, down = self.runtime.mouse()
            return {"x": float(mx), "y": float(my), "down": bool(down)}[node.what]
        if isinstance(node, A.Touching):
            return self.touching(node.what, node.line)
        if isinstance(node, A.ReadPin):
            raise SparkyError(BOARD_ONLY.format(what="read pin"), node.line)
        if isinstance(node, A.DistanceTo):
            tx, ty = self.place_of(node.what, node.line)
            return math.hypot(tx - self.sprite.x, ty - self.sprite.y)
        raise SparkyError("I got confused by this expression.", node.line)

    def eval_now(self, node):
        """Evaluate an expression right away (for event names)."""
        gen = self.eval(node)
        try:
            while True:
                next(gen)
        except StopIteration as done:
            return done.value

    def unop(self, node, value):
        if node.op == "-":
            return -self.as_number(value, node.line, "-")
        if node.op == "not":
            return not self.truthy(value)
        if node.op == "round":
            return float(round(self.as_number(value, node.line, "round")))
        if node.op == "abs":
            return abs(self.as_number(value, node.line, "abs"))
        raise SparkyError("I got confused by this expression.", node.line)

    def eval_binop(self, node):
        op = node.op
        if op == "and":
            left = yield from self.eval(node.left)
            if not self.truthy(left):
                return False
            return self.truthy((yield from self.eval(node.right)))
        if op == "or":
            left = yield from self.eval(node.left)
            if self.truthy(left):
                return True
            return self.truthy((yield from self.eval(node.right)))

        left = yield from self.eval(node.left)
        right = yield from self.eval(node.right)

        if op == "+":
            if isinstance(left, list) and isinstance(right, list):
                return left + right
            # joining text works with +, like: "Hi " + name
            if isinstance(left, str) or isinstance(right, str):
                return format_value(left) + format_value(right)
            if isinstance(left, list) or isinstance(right, list):
                raise SparkyError('To put something in a list, use: add ITEM to LIST',
                                  node.line)
            return self.as_number(left, node.line, "+") + \
                self.as_number(right, node.line, "+")
        if op == "-":
            return self.as_number(left, node.line, "-") - \
                self.as_number(right, node.line, "-")
        if op == "*":
            return self.as_number(left, node.line, "*") * \
                self.as_number(right, node.line, "*")
        if op == "/":
            right_num = self.as_number(right, node.line, "/")
            if right_num == 0:
                raise SparkyError("You can't divide by zero — "
                                  "not even computers can!", node.line)
            return self.as_number(left, node.line, "/") / right_num
        if op == "mod":
            right_num = self.as_number(right, node.line, "mod")
            if right_num == 0:
                raise SparkyError("You can't divide by zero — "
                                  "not even computers can!", node.line)
            return math.fmod(self.as_number(left, node.line, "mod"), right_num)

        if op in ("=", "!="):
            equal = self.values_equal(left, right)
            return equal if op == "=" else not equal
        if op in (">", "<", ">=", "<="):
            left, right = self.comparable_pair(left, right, node.line, op)
            if op == ">":
                return left > right
            if op == "<":
                return left < right
            if op == ">=":
                return left >= right
            return left <= right
        raise SparkyError("I got confused by this expression.", node.line)

    def values_equal(self, left, right):
        # "5" equals 5, so ask-answers compare nicely with numbers
        if isinstance(left, str) and is_number(right):
            left = self.try_number(left)
        if isinstance(right, str) and is_number(left):
            right = self.try_number(right)
        if is_number(left) and is_number(right):
            return abs(left - right) < 1e-9 * max(1.0, abs(left), abs(right))
        return left == right

    def comparable_pair(self, left, right, line, op):
        if isinstance(left, str):
            left = self.try_number(left)
        if isinstance(right, str):
            right = self.try_number(right)
        if (is_number(left) and is_number(right)) or \
                (isinstance(left, str) and isinstance(right, str)):
            return left, right
        raise SparkyError(f'I can\'t compare {format_value(left, True)} and '
                          f'{format_value(right, True)} with "{op}".', line)

    @staticmethod
    def try_number(text):
        try:
            return float(text)
        except (ValueError, TypeError):
            return text

    def as_number(self, value, line, where):
        if is_number(value):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                raise SparkyError(f'"{where}" needs a number, but got the text '
                                  f'"{value}".', line)
        raise SparkyError(f'"{where}" needs a number, but got '
                          f'{format_value(value, True)}.', line)

    def as_list(self, value, line, where):
        if isinstance(value, list):
            return value
        raise SparkyError(f'"{where}" needs a list, like ["a", "b"], but got '
                          f'{format_value(value, True)}.', line)

    def as_text(self, value, line, where):
        if isinstance(value, str):
            return value
        raise SparkyError(f'"{where}" needs text, like "hello", but got '
                          f'{format_value(value, True)}.', line)

    @staticmethod
    def truthy(value):
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if is_number(value):
            return value != 0
        return len(value) > 0

    def as_color(self, value, line):
        if not isinstance(value, str):
            raise SparkyError('Colors are text, like "red" or "#ff8800". '
                              "Don't forget the quotes!", line)
        name = value.strip().lower()
        if name.startswith("#") and len(name) in (4, 7):
            try:
                int(name[1:], 16)
                return name
            except ValueError:
                pass
        if name in COLORS:
            return COLORS[name]
        hint = did_you_mean(name, COLORS)
        raise SparkyError(f'I don\'t know the color "{value}".{hint} You can also use '
                          'rgb(255, 136, 0) or "#ff8800".', line)

    # ---------- records ----------

    def get_field(self, record, name, target_node, line):
        if isinstance(record, str) and name == "length":
            return float(len(record))
        if not isinstance(record, dict):
            raise SparkyError(f'"{name} of ..." needs a record, like {{name: "Rex"}}, '
                              f"but got {format_value(record, True)}.", line)
        if name not in record:
            what = (f'"{target_node.name}"' if isinstance(target_node, A.Var)
                    else "This record")
            has = ", ".join(record) or "no fields yet"
            raise SparkyError(f'{what} has no "{name}". It has: {has}.', line)
        return record[name]

    def record_target(self, node, name, line):
        record = yield from self.eval(node)
        if not isinstance(record, dict):
            raise SparkyError(f'"{name} of ..." needs a record, like {{name: "Rex"}}, '
                              f"but got {format_value(record, True)}.", line)
        return record

    # ---------- lists ----------

    def item_position(self, seq, index, line):
        number = self.as_number(index, line, "item")
        if number != int(number):
            raise SparkyError(f"Item numbers are whole numbers, like 1 or 2 — "
                              f"not {format_value(number)}.", line)
        number = int(number)
        what = "letters" if isinstance(seq, str) else "items"
        if number == 0:
            raise SparkyError("Items start at 1, so the first one is item 1 "
                              "(and the last one is item -1).", line)
        if number < 0:
            if -number > len(seq):
                raise SparkyError(f"There's no item {number} — that only has "
                                  f"{len(seq)} {what}.", line)
            return len(seq) + number
        if number > len(seq):
            raise SparkyError(f"There's no item {number} — that only has "
                              f"{len(seq)} {what}.", line)
        return number - 1

    def get_item(self, target, index, line):
        if not isinstance(target, (list, str)):
            raise SparkyError(f'"item ... of" needs a list or text, but got '
                              f"{format_value(target, True)}.", line)
        return target[self.item_position(target, index, line)]

    # ---------- sprites ----------

    def find_sprite(self, name, line):
        sprite = self.sprites.get(name)
        if sprite is None:
            hint = did_you_mean(name, self.sprites)
            raise SparkyError(f'I don\'t know a sprite called "{name}".{hint} '
                              f"Make one with: make sprite {name}", line)
        return sprite

    def place_of(self, what, line):
        if what == "mouse":
            mx, my, _ = self.runtime.mouse()
            return float(mx), float(my)
        sprite = self.find_sprite(what, line)
        return sprite.x, sprite.y

    def touching(self, what, line):
        me = self.sprite
        if not me.visible:
            return False
        if what == "edge":
            return (abs(me.x) + me.radius >= STAGE_HALF_W
                    or abs(me.y) + me.radius >= STAGE_HALF_H)
        if what == "mouse":
            mx, my, _ = self.runtime.mouse()
            return math.hypot(mx - me.x, my - me.y) <= me.radius
        other = self.find_sprite(what, line)
        if other is me or not other.visible:
            return False
        return math.hypot(other.x - me.x, other.y - me.y) < me.radius + other.radius

    def show_sprite(self, sprite=None):
        self.runtime.sprite_changed(sprite or self.sprite)

    # ---------- functions ----------

    def call(self, name, arg_nodes, line):
        """Call a command you taught, or a built-in function. A generator."""
        args = []
        for node in arg_nodes:
            args.append((yield from self.eval(node)))
        func = self.functions.get(name)
        if func is not None:
            return (yield from self.run_function(func, args, line))
        builtin = BUILTINS.get(name)
        if builtin is None:
            hint = did_you_mean(name, list(self.functions) + list(BUILTINS))
            raise SparkyError(f'I don\'t know a function called "{name}".{hint} '
                              f'You can make one with: teach {name} ... end', line)
        low, high, fn = builtin
        if not low <= len(args) <= high:
            need = str(low) if low == high else f"{low} to {high}"
            raise SparkyError(f'"{name}" needs {need} input(s) but got '
                              f"{len(args)}.", line)
        return fn(self, args, line)

    def run_function(self, func, args, line):
        if len(args) != len(func.params):
            need = ", ".join(func.params) if func.params else "no inputs"
            raise SparkyError(f'"{func.name}" needs {len(func.params)} '
                              f"input(s) ({need}) but you gave "
                              f"{len(args)}.", line)
        if len(self.frames) >= MAX_CALL_DEPTH:
            raise SparkyError(f'"{func.name}" called itself too many times '
                              "and got dizzy!", line)
        self.frames.append(dict(zip(func.params, args)))
        self.calls.append((func.name, line))
        try:
            yield from self.run_block(func.body)
        except ReturnValue as result:
            return result.value
        except BreakLoop:
            pass
        finally:
            self.frames.pop()
            if self.calls:
                self.calls.pop()
        return None

    # ---------- running ----------

    def run(self):
        """The main generator. Drive it with a for-loop; it yields ticks."""
        # every Sparky call level is several Python generator frames deep
        sys.setrecursionlimit(max(sys.getrecursionlimit(), 6000))
        self.timer_start = time.monotonic()
        try:
            self.handlers = [(node, self.event_value(node))
                             for node in self.program if isinstance(node, A.When)]
            self.threads = [Thread(self.script(self.program), self.main_sprite)]
            yield from self.schedule()
        except HaltProgram:
            pass
        except RecursionError:
            raise SparkyError("Your program went too deep — a command keeps "
                              "calling itself without stopping. Give it a way "
                              "to stop, like: if n < 1 then give back 0", None)
        except SparkyError as err:
            raise attach_example(err, self.source)

    def script(self, body):
        """One thread's whole script. "stop loop" outside a loop ends the script."""
        try:
            yield from self.run_block(body)
        except BreakLoop:
            pass

    def event_value(self, node):
        if node.value is None:
            return None
        return format_value(self.eval_now(node.value)).strip().lower()

    def spawn(self, node, sprite=None):
        thread = Thread(self.script(node.body), sprite or self.main_sprite, handler=node)
        self.threads.append(thread)
        return thread

    def is_running(self, node):
        return any(t.handler is node and not t.done for t in self.threads)

    def dispatch_events(self):
        events = self.runtime.events()
        if not events or not self.handlers:
            return
        for event in events:
            kind = event[0]
            for node, value in self.handlers:
                if kind == "key" and node.kind == "key":
                    key = str(event[1]).lower()
                    if value in (key, "any") and not self.is_running(node):
                        self.spawn(node)
                elif kind == "click" and node.kind == "clicked" and node.sprite == event[1]:
                    if not self.is_running(node):
                        self.spawn(node, self.sprites.get(node.sprite))
                elif kind == "stage_click" and node.kind == "stage":
                    if not self.is_running(node):
                        self.spawn(node)

    def broadcast(self, message):
        started = []
        for node, value in self.handlers:
            if node.kind == "message" and value == message:
                started.append(self.spawn(node))
        return started

    def step(self, thread):
        """Run one thread until it yields a tick. None when it has finished."""
        self.current = thread
        self.frames = thread.frames
        self.calls = thread.calls
        self.sprite = thread.sprite
        try:
            return next(thread.gen)
        except StopIteration:
            thread.done = True
            return None
        finally:
            thread.sprite = self.sprite
            self.current = None

    def schedule(self):
        while True:
            self.dispatch_events()
            live = [t for t in self.threads if not t.done]
            if not live:
                if self.handlers and self.runtime.wants_events():
                    yield ("wait", FRAME, None)       # listening for keys and clicks
                    continue
                return
            passthrough = len(live) == 1 and not self.handlers
            yielded = False
            now = time.monotonic()
            for thread in live:
                if thread.wake > now:
                    continue
                tick = self.step(thread)
                if tick is None:
                    continue
                if tick[0] == "wait" and not passthrough:
                    thread.wake = time.monotonic() + max(0.0, tick[1])
                    continue
                yielded = True
                yield tick
            self.threads = [t for t in self.threads if not t.done]
            if not yielded:
                waiting = [t.wake for t in self.threads if not t.done]
                delay = max(0.0, min(waiting) - time.monotonic()) if waiting else 0.0
                yield ("wait", min(delay, FRAME) if self.handlers else delay, None)

    def run_block(self, body):
        for stmt in body:
            yield from self.execute(stmt)

    def execute(self, stmt):
        if stmt.line in self.break_lines:
            yield ("break", stmt.line)          # a breakpoint: the runner pauses here
        kind = type(stmt).__name__
        method = getattr(self, f"exec_{kind}", None)
        if method is None:
            raise SparkyError("I got confused by this command.", stmt.line)
        yield from method(stmt)

    # ---------- statement handlers ----------

    def exec_Say(self, stmt):
        text = format_value((yield from self.eval(stmt.value)))
        self.runtime.say(text)
        self.runtime.sprite_bubble(text, "say", self.sprite.name)
        yield ("visual", stmt.line)
        if stmt.duration is not None:
            seconds = self.as_number((yield from self.eval(stmt.duration)), stmt.line, "say for")
            yield ("wait", max(0.0, seconds), stmt.line)
            self.runtime.sprite_bubble("", "say", self.sprite.name)
            yield ("visual", stmt.line)

    def exec_Think(self, stmt):
        text = format_value((yield from self.eval(stmt.value)))
        self.runtime.sprite_bubble(text, "think", self.sprite.name)
        yield ("visual", stmt.line)
        if stmt.duration is not None:
            seconds = self.as_number((yield from self.eval(stmt.duration)), stmt.line,
                                     "think for")
            yield ("wait", max(0.0, seconds), stmt.line)
            self.runtime.sprite_bubble("", "think", self.sprite.name)
            yield ("visual", stmt.line)

    def exec_Speak(self, stmt):
        text = format_value((yield from self.eval(stmt.value)))
        self.runtime.speak(text)
        yield ("visual", stmt.line)

    def exec_Ask(self, stmt):
        prompt = format_value((yield from self.eval(stmt.prompt)))
        choices = None
        if stmt.choices is not None:
            choices = self.as_list((yield from self.eval(stmt.choices)), stmt.line, "choices")
            if not choices:
                raise SparkyError('"choices" needs a list with something in it, '
                                  'like ["yes", "no"].', stmt.line)
        while True:
            if choices is not None:
                answer = self.runtime.ask_choice(prompt, [format_value(c) for c in choices])
            else:
                answer = self.runtime.ask(prompt)
            if answer is None:
                raise HaltProgram()
            if choices is not None:
                picked = self.match_choice(answer, choices)
                if picked is _MISSING:
                    names = ", ".join(format_value(c) for c in choices)
                    self.runtime.say(f"Please pick one of: {names}.")
                    yield ("step", stmt.line)
                    continue
                answer = picked
            elif stmt.mode == "number":
                number = self.try_number(str(answer).strip())
                if not is_number(number):
                    self.runtime.say("Please answer with a number, like 7.")
                    yield ("step", stmt.line)
                    continue
                answer = number
            break
        self.set_var(stmt.target, answer)
        yield ("step", stmt.line)

    @staticmethod
    def match_choice(answer, choices):
        text = str(answer).strip().lower()
        for choice in choices:
            if format_value(choice).lower() == text:
                return choice
        if text.isdigit() and 1 <= int(text) <= len(choices):
            return choices[int(text) - 1]
        return _MISSING

    def exec_SetVar(self, stmt):
        self.set_var(stmt.name, (yield from self.eval(stmt.value)))
        yield ("step", stmt.line)

    def exec_ChangeVar(self, stmt):
        current = self.as_number(self.get_var(stmt.name, stmt.line),
                                 stmt.line, "change")
        amount = self.as_number((yield from self.eval(stmt.amount)),
                                stmt.line, "change")
        self.set_var(stmt.name, current + amount)
        yield ("step", stmt.line)

    def exec_SetField(self, stmt):
        record = yield from self.record_target(stmt.target, stmt.name, stmt.line)
        record[stmt.name] = yield from self.eval(stmt.value)
        yield ("step", stmt.line)

    def exec_ChangeField(self, stmt):
        record = yield from self.record_target(stmt.target, stmt.name, stmt.line)
        current = self.as_number(self.get_field(record, stmt.name, stmt.target, stmt.line),
                                 stmt.line, "change")
        amount = self.as_number((yield from self.eval(stmt.amount)), stmt.line, "change")
        record[stmt.name] = current + amount
        yield ("step", stmt.line)

    def exec_RepeatTimes(self, stmt):
        count = int(self.as_number((yield from self.eval(stmt.count)),
                                   stmt.line, "repeat"))
        try:
            for _ in range(max(0, count)):
                yield from self.run_block(stmt.body)
                yield ("step", stmt.line)
        except BreakLoop:
            pass

    def exec_RepeatUntil(self, stmt):
        try:
            while not self.truthy((yield from self.eval(stmt.condition))):
                yield from self.run_block(stmt.body)
                yield ("step", stmt.line)
        except BreakLoop:
            pass

    def exec_RepeatWhile(self, stmt):
        try:
            while self.truthy((yield from self.eval(stmt.condition))):
                yield from self.run_block(stmt.body)
                yield ("step", stmt.line)
        except BreakLoop:
            pass

    def exec_Forever(self, stmt):
        try:
            while True:
                yield from self.run_block(stmt.body)
                yield ("step", stmt.line)
        except BreakLoop:
            pass

    def exec_ForEach(self, stmt):
        things = yield from self.eval(stmt.iterable)
        if isinstance(things, str):
            things = list(things)
        elif isinstance(things, dict):
            things = list(things)
        things = list(self.as_list(things, stmt.line, "for each"))
        try:
            for thing in things:
                self.set_var(stmt.name, thing)
                yield from self.run_block(stmt.body)
                yield ("step", stmt.line)
        except BreakLoop:
            pass

    def exec_ForRange(self, stmt):
        start = self.as_number((yield from self.eval(stmt.start)), stmt.line, "for")
        stop = self.as_number((yield from self.eval(stmt.stop)), stmt.line, "for")
        step = 1.0 if start <= stop else -1.0
        if stmt.step is not None:
            step = self.as_number((yield from self.eval(stmt.step)), stmt.line, "for ... by")
            if step == 0:
                raise SparkyError('"by 0" would count forever. Use a number like 1 or 2.',
                                  stmt.line)
        value = start
        try:
            while (step > 0 and value <= stop + 1e-9) or (step < 0 and value >= stop - 1e-9):
                self.set_var(stmt.name, value)
                yield from self.run_block(stmt.body)
                yield ("step", stmt.line)
                value += step
        except BreakLoop:
            pass

    def exec_If(self, stmt):
        for condition, body in stmt.branches:
            if self.truthy((yield from self.eval(condition))):
                yield from self.run_block(body)
                return
        if stmt.else_body is not None:
            yield from self.run_block(stmt.else_body)

    def exec_Wait(self, stmt):
        seconds = self.as_number((yield from self.eval(stmt.seconds)),
                                 stmt.line, "wait")
        yield ("wait", max(0.0, seconds), stmt.line)

    def exec_WaitUntil(self, stmt):
        while not self.truthy((yield from self.eval(stmt.condition))):
            yield ("wait", FRAME, stmt.line)
        yield ("step", stmt.line)

    def exec_StopLoop(self, stmt):
        raise BreakLoop()
        yield  # pragma: no cover (makes this a generator)

    def exec_StopProgram(self, stmt):
        raise HaltProgram()
        yield  # pragma: no cover

    def exec_Teach(self, stmt):
        self.functions[stmt.name] = stmt
        yield ("step", stmt.line)

    def exec_Do(self, stmt):
        func = self.functions.get(stmt.name)
        if func is None:
            hint = did_you_mean(stmt.name, self.functions)
            raise SparkyError(f'I don\'t know how to do "{stmt.name}".{hint} '
                              f'You can teach me with: teach {stmt.name} ... end',
                              stmt.line)
        args = []
        for node in stmt.args:
            args.append((yield from self.eval(node)))
        yield from self.run_function(func, args, stmt.line)

    def exec_ExprStatement(self, stmt):
        yield from self.eval(stmt.expr)
        yield ("step", stmt.line)

    def exec_Return(self, stmt):
        if not self.frames:
            raise SparkyError('"give back" only works inside a command you '
                              "taught with teach.", stmt.line)
        raise ReturnValue((yield from self.eval(stmt.value)))

    def exec_AddTo(self, stmt):
        value = yield from self.eval(stmt.value)
        current = self.get_var(stmt.name, stmt.line)
        if isinstance(current, list):
            current.append(value)
        elif isinstance(current, str):
            self.set_var(stmt.name, current + format_value(value))
        elif is_number(current):
            self.set_var(stmt.name, current + self.as_number(value, stmt.line, "add"))
        else:
            raise SparkyError(f'I can\'t add to "{stmt.name}" — it holds '
                              f"{format_value(current, True)}. Try: "
                              f"set {stmt.name} to []", stmt.line)
        yield ("step", stmt.line)

    def exec_RemoveFrom(self, stmt):
        value = yield from self.eval(stmt.value)
        things = self.as_list(self.get_var(stmt.name, stmt.line), stmt.line, "remove")
        for i, thing in enumerate(things):
            if self.values_equal(thing, value):
                del things[i]
                break
        else:
            raise SparkyError(f"I couldn't find {format_value(value, True)} in "
                              f'"{stmt.name}".', stmt.line)
        yield ("step", stmt.line)

    def exec_SetItem(self, stmt):
        index = yield from self.eval(stmt.index)
        value = yield from self.eval(stmt.value)
        things = self.as_list(self.get_var(stmt.name, stmt.line), stmt.line,
                              "set item")
        things[self.item_position(things, index, stmt.line)] = value
        yield ("step", stmt.line)

    def exec_InsertAt(self, stmt):
        value = yield from self.eval(stmt.value)
        index = self.as_number((yield from self.eval(stmt.index)), stmt.line, "insert")
        things = self.as_list(self.get_var(stmt.name, stmt.line), stmt.line, "insert")
        n = int(index)
        if n != index or n == 0 or not -(len(things) + 1) <= n <= len(things) + 1:
            raise SparkyError(f"I can insert at 1 to {len(things) + 1} in "
                              f'"{stmt.name}" (it has {len(things)} items).', stmt.line)
        things.insert(n - 1 if n > 0 else len(things) + 1 + n, value)
        yield ("step", stmt.line)

    def exec_ResetTimer(self, stmt):
        self.timer_start = time.monotonic()
        yield ("step", stmt.line)

    def exec_Use(self, stmt):
        name = self.as_text((yield from self.eval(stmt.path)), stmt.line, "use")
        path = Path(name)
        if not path.is_absolute():
            path = (self.base_dir or Path.cwd()) / path
        if not path.exists() and path.suffix == "":
            path = path.with_suffix(".spark")
        if not path.is_file():
            raise SparkyError(f'I couldn\'t find "{name}" next to your program. Save '
                              "both files in the same folder.", stmt.line)
        key = str(path.resolve())
        if key not in self.used_files:
            self.used_files.add(key)
            from .parser import parse
            try:
                program = parse(path.read_text(encoding="utf-8"))
            except SparkyError as err:
                where = f" line {err.line}" if err.line else ""
                raise SparkyError(f"In {path.name}{where}: {err.message}", stmt.line)
            for node in program:
                if isinstance(node, A.Teach):
                    self.functions[node.name] = node
                elif isinstance(node, A.Use):
                    saved = self.base_dir
                    self.base_dir = path.parent
                    try:
                        yield from self.exec_Use(node)
                    finally:
                        self.base_dir = saved
        yield ("step", stmt.line)

    def exec_Try(self, stmt):
        try:
            yield from self.run_block(stmt.body)
        except SparkyError as err:
            self.set_var("problem", err.message)
            yield ("step", stmt.line)
            yield from self.run_block(stmt.oops_body)

    # ---------- events ----------

    def exec_When(self, stmt):
        return
        yield  # pragma: no cover (when-blocks are set up before the program starts)

    def exec_Broadcast(self, stmt):
        message = format_value((yield from self.eval(stmt.message))).strip().lower()
        started = self.broadcast(message)
        yield ("step", stmt.line)
        if stmt.wait:
            while any(not t.done for t in started):
                yield ("wait", 0.0, stmt.line)

    def exec_NextFrame(self, stmt):
        yield ("visual", stmt.line)
        now = time.monotonic()
        if self.last_frame is None:
            self.last_frame = self.timer_start
        target = self.last_frame + FRAME
        self.last_frame = max(target, now)
        yield ("wait", max(0.0, target - now), stmt.line)

    # ---------- sprites ----------

    def costume_value(self, value, line):
        if value is None:
            return None
        text = format_value(value).strip()
        name = text.lower()
        if name in ("sparky", ""):
            return None
        if name in COSTUMES:
            return COSTUMES[name]
        if len(text) <= 4 and not text.isascii():
            return text            # an emoji
        hint = did_you_mean(name, COSTUMES)
        raise SparkyError(f'I don\'t know the costume "{text}".{hint} Use an emoji like '
                          '"🐱", or a name like "cat", "rocket" or "sparky".', line)

    def exec_MakeSprite(self, stmt):
        costume = None
        if stmt.costume is not None:
            costume = self.costume_value((yield from self.eval(stmt.costume)), stmt.line)
        sprite = self.sprites.get(stmt.name)
        if sprite is None:
            sprite = Sprite(stmt.name, costume, pen_down=False)
            self.top_layer += 1
            sprite.layer = self.top_layer
            self.sprites[stmt.name] = sprite
        else:
            sprite.costume = costume
        self.show_sprite(sprite)
        yield ("visual", stmt.line)

    def exec_Tell(self, stmt):
        sprite = self.find_sprite(stmt.name, stmt.line)
        saved = self.sprite
        self.sprite = sprite
        try:
            yield from self.run_block(stmt.body)
        finally:
            self.sprite = saved

    def exec_Costume(self, stmt):
        if stmt.value is None:
            current = self.sprite.costume
            index = COSTUME_ORDER.index(current) + 1 if current in COSTUME_ORDER else 0
            self.sprite.costume = COSTUME_ORDER[index % len(COSTUME_ORDER)]
        else:
            self.sprite.costume = self.costume_value((yield from self.eval(stmt.value)),
                                                     stmt.line)
        self.show_sprite()
        yield ("visual", stmt.line)

    def exec_Ghost(self, stmt):
        value = self.as_number((yield from self.eval(stmt.value)), stmt.line, "ghost")
        self.sprite.ghost = max(0.0, min(100.0, value))
        self.show_sprite()
        yield ("visual", stmt.line)

    def exec_Layer(self, stmt):
        if stmt.where == "front":
            self.top_layer += 1
            self.sprite.layer = self.top_layer
        else:
            self.sprite.layer = min(s.layer for s in self.sprites.values()) - 1
        self.show_sprite()
        yield ("visual", stmt.line)

    def exec_Bounce(self, stmt):
        me = self.sprite
        r = me.radius
        bounced = False
        if me.x + r > STAGE_HALF_W or me.x - r < -STAGE_HALF_W:
            me.x = max(-STAGE_HALF_W + r, min(STAGE_HALF_W - r, me.x))
            me.heading = (360.0 - me.heading) % 360.0
            bounced = True
        if me.y + r > STAGE_HALF_H or me.y - r < -STAGE_HALF_H:
            me.y = max(-STAGE_HALF_H + r, min(STAGE_HALF_H - r, me.y))
            me.heading = (180.0 - me.heading) % 360.0
            bounced = True
        if bounced:
            self.show_sprite()
        yield ("visual", stmt.line)

    def exec_Glide(self, stmt):
        x = self.as_number((yield from self.eval(stmt.x)), stmt.line, "glide")
        y = self.as_number((yield from self.eval(stmt.y)), stmt.line, "glide")
        seconds = max(0.0, self.as_number((yield from self.eval(stmt.seconds)), stmt.line,
                                          "glide"))
        start_x, start_y = self.sprite.x, self.sprite.y
        steps = max(1, int(seconds * 30))
        for i in range(1, steps + 1):
            t = i / steps
            self.move_sprite(start_x + (x - start_x) * t, start_y + (y - start_y) * t)
            yield ("visual", stmt.line)
            if seconds:
                yield ("wait", seconds / steps, stmt.line)

    # ---------- sprite / stage handlers ----------

    def move_sprite(self, new_x, new_y):
        me = self.sprite
        if me.pen_down:
            pen = me.pen()
            if me.rainbow:
                me.hue = (me.hue + math.hypot(new_x - me.x, new_y - me.y) / 400.0) % 1.0
                r, g, b = colorsys.hsv_to_rgb(me.hue, 0.75, 0.95)
                pen["color"] = hex_color(r * 255, g * 255, b * 255)
            self.runtime.pen_line(me.x, me.y, new_x, new_y, pen)
        me.x, me.y = new_x, new_y
        self.show_sprite()

    def exec_Move(self, stmt):
        distance = self.as_number((yield from self.eval(stmt.distance)), stmt.line, "move")
        radians = math.radians(self.sprite.heading)
        dx = math.sin(radians)
        dy = math.cos(radians)
        # chunk long moves into little hops so the sprite glides
        hops = 1 if self.speed >= 10 else max(1, min(30, int(abs(distance) / 8)))
        for _ in range(hops):
            self.move_sprite(self.sprite.x + dx * distance / hops,
                             self.sprite.y + dy * distance / hops)
            yield ("visual", stmt.line)

    def exec_Turn(self, stmt):
        degrees = self.as_number((yield from self.eval(stmt.degrees)), stmt.line, "turn")
        self.sprite.heading = (self.sprite.heading + degrees * stmt.direction) % 360
        self.show_sprite()
        yield ("visual", stmt.line)

    def exec_Point(self, stmt):
        self.sprite.heading = self.as_number((yield from self.eval(stmt.heading)),
                                             stmt.line, "point") % 360
        self.show_sprite()
        yield ("visual", stmt.line)

    def exec_Goto(self, stmt):
        x = self.as_number((yield from self.eval(stmt.x)), stmt.line, "goto")
        y = self.as_number((yield from self.eval(stmt.y)), stmt.line, "goto")
        self.move_sprite(x, y)
        yield ("visual", stmt.line)

    def exec_Home(self, stmt):
        self.move_sprite(0.0, 0.0)
        self.sprite.heading = 0.0
        self.show_sprite()
        yield ("visual", stmt.line)

    def exec_Pen(self, stmt):
        me = self.sprite
        if stmt.mode == "up":
            me.pen_down = False
        elif stmt.mode == "down":
            me.pen_down = True
        elif stmt.mode == "color":
            value = yield from self.eval(stmt.value)
            if isinstance(value, str) and value.strip().lower() == "rainbow":
                me.rainbow = True
            else:
                me.rainbow = False
                me.pen_color = self.as_color(value, stmt.line)
        elif stmt.mode == "size":
            size = self.as_number((yield from self.eval(stmt.value)), stmt.line, "pen size")
            me.pen_size = max(0.5, min(60.0, size))
        elif stmt.mode == "style":
            style = format_value((yield from self.eval(stmt.value))).strip().lower()
            if style not in ("solid", "dashed", "dotted"):
                raise SparkyError('Pen styles are solid, dashed and dotted — like: '
                                  "pen style dashed", stmt.line)
            me.pen_style = style
        elif stmt.mode == "opacity":
            value = self.as_number((yield from self.eval(stmt.value)), stmt.line, "pen opacity")
            me.pen_opacity = max(0.0, min(100.0, value)) / 100.0
        yield ("step", stmt.line)

    def exec_Fill(self, stmt):
        if stmt.value is None:
            self.sprite.fill = None
        else:
            self.sprite.fill = self.as_color((yield from self.eval(stmt.value)), stmt.line)
        yield ("step", stmt.line)

    def shape_points(self, local, close=True):
        """Turn shape points around the sprite (x right, y up when heading 0) into
        stage points, rotated with the sprite's heading."""
        me = self.sprite
        h = math.radians(me.heading)
        c, s = math.cos(h), math.sin(h)
        return [(me.x + dx * c + dy * s, me.y - dx * s + dy * c) for dx, dy in local]

    def exec_Shape(self, stmt):
        args = []
        for node in stmt.args:
            args.append(self.as_number((yield from self.eval(node)), stmt.line, stmt.kind))
        me = self.sprite
        pen = me.pen()
        if me.rainbow:          # each shape gets the next color of the rainbow
            me.hue = (me.hue + 0.09) % 1.0
            r, g, b = colorsys.hsv_to_rgb(me.hue, 0.75, 0.95)
            pen["color"] = hex_color(r * 255, g * 255, b * 255)
        fill = me.fill
        closed = True
        kind = stmt.kind
        if kind == "circle":
            r = abs(args[0])
            local = [(r * math.sin(2 * math.pi * i / 72), r * math.cos(2 * math.pi * i / 72))
                     for i in range(72)]
        elif kind == "dot":
            r = abs(args[0]) / 2
            local = [(r * math.sin(2 * math.pi * i / 24), r * math.cos(2 * math.pi * i / 24))
                     for i in range(24)]
            fill = me.pen_color
            pen = dict(pen, width=0)
        elif kind == "rectangle":
            w, h = abs(args[0]) / 2, abs(args[1]) / 2
            local = [(-w, h), (w, h), (w, -h), (-w, -h)]
        elif kind in ("polygon", "star"):
            n = int(args[0])
            if n < 3 or n > 100:
                raise SparkyError(f"A {kind} needs 3 to 100 {'sides' if kind == 'polygon' else 'points'}.",
                                  stmt.line)
            r = abs(args[1])
            if kind == "polygon":
                local = [(r * math.sin(2 * math.pi * i / n), r * math.cos(2 * math.pi * i / n))
                         for i in range(n)]
            else:
                local = []
                for i in range(2 * n):
                    rr = r if i % 2 == 0 else r * 0.45
                    a = math.pi * i / n
                    local.append((rr * math.sin(a), rr * math.cos(a)))
        else:   # arc DEGREES radius R — clockwise from where the sprite points
            degrees, r = args[0], abs(args[1])
            steps = max(2, int(abs(degrees) / 5) + 1)
            local = [(r * math.sin(math.radians(degrees * i / (steps - 1))),
                      r * math.cos(math.radians(degrees * i / (steps - 1))))
                     for i in range(steps)]
            closed = False
            fill = None
        self.runtime.shape(self.shape_points(local), closed, pen, fill)
        yield ("visual", stmt.line)

    def exec_Clear(self, stmt):
        self.runtime.clear()
        yield ("visual", stmt.line)

    def exec_HideShow(self, stmt):
        self.sprite.visible = stmt.visible
        self.show_sprite()
        yield ("visual", stmt.line)

    def exec_Stamp(self, stmt):
        me = self.sprite
        self.runtime.stamp_sprite(me.snapshot())
        yield ("visual", stmt.line)

    def exec_Background(self, stmt):
        self.runtime.background(self.as_color((yield from self.eval(stmt.color)), stmt.line))
        yield ("visual", stmt.line)

    def exec_Backdrop(self, stmt):
        value = format_value((yield from self.eval(stmt.value))).strip()
        name = value.lower()
        if name in BACKDROPS:
            self.runtime.backdrop(name)
        elif name.endswith(IMAGE_TYPES):
            path = Path(value)
            if not path.is_absolute():
                path = (self.base_dir or Path.cwd()) / path
            if not path.is_file():
                raise SparkyError(f'I couldn\'t find the picture "{value}". Put it in the '
                                  "same folder as your program.", stmt.line)
            self.runtime.backdrop(str(path))
        else:
            hint = did_you_mean(name, BACKDROPS)
            raise SparkyError(f'I don\'t know the backdrop "{value}".{hint} Try: '
                              f'{", ".join(BACKDROPS)}, or a picture file.', stmt.line)
        yield ("visual", stmt.line)

    def exec_Speed(self, stmt):
        value = self.as_number((yield from self.eval(stmt.value)), stmt.line, "speed")
        self.speed = max(1, min(10, int(value)))
        yield ("step", stmt.line)

    def exec_WriteText(self, stmt):
        text = format_value((yield from self.eval(stmt.value)))
        style = {}
        for key, value in stmt.style.items():
            if key == "size":
                size = self.as_number((yield from self.eval(value)), stmt.line, "write size")
                style["size"] = max(4.0, min(200.0, size))
            else:
                style[key] = True
        me = self.sprite
        self.runtime.write_styled(me.x, me.y, text, me.pen_color, me.scale, style)
        yield ("visual", stmt.line)

    def exec_Beep(self, stmt):
        self.runtime.beep()
        yield ("visual", stmt.line)

    def exec_SpriteSize(self, stmt):
        percent = self.as_number((yield from self.eval(stmt.percent)), stmt.line, "size")
        self.sprite.scale = max(0.1, min(10.0, percent / 100.0))
        self.show_sprite()
        yield ("visual", stmt.line)

    def exec_PlaySound(self, stmt):
        if stmt.kind == "name":
            name = (yield from self.eval(stmt.value))
            if not isinstance(name, str):
                raise SparkyError('Sound names are text, like play "pop". '
                                  "Don't forget the quotes!", stmt.line)
            name = name.strip().lower()
            if name not in SOUND_NAMES:
                hint = did_you_mean(name, SOUND_NAMES)
                sounds = ", ".join(SOUND_NAMES)
                raise SparkyError(f'I don\'t know the sound "{name}".{hint} '
                                  f"I can play: {sounds}.", stmt.line)
            self.runtime.play_sound(name, 0, 0.0)
            yield ("visual", stmt.line)
            return
        # play note N (for X) — notes go 1..14 (two do-re-mi octaves)
        note = self.as_number((yield from self.eval(stmt.value)), stmt.line, "play note")
        note = int(note)
        if not 1 <= note <= 14:
            raise SparkyError("Notes go from 1 (low do) to 14 (high do, "
                              "one octave up from 8).", stmt.line)
        duration = 0.4
        if stmt.duration is not None:
            duration = self.as_number((yield from self.eval(stmt.duration)),
                                      stmt.line, "play note ... for")
        duration = max(0.05, min(4.0, duration))
        self.runtime.play_sound("", note, duration)
        # the note plays while the program waits, so melodies line up
        yield ("wait", duration, stmt.line)

    # ---------- Sparky for Arduino ----------

    def exec_Pin(self, stmt):
        raise SparkyError(BOARD_ONLY.format(what="pin"), stmt.line)
        yield  # pragma: no cover

    def exec_Servo(self, stmt):
        raise SparkyError(BOARD_ONLY.format(what="servo"), stmt.line)
        yield  # pragma: no cover

    def exec_Buzzer(self, stmt):
        raise SparkyError(BOARD_ONLY.format(what="buzzer"), stmt.line)
        yield  # pragma: no cover

    # ---------- memory between runs ----------

    def exec_Save(self, stmt):
        value = yield from self.eval(stmt.value)
        name = format_value((yield from self.eval(stmt.name))).strip()
        if not name:
            raise SparkyError('Give what you save a name, like: save score as "best"',
                              stmt.line)
        self.runtime.save_value(name, value)
        yield ("step", stmt.line)

    def exec_Load(self, stmt):
        name = format_value((yield from self.eval(stmt.name))).strip()
        value = self.runtime.load_value(name)
        self.set_var(stmt.target, 0.0 if value is None else value)
        yield ("step", stmt.line)


# ---------- built-in functions: name(inputs) ----------

def _length(it, args, line):
    value = args[0]
    if isinstance(value, (list, str, dict)):
        return float(len(value))
    raise SparkyError(f'"length" needs a list or text, but got '
                      f"{format_value(value, True)}.", line)


def _number(it, args, line):
    value = args[0]
    if is_number(value):
        return float(value)
    try:
        return float(str(value).strip())
    except ValueError:
        raise SparkyError(f'I can\'t turn "{format_value(value)}" into a number.', line)


def _sqrt(it, args, line):
    n = it.as_number(args[0], line, "sqrt")
    if n < 0:
        raise SparkyError("sqrt needs a number that isn't negative.", line)
    return math.sqrt(n)


def _power(it, args, line):
    base = it.as_number(args[0], line, "power")
    exp = it.as_number(args[1], line, "power")
    if base.is_integer() and exp.is_integer() and 0 <= exp <= 1000:
        return int(base) ** int(exp)            # exact, so big answers stay right
    try:
        return base ** exp
    except (OverflowError, ZeroDivisionError):
        raise SparkyError("That power is too big (or divides by zero).", line)


def _round(it, args, line):
    value = it.as_number(args[0], line, "round")
    if len(args) == 1:
        return float(round(value))
    places = int(it.as_number(args[1], line, "round"))
    return round(value, max(0, min(10, places)))


def _log(it, args, line):
    n = it.as_number(args[0], line, "log")
    if n <= 0:
        raise SparkyError("log needs a number bigger than 0.", line)
    return math.log10(n)


def _ln(it, args, line):
    n = it.as_number(args[0], line, "ln")
    if n <= 0:
        raise SparkyError("ln needs a number bigger than 0.", line)
    return math.log(n)


def _clamp(it, args, line):
    value, low, high = (it.as_number(a, line, "clamp") for a in args)
    if low > high:
        low, high = high, low
    return max(low, min(high, value))


def _from_sprite(it, args, line, where):
    if len(args) == 2:
        return it.sprite.x, it.sprite.y, it.as_number(args[0], line, where), \
            it.as_number(args[1], line, where)
    return tuple(it.as_number(a, line, where) for a in args)


def _distance(it, args, line):
    if len(args) not in (2, 4):
        raise SparkyError('"distance" needs 2 inputs (x, y) or 4 (x1, y1, x2, y2).', line)
    x1, y1, x2, y2 = _from_sprite(it, args, line, "distance")
    return math.hypot(x2 - x1, y2 - y1)


def _angle(it, args, line):
    if len(args) not in (2, 4):
        raise SparkyError('"angle" needs 2 inputs (x, y) or 4 (x1, y1, x2, y2).', line)
    x1, y1, x2, y2 = _from_sprite(it, args, line, "angle")
    return round(math.degrees(math.atan2(x2 - x1, y2 - y1)) % 360.0, 9)


def _rgb(it, args, line):
    return hex_color(*(it.as_number(a, line, "rgb") for a in args))


def _minmax(pick):
    def fn(it, args, line):
        values = args[0] if len(args) == 1 and isinstance(args[0], list) else args
        if not values:
            raise SparkyError(f'"{pick.__name__}" needs at least one number.', line)
        return pick(it.as_number(v, line, pick.__name__) for v in values)
    return fn


def _join(it, args, line):
    things = it.as_list(args[0], line, "join")
    sep = format_value(args[1]) if len(args) > 1 else ""
    return sep.join(format_value(t) for t in things)


def _split(it, args, line):
    text = it.as_text(args[0], line, "split")
    if len(args) > 1:
        sep = format_value(args[1])
        if sep == "":
            return list(text)
        return text.split(sep)
    return text.split()


def _contains(it, args, line):
    where, what = args
    if isinstance(where, str):
        return format_value(what) in where
    if isinstance(where, dict):
        return format_value(what).lower() in where
    things = it.as_list(where, line, "contains")
    return any(it.values_equal(t, what) for t in things)


def _pick(it, args, line):
    things = args[0]
    if not isinstance(things, (list, str)) or not things:
        raise SparkyError('"pick" needs a list with something in it.', line)
    return random.choice(things)


def _reverse(it, args, line):
    value = args[0]
    if isinstance(value, str):
        return value[::-1]
    return list(reversed(it.as_list(value, line, "reverse")))


def _sort(it, args, line):
    things = it.as_list(args[0], line, "sort")
    if all(is_number(t) for t in things) or all(isinstance(t, str) for t in things):
        return sorted(things)
    raise SparkyError('"sort" needs a list of all numbers or all text.', line)


def _trig(fn):
    def call(it, args, line):
        return fn(math.radians(it.as_number(args[0], line, fn.__name__)))
    return call


def _replace(it, args, line):
    text = it.as_text(args[0], line, "replace")
    return text.replace(format_value(args[1]), format_value(args[2]))


def _find(it, args, line):
    text = it.as_text(args[0], line, "find")
    return float(text.find(format_value(args[1])) + 1)


def _index(it, args, line):
    where, what = args
    if isinstance(where, str):
        return float(where.find(format_value(what)) + 1)
    for i, thing in enumerate(it.as_list(where, line, "index")):
        if it.values_equal(thing, what):
            return float(i + 1)
    return 0.0


def _slice(it, args, line):
    seq = args[0]
    if not isinstance(seq, (list, str)):
        raise SparkyError(f'"slice" needs a list or text, but got {format_value(seq, True)}.',
                          line)
    start = int(it.as_number(args[1], line, "slice"))
    end = int(it.as_number(args[2], line, "slice")) if len(args) > 2 else len(seq)
    if start < 0:
        start = len(seq) + start + 1
    if end < 0:
        end = len(seq) + end + 1
    return seq[max(0, start - 1):max(0, end)]


def _range(it, args, line):
    start = it.as_number(args[0], line, "range")
    stop = it.as_number(args[1], line, "range")
    step = it.as_number(args[2], line, "range") if len(args) > 2 else (1.0 if start <= stop else -1.0)
    if step == 0:
        raise SparkyError('"range" can\'t count by 0.', line)
    out, value = [], start
    while (step > 0 and value <= stop + 1e-9) or (step < 0 and value >= stop - 1e-9):
        out.append(value)
        value += step
        if len(out) > 100000:
            raise SparkyError('That range has more than 100,000 numbers.', line)
    return out


def _shuffle(it, args, line):
    things = list(it.as_list(args[0], line, "shuffle"))
    random.shuffle(things)
    return things


def _unique(it, args, line):
    out = []
    for thing in it.as_list(args[0], line, "unique"):
        if not any(it.values_equal(thing, seen) for seen in out):
            out.append(thing)
    return out


def _count(it, args, line):
    where, what = args
    if isinstance(where, str):
        return float(where.count(format_value(what)))
    return float(sum(1 for t in it.as_list(where, line, "count") if it.values_equal(t, what)))


def _keys(it, args, line):
    record = args[0]
    if not isinstance(record, dict):
        raise SparkyError(f'"keys" needs a record, but got {format_value(record, True)}.', line)
    return list(record)


BUILTINS = {
    # name: (fewest inputs, most inputs, function)
    "length": (1, 1, _length),
    "upper": (1, 1, lambda it, a, l: it.as_text(a[0], l, "upper").upper()),
    "lower": (1, 1, lambda it, a, l: it.as_text(a[0], l, "lower").lower()),
    "trim": (1, 1, lambda it, a, l: it.as_text(a[0], l, "trim").strip()),
    "capital": (1, 1, lambda it, a, l: (lambda t: t[:1].upper() + t[1:])(
        it.as_text(a[0], l, "capital"))),
    "text": (1, 1, lambda it, a, l: format_value(a[0])),
    "number": (1, 1, _number),
    "sqrt": (1, 1, _sqrt),
    "power": (2, 2, _power),
    "round": (1, 2, _round),
    "abs": (1, 1, lambda it, a, l: abs(it.as_number(a[0], l, "abs"))),
    "floor": (1, 1, lambda it, a, l: float(math.floor(it.as_number(a[0], l, "floor")))),
    "ceil": (1, 1, lambda it, a, l: float(math.ceil(it.as_number(a[0], l, "ceil")))),
    "log": (1, 1, _log),
    "ln": (1, 1, _ln),
    "clamp": (3, 3, _clamp),
    "sin": (1, 1, _trig(math.sin)),
    "cos": (1, 1, _trig(math.cos)),
    "tan": (1, 1, _trig(math.tan)),
    "min": (1, 99, _minmax(min)),
    "max": (1, 99, _minmax(max)),
    "sum": (1, 1, lambda it, a, l: float(sum(it.as_number(v, l, "sum")
                                             for v in it.as_list(a[0], l, "sum")))),
    "distance": (2, 4, _distance),
    "angle": (2, 4, _angle),
    "rgb": (3, 3, _rgb),
    "join": (1, 2, _join),
    "split": (1, 2, _split),
    "contains": (2, 2, _contains),
    "replace": (3, 3, _replace),
    "begins": (2, 2, lambda it, a, l: it.as_text(a[0], l, "begins").startswith(format_value(a[1]))),
    "ends": (2, 2, lambda it, a, l: it.as_text(a[0], l, "ends").endswith(format_value(a[1]))),
    "find": (2, 2, _find),
    "words": (1, 1, lambda it, a, l: it.as_text(a[0], l, "words").split()),
    "letters": (1, 1, lambda it, a, l: list(it.as_text(a[0], l, "letters"))),
    "pick": (1, 1, _pick),
    "reverse": (1, 1, _reverse),
    "sort": (1, 1, _sort),
    "index": (2, 2, _index),
    "slice": (2, 3, _slice),
    "range": (2, 3, _range),
    "shuffle": (1, 1, _shuffle),
    "unique": (1, 1, _unique),
    "count": (2, 2, _count),
    "keys": (1, 1, _keys),
    "xpos": (0, 0, lambda it, a, l: it.sprite.x),
    "ypos": (0, 0, lambda it, a, l: it.sprite.y),
    "direction": (0, 0, lambda it, a, l: it.sprite.heading),
}
