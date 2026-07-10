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
    def __init__(self, value, line):
        super().__init__(line)
        self.value = value


class Ask(Node):
    def __init__(self, prompt, target, line):
        super().__init__(line)
        self.prompt = prompt
        self.target = target


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
    def __init__(self, value, line):
        super().__init__(line)
        self.value = value


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
