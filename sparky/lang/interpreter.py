# Sparky interpreter: walks the AST and makes things happen.
#
# It runs as a GENERATOR — after (almost) every statement it yields a small
# tick tuple. Whoever drives the generator (the IDE or the console runner)
# uses those ticks to animate the stage, pace the program, and stop it.
#
# Tick shapes:
#   ("step", line)          — a logic statement ran
#   ("visual", line)        — something on the stage changed
#   ("wait", seconds, line) — the program asked to pause
#
# Expressions are generators too (`yield from self.eval(node)`), so a
# command you taught can be called inside an expression — `say double(21)`
# — and still animate, pause and stop like everything else.

import math
import random
import sys

from . import ast_nodes as A
from .errors import SparkyError, did_you_mean

COLORS = {
    "red": "#e5484d", "orange": "#d97757", "yellow": "#f5c518",
    "green": "#788c5d", "blue": "#6a9bcc", "purple": "#8e7cc3",
    "pink": "#e58fb1", "brown": "#8d6748", "black": "#141413",
    "white": "#faf9f5", "gray": "#b0aea5", "grey": "#b0aea5",
    "cyan": "#4cc2c4", "magenta": "#c65ca8", "lime": "#9fbf3b",
    "navy": "#2d4a6b", "cream": "#faf9f5", "ink": "#141413",
}

MAX_CALL_DEPTH = 150

# built-in sound effects for `play "name"`
SOUND_NAMES = ("pop", "ding", "boing", "laser", "drum", "tada", "jump")


class BreakLoop(Exception):
    pass


class HaltProgram(Exception):
    pass


class ReturnValue(Exception):
    def __init__(self, value):
        super().__init__()
        self.value = value


def format_value(value, quoted=False):
    """How Sparky shows values to kids: 3.0 prints as 3, True as true."""
    if value is None:
        return "nothing"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if value == int(value) and abs(value) < 1e15:
            return str(int(value))
        return str(round(value, 6))
    if isinstance(value, list):
        return "[" + ", ".join(format_value(v, quoted=True) for v in value) + "]"
    if quoted and isinstance(value, str):
        return f'"{value}"'
    return str(value)


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


