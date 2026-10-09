# Sparky AST: tiny classes describing each thing a program can do.
# The parser builds these; the interpreter walks them.


class Node:
    def __init__(self, line):
        self.line = line


# ---------- expressions ----------

class Num(Node):
    def __init__(self, value, line):
        super().__init__(line)
        self.value = value


class Str(Node):
    def __init__(self, value, line):
        super().__init__(line)
        self.value = value


class Bool(Node):
    def __init__(self, value, line):
        super().__init__(line)
        self.value = value


class Var(Node):
    def __init__(self, name, line):
        super().__init__(line)
        self.name = name


class BinOp(Node):
    def __init__(self, op, left, right, line):
        super().__init__(line)
        self.op = op
        self.left = left
        self.right = right


class UnOp(Node):
    # op is "-", "not", "round", or "abs"
    def __init__(self, op, operand, line):
        super().__init__(line)
        self.op = op
        self.operand = operand


class Random(Node):
    # random LOW to HIGH
    def __init__(self, low, high, line):
        super().__init__(line)
        self.low = low
        self.high = high


# ---------- statements ----------

class Say(Node):
    # say VALUE (for SECONDS)
    def __init__(self, value, line, duration=None):
        super().__init__(line)
        self.value = value
        self.duration = duration


class Ask(Node):
    # mode is "text" or "number"; choices is an expression giving a list, or None
    def __init__(self, prompt, target, line, mode="text", choices=None):
        super().__init__(line)
        self.prompt = prompt
        self.target = target
        self.mode = mode
        self.choices = choices


class SetVar(Node):
    def __init__(self, name, value, line):
        super().__init__(line)
        self.name = name
        self.value = value


class ChangeVar(Node):
    def __init__(self, name, amount, line):
        super().__init__(line)
        self.name = name
        self.amount = amount


class RepeatTimes(Node):
    def __init__(self, count, body, line):
        super().__init__(line)
        self.count = count
        self.body = body


class RepeatUntil(Node):
    def __init__(self, condition, body, line):
        super().__init__(line)
        self.condition = condition
        self.body = body


class Forever(Node):
    def __init__(self, body, line):
        super().__init__(line)
        self.body = body


class If(Node):
    # branches: list of (condition, body); else_body may be None
    def __init__(self, branches, else_body, line):
        super().__init__(line)
        self.branches = branches
        self.else_body = else_body


class Wait(Node):
    def __init__(self, seconds, line):
        super().__init__(line)
        self.seconds = seconds


class StopLoop(Node):
    pass


class StopProgram(Node):
    pass


class Teach(Node):
    def __init__(self, name, params, body, line):
        super().__init__(line)
        self.name = name
        self.params = params
        self.body = body


class Do(Node):
    def __init__(self, name, args, line):
        super().__init__(line)
        self.name = name
        self.args = args


# ---------- sprite / stage statements ----------

class Move(Node):
    def __init__(self, distance, line):
        super().__init__(line)
        self.distance = distance


class Turn(Node):
    # direction is +1 (right) or -1 (left)
    def __init__(self, degrees, direction, line):
        super().__init__(line)
        self.degrees = degrees
        self.direction = direction


class Point(Node):
    def __init__(self, heading, line):
        super().__init__(line)
        self.heading = heading


class Goto(Node):
    def __init__(self, x, y, line):
        super().__init__(line)
        self.x = x
        self.y = y


class Home(Node):
    pass


class Pen(Node):
    # mode: "up", "down", "color", "size"
    def __init__(self, mode, value, line):
        super().__init__(line)
        self.mode = mode
        self.value = value


class Clear(Node):
    pass


class HideShow(Node):
    def __init__(self, visible, line):
        super().__init__(line)
        self.visible = visible


class Stamp(Node):
    pass


class Background(Node):
    def __init__(self, color, line):
        super().__init__(line)
        self.color = color


class Speed(Node):
    def __init__(self, value, line):
        super().__init__(line)
        self.value = value


class WriteText(Node):
    # style: {"size": node, "bold": bool, "italic": bool}
    def __init__(self, value, line, style=None):
        super().__init__(line)
        self.value = value
        self.style = style or {}


class Beep(Node):
    pass


class SpriteSize(Node):
    def __init__(self, percent, line):
        super().__init__(line)
        self.percent = percent


class PlaySound(Node):
    # kind is "name" (play "pop") or "note" (play note 3 for 0.5)
    def __init__(self, kind, value, duration, line):
        super().__init__(line)
        self.kind = kind
        self.value = value
        self.duration = duration


# ---------- Sparky 2.0: lists, functions with results, for loops ----------

class Nothing(Node):
    """The value `nothing` (what a function gives back when it gives nothing)."""


class ListLit(Node):
    def __init__(self, items, line):
        super().__init__(line)
        self.items = items


class Index(Node):
    # item INDEX of TARGET   (items count from 1)
    def __init__(self, target, index, line):
        super().__init__(line)
        self.target = target
        self.index = index


class Call(Node):
    # name(arg, arg) — a built-in function or one you taught
    def __init__(self, name, args, line):
        super().__init__(line)
        self.name = name
        self.args = args


class ExprStatement(Node):
    def __init__(self, expr, line):
        super().__init__(line)
        self.expr = expr


class Return(Node):
    def __init__(self, value, line):
        super().__init__(line)
        self.value = value


class ForEach(Node):
    def __init__(self, name, iterable, body, line):
        super().__init__(line)
        self.name = name
        self.iterable = iterable
        self.body = body


class ForRange(Node):
    def __init__(self, name, start, stop, step, body, line):
        super().__init__(line)
        self.name = name
        self.start = start
        self.stop = stop
        self.step = step
        self.body = body


