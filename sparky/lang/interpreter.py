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

import math
import random

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

MAX_CALL_DEPTH = 200

# built-in sound effects for `play "name"`
SOUND_NAMES = ("pop", "ding", "boing", "laser", "drum", "tada", "jump")


class BreakLoop(Exception):
    pass


class HaltProgram(Exception):
    pass


def format_value(value):
    """How Sparky shows values to kids: 3.0 prints as 3, True as true."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if value == int(value) and abs(value) < 1e15:
            return str(int(value))
        return str(round(value, 6))
    return str(value)


class Interpreter:
    def __init__(self, program, runtime):
        self.program = program
        self.runtime = runtime
        self.globals = {}
        self.frames = []          # parameter scopes for teach/do
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
        hint = did_you_mean(name, known)
        raise SparkyError(f'I don\'t know a variable called "{name}".{hint} '
                          f'You can make it with: set {name} to 0', line)

    def set_var(self, name, value):
        if self.frames and name in self.frames[-1]:
            self.frames[-1][name] = value
        else:
            self.globals[name] = value

    # ---------- expressions ----------

    def evaluate(self, node):
        if isinstance(node, A.Num):
            return node.value
        if isinstance(node, A.Str):
            return node.value
        if isinstance(node, A.Bool):
            return node.value
        if isinstance(node, A.Var):
            return self.get_var(node.name, node.line)
        if isinstance(node, A.Random):
            low = self.as_number(self.evaluate(node.low), node.line, "random")
            high = self.as_number(self.evaluate(node.high), node.line, "random")
            if low > high:
                low, high = high, low
            if low == int(low) and high == int(high):
                return float(random.randint(int(low), int(high)))
            return random.uniform(low, high)
        if isinstance(node, A.UnOp):
            return self.eval_unop(node)
        if isinstance(node, A.BinOp):
            return self.eval_binop(node)
        raise SparkyError("I got confused by this expression.", node.line)

    def eval_unop(self, node):
        value = self.evaluate(node.operand)
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
            return self.truthy(self.evaluate(node.left)) and \
                self.truthy(self.evaluate(node.right))
        if op == "or":
            return self.truthy(self.evaluate(node.left)) or \
                self.truthy(self.evaluate(node.right))

        left = self.evaluate(node.left)
        right = self.evaluate(node.right)

        if op == "+":
            # joining text works with +, like: "Hi " + name
            if isinstance(left, str) or isinstance(right, str):
                return format_value(left) + format_value(right)
            return left + right
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
        if isinstance(left, str) and not isinstance(right, str):
            left = self.try_number(left)
        if isinstance(right, str) and not isinstance(left, str):
            right = self.try_number(right)
        return left == right

    def comparable_pair(self, left, right, line, op):
        if isinstance(left, str):
            left = self.try_number(left)
        if isinstance(right, str):
            right = self.try_number(right)
        both_numbers = isinstance(left, (int, float)) and \
            isinstance(right, (int, float)) and \
            not isinstance(left, bool) and not isinstance(right, bool)
        both_text = isinstance(left, str) and isinstance(right, str)
        if both_numbers or both_text:
            return left, right
        raise SparkyError(f'I can\'t compare {format_value(left)!r} and '
                          f'{format_value(right)!r} with "{op}".', line)

    @staticmethod
    def try_number(text):
        try:
            return float(text)
        except (ValueError, TypeError):
            return text

    def as_number(self, value, line, where):
        if isinstance(value, bool):
            raise SparkyError(f'"{where}" needs a number, but got '
                              f'{format_value(value)}.', line)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                pass
        raise SparkyError(f'"{where}" needs a number, but got the text '
                          f'"{value}".', line)

    @staticmethod
    def truthy(value):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        return len(str(value)) > 0

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

    # ---------- running ----------

    def run(self):
        """The main generator. Drive it with a for-loop; it yields ticks."""
        try:
            yield from self.run_block(self.program)
        except HaltProgram:
            pass

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
        text = format_value(self.evaluate(stmt.value))
        self.runtime.say(text)
        self.runtime.bubble(text)
        yield ("visual", stmt.line)

    def exec_Ask(self, stmt):
        prompt = format_value(self.evaluate(stmt.prompt))
        answer = self.runtime.ask(prompt)
        if answer is None:
            raise HaltProgram()
        self.set_var(stmt.target, answer)
        yield ("step", stmt.line)

    def exec_SetVar(self, stmt):
        self.set_var(stmt.name, self.evaluate(stmt.value))
        yield ("step", stmt.line)

    def exec_ChangeVar(self, stmt):
        current = self.as_number(self.get_var(stmt.name, stmt.line),
                                 stmt.line, "change")
        amount = self.as_number(self.evaluate(stmt.amount), stmt.line, "change")
        self.set_var(stmt.name, current + amount)
        yield ("step", stmt.line)

    def exec_RepeatTimes(self, stmt):
        count = int(self.as_number(self.evaluate(stmt.count), stmt.line, "repeat"))
        try:
            for _ in range(max(0, count)):
                yield from self.run_block(stmt.body)
                yield ("step", stmt.line)
        except BreakLoop:
            pass

    def exec_RepeatUntil(self, stmt):
        try:
            while not self.truthy(self.evaluate(stmt.condition)):
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

    def exec_If(self, stmt):
        for condition, body in stmt.branches:
            if self.truthy(self.evaluate(condition)):
                yield from self.run_block(body)
                return
        if stmt.else_body is not None:
            yield from self.run_block(stmt.else_body)

    def exec_Wait(self, stmt):
        seconds = self.as_number(self.evaluate(stmt.seconds), stmt.line, "wait")
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
        if len(stmt.args) != len(func.params):
            need = ", ".join(func.params) if func.params else "no inputs"
            raise SparkyError(f'"{stmt.name}" needs {len(func.params)} '
                              f"input(s) ({need}) but you gave "
                              f"{len(stmt.args)}.", stmt.line)
        if len(self.frames) >= MAX_CALL_DEPTH:
            raise SparkyError(f'"{stmt.name}" called itself too many times '
                              "and got dizzy!", stmt.line)
        frame = {param: self.evaluate(arg)
                 for param, arg in zip(func.params, stmt.args)}
        self.frames.append(frame)
        try:
            yield from self.run_block(func.body)
        except BreakLoop:
            pass
        finally:
            self.frames.pop()

    # ---------- sprite / stage handlers ----------

    def move_sprite(self, new_x, new_y):
        if self.pen_down:
            self.runtime.line(self.x, self.y, new_x, new_y,
                              self.pen_color, self.pen_size)
        self.x, self.y = new_x, new_y
        self.runtime.sprite(self.x, self.y, self.heading,
                            self.visible, self.scale)

    def exec_Move(self, stmt):
        distance = self.as_number(self.evaluate(stmt.distance), stmt.line, "move")
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
        degrees = self.as_number(self.evaluate(stmt.degrees), stmt.line, "turn")
        self.heading = (self.heading + degrees * stmt.direction) % 360
        self.runtime.sprite(self.x, self.y, self.heading, self.visible, self.scale)
        yield ("visual", stmt.line)

    def exec_Point(self, stmt):
        self.heading = self.as_number(self.evaluate(stmt.heading),
                                      stmt.line, "point") % 360
        self.runtime.sprite(self.x, self.y, self.heading, self.visible, self.scale)
        yield ("visual", stmt.line)

    def exec_Goto(self, stmt):
        x = self.as_number(self.evaluate(stmt.x), stmt.line, "goto")
        y = self.as_number(self.evaluate(stmt.y), stmt.line, "goto")
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
            self.pen_color = self.as_color(self.evaluate(stmt.value), stmt.line)
        elif stmt.mode == "size":
            size = self.as_number(self.evaluate(stmt.value), stmt.line, "pen size")
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
        self.runtime.background(self.as_color(self.evaluate(stmt.color), stmt.line))
        yield ("visual", stmt.line)

    def exec_Speed(self, stmt):
        value = self.as_number(self.evaluate(stmt.value), stmt.line, "speed")
        self.speed = max(1, min(10, int(value)))
        yield ("step", stmt.line)

    def exec_WriteText(self, stmt):
        text = format_value(self.evaluate(stmt.value))
        self.runtime.write_text(self.x, self.y, text,
                                self.pen_color, self.scale)
        yield ("visual", stmt.line)

    def exec_Beep(self, stmt):
        self.runtime.beep()
        yield ("visual", stmt.line)

    def exec_SpriteSize(self, stmt):
        percent = self.as_number(self.evaluate(stmt.percent), stmt.line, "size")
        self.scale = max(0.1, min(10.0, percent / 100.0))
        self.runtime.sprite(self.x, self.y, self.heading, self.visible, self.scale)
        yield ("visual", stmt.line)

    def exec_PlaySound(self, stmt):
        if stmt.kind == "name":
            name = self.evaluate(stmt.value)
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
        note = self.as_number(self.evaluate(stmt.value), stmt.line, "play note")
        note = int(note)
        if not 1 <= note <= 14:
            raise SparkyError("Notes go from 1 (low do) to 14 (high do, "
                              "one octave up from 8).", stmt.line)
        duration = 0.4
        if stmt.duration is not None:
            duration = self.as_number(self.evaluate(stmt.duration),
                                      stmt.line, "play note ... for")
        duration = max(0.05, min(4.0, duration))
        self.runtime.play_sound("", note, duration)
        # the note plays while the program waits, so melodies line up
        yield ("wait", duration, stmt.line)