class Interpreter:
    def __init__(self, program, runtime):
        self.program = program
        self.runtime = runtime
        self.globals = {}
        self.frames = []          # local scopes for commands you taught
        self.functions = {}
        self.speed = 5            # 1 (slow) .. 10 (instant)

        # sprite state — Scratch-style: origin at center, y grows upward,
        # heading 0 points up and turning right is clockwise
        self.x = 0.0
        self.y = 0.0
        self.heading = 0.0
        self.pen_down = True
        self.pen_color = "#141413"
        self.pen_size = 3.0
        self.visible = True
        self.scale = 1.0

    # ---------- variables ----------

    def get_var(self, name, line):
        if self.frames and name in self.frames[-1]:
            return self.frames[-1][name]
        if name in self.globals:
            return self.globals[name]
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
        if isinstance(node, A.ListLit):
            items = []
            for item in node.items:
                items.append((yield from self.eval(item)))
            return items
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
        if isinstance(node, A.UnOp):
            value = yield from self.eval(node.operand)
            return self.unop(node, value)
        if isinstance(node, A.BinOp):
            return (yield from self.eval_binop(node))
        raise SparkyError("I got confused by this expression.", node.line)

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
            return name
        if name in COLORS:
            return COLORS[name]
        hint = did_you_mean(name, COLORS)
        raise SparkyError(f'I don\'t know the color "{value}".{hint}', line)

    # ---------- lists ----------

    def item_position(self, seq, index, line):
        number = self.as_number(index, line, "item")
        if number != int(number):
            raise SparkyError(f"Item numbers are whole numbers, like 1 or 2 — "
                              f"not {format_value(number)}.", line)
        number = int(number)
        if number < 1:
            raise SparkyError("Items start at 1, so the first one is item 1.", line)
        if number > len(seq):
            what = "letters" if isinstance(seq, str) else "items"
            raise SparkyError(f"There's no item {number} — that only has "
                              f"{len(seq)} {what}.", line)
        return number - 1

    def get_item(self, target, index, line):
        if not isinstance(target, (list, str)):
            raise SparkyError(f'"item ... of" needs a list or text, but got '
                              f"{format_value(target, True)}.", line)
        return target[self.item_position(target, index, line)]

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
        try:
            yield from self.run_block(func.body)
        except ReturnValue as result:
            return result.value
        except BreakLoop:
            pass
        finally:
            self.frames.pop()
        return None

    # ---------- running ----------

    def run(self):
        """The main generator. Drive it with a for-loop; it yields ticks."""
        # every Sparky call level is several Python generator frames deep
        sys.setrecursionlimit(max(sys.getrecursionlimit(), 6000))
        try:
            yield from self.run_block(self.program)
        except HaltProgram:
            pass
        except RecursionError:
            raise SparkyError("Your program went too deep — a command keeps "
                              "calling itself without stopping. Give it a way "
                              "to stop, like: if n < 1 then give back 0", None)

    def run_block(self, body):
        for stmt in body:
            yield from self.execute(stmt)

    def execute(self, stmt):
        kind = type(stmt).__name__
        method = getattr(self, f"exec_{kind}", None)
        if method is None:
            raise SparkyError("I got confused by this command.", stmt.line)
        yield from method(stmt)

    # ---------- statement handlers ----------

    def exec_Say(self, stmt):
        text = format_value((yield from self.eval(stmt.value)))
        self.runtime.say(text)
        self.runtime.bubble(text)
        yield ("visual", stmt.line)

    def exec_Ask(self, stmt):
        prompt = format_value((yield from self.eval(stmt.prompt)))
        answer = self.runtime.ask(prompt)
        if answer is None:
            raise HaltProgram()
        self.set_var(stmt.target, answer)
        yield ("step", stmt.line)

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

    # ---------- sprite / stage handlers ----------


    def move_sprite(self, new_x, new_y):
        if self.pen_down:
            self.runtime.line(self.x, self.y, new_x, new_y,
                              self.pen_color, self.pen_size)
        self.x, self.y = new_x, new_y
        self.runtime.sprite(self.x, self.y, self.heading,
                            self.visible, self.scale)

    def exec_Move(self, stmt):
        distance = self.as_number((yield from self.eval(stmt.distance)), stmt.line, "move")
        radians = math.radians(self.heading)
        dx = math.sin(radians)
        dy = math.cos(radians)
        # chunk long moves into little hops so the sprite glides
        hops = 1 if self.speed >= 10 else max(1, min(30, int(abs(distance) / 8)))
        for _ in range(hops):
            self.move_sprite(self.x + dx * distance / hops,
                             self.y + dy * distance / hops)
            yield ("visual", stmt.line)

    def exec_Turn(self, stmt):
        degrees = self.as_number((yield from self.eval(stmt.degrees)), stmt.line, "turn")
        self.heading = (self.heading + degrees * stmt.direction) % 360
        self.runtime.sprite(self.x, self.y, self.heading, self.visible, self.scale)
        yield ("visual", stmt.line)

    def exec_Point(self, stmt):
        self.heading = self.as_number((yield from self.eval(stmt.heading)),
                                      stmt.line, "point") % 360
        self.runtime.sprite(self.x, self.y, self.heading, self.visible, self.scale)
        yield ("visual", stmt.line)

    def exec_Goto(self, stmt):
        x = self.as_number((yield from self.eval(stmt.x)), stmt.line, "goto")
        y = self.as_number((yield from self.eval(stmt.y)), stmt.line, "goto")
        self.move_sprite(x, y)
        yield ("visual", stmt.line)

    def exec_Home(self, stmt):
        self.move_sprite(0.0, 0.0)
        self.heading = 0.0
        self.runtime.sprite(self.x, self.y, self.heading, self.visible, self.scale)
        yield ("visual", stmt.line)

    def exec_Pen(self, stmt):
        if stmt.mode == "up":
            self.pen_down = False
        elif stmt.mode == "down":
            self.pen_down = True
        elif stmt.mode == "color":
            self.pen_color = self.as_color((yield from self.eval(stmt.value)), stmt.line)
        elif stmt.mode == "size":
            size = self.as_number((yield from self.eval(stmt.value)), stmt.line, "pen size")
            self.pen_size = max(0.5, min(60.0, size))
        yield ("step", stmt.line)

    def exec_Clear(self, stmt):
        self.runtime.clear()
        yield ("visual", stmt.line)

    def exec_HideShow(self, stmt):
        self.visible = stmt.visible
        self.runtime.sprite(self.x, self.y, self.heading, self.visible, self.scale)
        yield ("visual", stmt.line)

    def exec_Stamp(self, stmt):
        self.runtime.stamp(self.x, self.y, self.heading, self.scale)
        yield ("visual", stmt.line)

    def exec_Background(self, stmt):
        self.runtime.background(self.as_color((yield from self.eval(stmt.color)), stmt.line))
        yield ("visual", stmt.line)

    def exec_Speed(self, stmt):
        value = self.as_number((yield from self.eval(stmt.value)), stmt.line, "speed")
        self.speed = max(1, min(10, int(value)))
        yield ("step", stmt.line)

    def exec_WriteText(self, stmt):
        text = format_value((yield from self.eval(stmt.value)))
        self.runtime.write_text(self.x, self.y, text,
                                self.pen_color, self.scale)
        yield ("visual", stmt.line)

    def exec_Beep(self, stmt):
        self.runtime.beep()
        yield ("visual", stmt.line)

    def exec_SpriteSize(self, stmt):
        percent = self.as_number((yield from self.eval(stmt.percent)), stmt.line, "size")
        self.scale = max(0.1, min(10.0, percent / 100.0))
        self.runtime.sprite(self.x, self.y, self.heading, self.visible, self.scale)
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