class AddTo(Node):
    # add VALUE to NAME — appends to a list, adds to a number, joins text
    def __init__(self, value, name, line):
        super().__init__(line)
        self.value = value
        self.name = name


class RemoveFrom(Node):
    def __init__(self, value, name, line):
        super().__init__(line)
        self.value = value
        self.name = name


class SetItem(Node):
    # set item INDEX of NAME to VALUE
    def __init__(self, name, index, value, line):
        super().__init__(line)
        self.name = name
        self.index = index
        self.value = value


# ---------- Sparky 3.0 ----------

class Template(Node):
    # "Hi {name}!" — parts are plain text or expression nodes
    def __init__(self, parts, line):
        super().__init__(line)
        self.parts = parts


class RecordLit(Node):
    # {name: "Rex", age: 3} — pairs of (field name, expression)
    def __init__(self, pairs, line):
        super().__init__(line)
        self.pairs = pairs


class Field(Node):
    # FIELD of TARGET
    def __init__(self, name, target, line):
        super().__init__(line)
        self.name = name
        self.target = target


class SetField(Node):
    # set FIELD of TARGET to VALUE
    def __init__(self, name, target, value, line):
        super().__init__(line)
        self.name = name
        self.target = target
        self.value = value


class ChangeField(Node):
    # change FIELD of TARGET by AMOUNT
    def __init__(self, name, target, amount, line):
        super().__init__(line)
        self.name = name
        self.target = target
        self.amount = amount


class RepeatWhile(Node):
    def __init__(self, condition, body, line):
        super().__init__(line)
        self.condition = condition
        self.body = body


class WaitUntil(Node):
    def __init__(self, condition, line):
        super().__init__(line)
        self.condition = condition


class InsertAt(Node):
    # insert VALUE at INDEX in NAME
    def __init__(self, value, index, name, line):
        super().__init__(line)
        self.value = value
        self.index = index
        self.name = name


class ResetTimer(Node):
    pass


class Use(Node):
    # use "shapes.spark"
    def __init__(self, path, line):
        super().__init__(line)
        self.path = path


class Try(Node):
    def __init__(self, body, oops_body, line):
        super().__init__(line)
        self.body = body
        self.oops_body = oops_body


class Think(Node):
    def __init__(self, value, line, duration=None):
        super().__init__(line)
        self.value = value
        self.duration = duration


class Speak(Node):
    def __init__(self, value, line):
        super().__init__(line)
        self.value = value


class When(Node):
    # kind: "key" (value = key name), "message" (value = message),
    # "clicked" (sprite = name), "stage"
    def __init__(self, kind, value, sprite, body, line):
        super().__init__(line)
        self.kind = kind
        self.value = value
        self.sprite = sprite
        self.body = body


class Broadcast(Node):
    def __init__(self, message, wait, line):
        super().__init__(line)
        self.message = message
        self.wait = wait


class KeyDown(Node):
    # key "left" down   (an expression)
    def __init__(self, key, line):
        super().__init__(line)
        self.key = key


class Mouse(Node):
    # mouse x / mouse y / mouse down
    def __init__(self, what, line):
        super().__init__(line)
        self.what = what


class NextFrame(Node):
    pass


class MakeSprite(Node):
    def __init__(self, name, costume, line):
        super().__init__(line)
        self.name = name
        self.costume = costume


class Tell(Node):
    def __init__(self, name, body, line):
        super().__init__(line)
        self.name = name
        self.body = body


class Costume(Node):
    # costume VALUE, or "next costume" (value None)
    def __init__(self, value, line):
        super().__init__(line)
        self.value = value


class Ghost(Node):
    def __init__(self, value, line):
        super().__init__(line)
        self.value = value


class Layer(Node):
    # where: "front" or "back"
    def __init__(self, where, line):
        super().__init__(line)
        self.where = where


class Touching(Node):
    # touching NAME / touching edge / touching mouse   (an expression)
    def __init__(self, what, line):
        super().__init__(line)
        self.what = what


class DistanceTo(Node):
    # distance to NAME   (an expression)
    def __init__(self, what, line):
        super().__init__(line)
        self.what = what


class Bounce(Node):
    pass


class Glide(Node):
    def __init__(self, x, y, seconds, line):
        super().__init__(line)
        self.x = x
        self.y = y
        self.seconds = seconds


class Shape(Node):
    # kind: circle, rectangle, polygon, star, dot, arc — args are expressions
    def __init__(self, kind, args, line):
        super().__init__(line)
        self.kind = kind
        self.args = args


class Fill(Node):
    # fill color VALUE, or "no fill" (value None)
    def __init__(self, value, line):
        super().__init__(line)
        self.value = value


class RandomColor(Node):
    pass


class Backdrop(Node):
    def __init__(self, value, line):
        super().__init__(line)
        self.value = value


class Save(Node):
    # save VALUE as NAME
    def __init__(self, value, name, line):
        super().__init__(line)
        self.value = value
        self.name = name


class Load(Node):
    # load NAME into TARGET
    def __init__(self, name, target, line):
        super().__init__(line)
        self.name = name
        self.target = target


# ---------- Sparky for Arduino ----------

class Pin(Node):
    # pin 13 on / pin 13 off / pin 9 to 128
    def __init__(self, pin, mode, value, line):
        super().__init__(line)
        self.pin = pin
        self.mode = mode
        self.value = value


class Servo(Node):
    # servo 9 to 90
    def __init__(self, pin, angle, line):
        super().__init__(line)
        self.pin = pin
        self.angle = angle


class Buzzer(Node):
    # buzzer 8   (where play note and beep go on a board)
    def __init__(self, pin, line):
        super().__init__(line)
        self.pin = pin


class ReadPin(Node):
    # read pin A0   (an expression)
    def __init__(self, pin, line):
        super().__init__(line)
        self.pin = pin