# ---------- built-in functions: name(inputs) ----------

def _length(it, args, line):
    value = args[0]
    if isinstance(value, (list, str)):
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


BUILTINS = {
    # name: (fewest inputs, most inputs, function)
    "length": (1, 1, _length),
    "upper": (1, 1, lambda it, a, l: it.as_text(a[0], l, "upper").upper()),
    "lower": (1, 1, lambda it, a, l: it.as_text(a[0], l, "lower").lower()),
    "trim": (1, 1, lambda it, a, l: it.as_text(a[0], l, "trim").strip()),
    "text": (1, 1, lambda it, a, l: format_value(a[0])),
    "number": (1, 1, _number),
    "sqrt": (1, 1, _sqrt),
    "power": (2, 2, lambda it, a, l: it.as_number(a[0], l, "power")
              ** it.as_number(a[1], l, "power")),
    "floor": (1, 1, lambda it, a, l: float(math.floor(it.as_number(a[0], l, "floor")))),
    "ceil": (1, 1, lambda it, a, l: float(math.ceil(it.as_number(a[0], l, "ceil")))),
    "sin": (1, 1, _trig(math.sin)),
    "cos": (1, 1, _trig(math.cos)),
    "tan": (1, 1, _trig(math.tan)),
    "min": (1, 99, _minmax(min)),
    "max": (1, 99, _minmax(max)),
    "sum": (1, 1, lambda it, a, l: float(sum(it.as_number(v, l, "sum")
                                             for v in it.as_list(a[0], l, "sum")))),
    "join": (1, 2, _join),
    "split": (1, 2, _split),
    "contains": (2, 2, _contains),
    "pick": (1, 1, _pick),
    "reverse": (1, 1, _reverse),
    "sort": (1, 1, _sort),
    "xpos": (0, 0, lambda it, a, l: it.x),
    "ypos": (0, 0, lambda it, a, l: it.y),
    "direction": (0, 0, lambda it, a, l: it.heading),
}
