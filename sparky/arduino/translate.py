# Sparky for Arduino: turns a Sparky program into an Arduino sketch.
#
#   pin 13 on / pin 13 off / pin 9 to 128     digitalWrite / analogWrite
#   servo 9 to 90                             the Servo library
#   buzzer 8  then  play note 4 for 0.5       tone()
#   read pin A0                               analogRead / digitalRead
#   say ...                                   Serial.println (open the Serial Monitor)
#   wait 1                                    delay(1000)
#
# Everything before the last `forever` runs once (setup); the forever's body
# becomes loop(). Numbers are floats, text is String, true/false are bool.

import re

from ..lang import ast_nodes as A
from ..lang.errors import SparkyError
from ..lang.parser import parse

CPP_WORDS = set("""alignas alignof and asm auto bool break case catch char class const
constexpr continue default delete do double else enum explicit export extern false float for
friend goto if inline int long mutable namespace new noexcept not nullptr operator or private
protected public register return short signed sizeof static struct switch template this throw
true try typedef typeid typename union unsigned using virtual void volatile while xor setup
loop delay tone map min max abs round random byte word boolean String Serial HIGH LOW INPUT
OUTPUT millis micros""".split())

MAJOR_STEPS = (0, 2, 4, 5, 7, 9, 11)
STAGE_ONLY = {
    "Move": "move", "Turn": "turn", "Point": "point", "Goto": "goto", "Home": "home",
    "Pen": "pen", "Clear": "clear", "HideShow": "hide and show", "Stamp": "stamp",
    "Background": "background", "Speed": "speed", "WriteText": "write",
    "SpriteSize": "size", "Shape": "shapes", "Fill": "fill", "Backdrop": "backdrop",
    "MakeSprite": "sprites", "Tell": "tell", "Costume": "costumes", "Ghost": "ghost",
    "Layer": "layer", "Bounce": "bounce", "Glide": "glide", "Think": "think",
    "Speak": "speak", "Ask": "ask", "When": "when blocks", "Broadcast": "broadcast",
    "NextFrame": "next frame", "Use": "use", "Save": "save", "Load": "load",
    "AddTo": "lists", "RemoveFrom": "lists", "SetItem": "lists", "InsertAt": "lists",
    "ForEach": "for each", "SetField": "records", "ChangeField": "records", "Try": "try",
    "WaitUntil": "wait until", "ResetTimer": "reset timer",
}
EXPR_STAGE_ONLY = {"ListLit": "lists", "Index": "lists", "RecordLit": "records",
                   "Field": "records", "KeyDown": "keys", "Mouse": "the mouse",
                   "Touching": "touching", "DistanceTo": "distance to",
                   "RandomColor": "random color", "Template": None}


def note_hz(note):
    octave, degree = divmod(int(note) - 1, 7)
    return round(261.63 * (2 ** ((octave * 12 + MAJOR_STEPS[degree]) / 12)))


def not_on_board(what, line):
    return SparkyError(f'"{what}" works on the stage, not on an Arduino board. On a board '
                       "you can use pin, servo, buzzer, play note, read pin, say, wait, "
                       "repeat, if, set and teach.", line)


class ArduinoTranslator:
    def __init__(self):
        self.pins_out = set()
        self.pins_in = set()
        self.servos = set()
        self.buzzer = None
        self.uses_serial = False
        self.uses_say_helpers = False
        self.uses_math = False
        self.kinds = {}            # variable -> "float" | "String" | "bool"
        self.functions = {}        # name -> Teach node
        self.returns = set()       # functions that give back a value
        self.counter = 0
        self.locals = []           # stack of sets of names local to a function
        self.uses_read_helper = False

    # ---------- names ----------

    @staticmethod
    def name(sparky):
        clean = re.sub(r"\W", "_", sparky)
        if not clean or clean[0].isdigit():
            clean = "v_" + clean
        return clean + "_" if clean in CPP_WORDS else clean

    def pin(self, node):
        if isinstance(node, A.Var) and re.fullmatch(r"a\d+", node.name):
            return node.name.upper()
        if isinstance(node, A.Num):
            return str(int(node.value))
        return f"(int)({self.expr(node)})"

    # ---------- kinds of values ----------

    def kind(self, node):
        if isinstance(node, (A.Str, A.Template)):
            return "String"
        if isinstance(node, A.Bool):
            return "bool"
        if isinstance(node, A.UnOp) and node.op == "not":
            return "bool"
        if isinstance(node, A.BinOp):
            if node.op in ("and", "or", "=", "!=", ">", "<", ">=", "<="):
                return "bool"
            if node.op == "+" and "String" in (self.kind(node.left), self.kind(node.right)):
                return "String"
            return "float"
        if isinstance(node, A.Var):
            return self.kinds.get(node.name, "float")
        if isinstance(node, A.Call) and node.name in ("text", "upper", "lower", "trim"):
            return "String"
        return "float"

    def learn_kinds(self, body):
        for stmt in walk(body):
            if isinstance(stmt, A.SetVar):
                self.kinds.setdefault(stmt.name, self.kind(stmt.value))
            elif isinstance(stmt, (A.ChangeVar, A.ForRange)):
                self.kinds.setdefault(stmt.name, "float")

    # ---------- expressions ----------

    def number(self, value):
        value = float(value)
        if value.is_integer() and abs(value) < 2 ** 31:
            return str(int(value))
        return repr(value)

    def text(self, node):
        """An expression as String (for joining text)."""
        k = self.kind(node)
        if k == "String":
            return self.expr(node) if not isinstance(node, A.Str) else f"String({self.expr(node)})"
        self.uses_say_helpers = True
        cast = "bool" if k == "bool" else "float"
        return f"sparkyText(({cast})({self.expr(node)}))"

    def expr(self, node):
        if isinstance(node, A.Num):
            return self.number(node.value)
        if isinstance(node, A.Str):
            return '"' + node.value.replace("\\", "\\\\").replace('"', '\\"') + '"'
        if isinstance(node, A.Bool):
            return "true" if node.value else "false"
        if isinstance(node, A.Template):
            parts = []
            for part in node.parts:
                parts.append(f"String({self.expr(A.Str(part, node.line))})"
                             if isinstance(part, str) else self.text(part))
            return "(" + " + ".join(parts or ['String("")']) + ")"
        if isinstance(node, A.Var):
            if re.fullmatch(r"a\d+", node.name) and node.name not in self.kinds:
                return node.name.upper()
            if node.name == "timer" and node.name not in self.kinds:
                return "(millis() / 1000.0)"
            if node.name == "pi" and node.name not in self.kinds:
                return "PI"
            return self.name(node.name)
        if isinstance(node, A.ReadPin):
            pin = self.pin(node.pin)
            if pin.startswith("A"):
                return f"analogRead({pin})"
            if pin.isdigit():
                self.pins_in.add(pin)
                return f"digitalRead({pin})"
            self.uses_read_helper = True
            return f"sparkyRead({pin})"
        if isinstance(node, A.Random):
            return f"random({self.expr(node.low)}, {self.expr(node.high)} + 1)"
        if isinstance(node, A.UnOp):
            inner = self.expr(node.operand)
            if node.op == "-":
                return f"(-{inner})"
            if node.op == "not":
                return f"(!{inner})"
            return f"{node.op}({inner})"
        if isinstance(node, A.BinOp):
            op = node.op
            if op == "+" and self.kind(node) == "String":
                return f"({self.text(node.left)} + {self.text(node.right)})"
            left, right = self.expr(node.left), self.expr(node.right)
            if op == "mod":
                return f"fmod({left}, {right})"
            if op == "/":
                return f"((float)({left}) / ({right}))"
            c_op = {"and": "&&", "or": "||", "=": "==", "!=": "!="}.get(op, op)
            return f"({left} {c_op} {right})"
        if isinstance(node, A.Call):
            return self.call(node)
        what = EXPR_STAGE_ONLY.get(type(node).__name__, type(node).__name__)
        raise not_on_board(what, node.line)

    def call(self, node):
        args = [self.expr(a) for a in node.args]
        n = node.name
        if n in self.functions:
            return f"{self.name(n)}({', '.join(args)})"
        simple = {"sqrt": "sqrt", "abs": "fabs", "floor": "floor", "ceil": "ceil",
                  "min": "min", "max": "max", "power": "pow", "round": "round"}
        if n in simple and (n != "round" or len(args) == 1):
            return f"{simple[n]}({', '.join(args)})"
        if n in ("sin", "cos", "tan"):
            return f"{n}(({args[0]}) * DEG_TO_RAD)"
        if n == "clamp":
            return f"constrain({args[0]}, {args[1]}, {args[2]})"
        if n == "text":
            return self.text(node.args[0])
        if n == "length" and node.args and self.kind(node.args[0]) == "String":
            return f"{args[0]}.length()"
        raise SparkyError(f'"{n}" isn\'t something a board can do yet. On a board you can '
                          "use sqrt, abs, min, max, power, round, sin, cos and your own "
                          "commands.", node.line)

    # ---------- statements ----------

    def block(self, body, depth):
        out = []
        for stmt in body:
            out += self.stmt(stmt, depth)
        return out

    def stmt(self, s, d):
        pad = "  " * d
        e = self.expr
        if isinstance(s, A.Say):
            self.uses_serial = True
            self.uses_say_helpers = True
            k = self.kind(s.value)
            value = e(s.value) if k == "String" or isinstance(s.value, A.Str) else \
                f"({'bool' if k == 'bool' else 'float'})({e(s.value)})"
            out = [f"{pad}sparkySay({value});"]
            if s.duration is not None:
                out.append(f"{pad}delay({self.millis(s.duration)});")
            return out
        if isinstance(s, A.Wait):
            return [f"{pad}delay({self.millis(s.seconds)});"]
        if isinstance(s, A.SetVar):
            return [f"{pad}{self.name(s.name)} = {e(s.value)};"]
        if isinstance(s, A.ChangeVar):
            return [f"{pad}{self.name(s.name)} += {e(s.amount)};"]
        if isinstance(s, A.RepeatTimes):
            self.counter += 1
            i = f"i{self.counter}"
            return ([f"{pad}for (long {i} = 0; {i} < (long)({e(s.count)}); {i}++) {{"]
                    + self.block(s.body, d + 1) + [f"{pad}}}"])
        if isinstance(s, A.RepeatUntil):
            return [f"{pad}while (!({e(s.condition)})) {{"] + self.block(s.body, d + 1) + [f"{pad}}}"]
        if isinstance(s, A.RepeatWhile):
            return [f"{pad}while ({e(s.condition)}) {{"] + self.block(s.body, d + 1) + [f"{pad}}}"]
        if isinstance(s, A.Forever):
            return [f"{pad}while (true) {{"] + self.block(s.body, d + 1) + [f"{pad}}}"]
        if isinstance(s, A.ForRange):
            v = self.name(s.name)
            step = e(s.step) if s.step is not None else None
            start, stop = e(s.start), e(s.stop)
            if step is None:
                head = (f"for ({v} = {start}; ({start} <= {stop}) ? {v} <= {stop} : {v} >= {stop}; "
                        f"{v} += ({start} <= {stop}) ? 1 : -1) {{")
            else:
                head = (f"for ({v} = {start}; ({step}) > 0 ? {v} <= {stop} : {v} >= {stop}; "
                        f"{v} += {step}) {{")
            return [pad + head] + self.block(s.body, d + 1) + [f"{pad}}}"]
        if isinstance(s, A.If):
            out = []
            for i, (cond, body) in enumerate(s.branches):
                out.append(f"{pad}{'if' if i == 0 else '} else if'} ({e(cond)}) {{")
                out += self.block(body, d + 1)
            if s.else_body is not None:
                out.append(f"{pad}}} else {{")
                out += self.block(s.else_body, d + 1)
            return out + [f"{pad}}}"]
        if isinstance(s, A.StopLoop):
            return [f"{pad}break;"]
        if isinstance(s, A.StopProgram):
            return [f"{pad}while (true) {{}}  // stop program"]
        if isinstance(s, A.Do):
            return [f"{pad}{self.name(s.name)}({', '.join(e(a) for a in s.args)});"]
        if isinstance(s, A.ExprStatement):
            return [f"{pad}{e(s.expr)};"]
        if isinstance(s, A.Return):
            return [f"{pad}return {e(s.value)};"]
        if isinstance(s, A.Teach):
            return []       # functions go above setup()
        if isinstance(s, A.Pin):
            pin = self.pin(s.pin)
            out = []
            if pin.isdigit() or re.fullmatch(r"A\d+", pin):
                self.pins_out.add(pin)
            else:       # a pin kept in a variable: set it up right here
                out.append(f"{pad}pinMode({pin}, OUTPUT);")
            if s.mode == "to":
                return out + [f"{pad}analogWrite({pin}, constrain((int)({e(s.value)}), 0, 255));"]
            return out + [f"{pad}digitalWrite({pin}, {'HIGH' if s.mode == 'on' else 'LOW'});"]
        if isinstance(s, A.Servo):
            pin = self.pin(s.pin)
            if not pin.isdigit():
                raise SparkyError("Write the servo's pin as a number, like: servo 9 to 90",
                                  s.line)
            self.servos.add(pin)
            return [f"{pad}servo{pin}.write(constrain((int)({e(s.angle)}), 0, 180));"]
        if isinstance(s, A.Buzzer):
            self.buzzer = self.pin(s.pin)
            return [f"{pad}sparkyBuzzer = {self.buzzer};"]
        if isinstance(s, A.PlaySound):
            if self.buzzer is None:
                raise SparkyError("Tell Sparky where the buzzer is first, like: buzzer 8",
                                  s.line)
            if s.kind == "note":
                ms = self.millis(s.duration) if s.duration is not None else "400"
                note = (str(note_hz(s.value.value)) if isinstance(s.value, A.Num)
                        and 1 <= s.value.value <= 14 else f"sparkyNote({e(s.value)})")
                self.uses_math = self.uses_math or note.startswith("sparkyNote")
                return [f"{pad}tone(sparkyBuzzer, {note}, {ms});", f"{pad}delay({ms});"]
            return [f"{pad}tone(sparkyBuzzer, 880, 120);", f"{pad}delay(120);"]
        if isinstance(s, A.Beep):
            if self.buzzer is None:
                raise SparkyError("Tell Sparky where the buzzer is first, like: buzzer 8",
                                  s.line)
            return [f"{pad}tone(sparkyBuzzer, 880, 120);", f"{pad}delay(120);"]
        what = STAGE_ONLY.get(type(s).__name__, type(s).__name__)
        raise not_on_board(what, s.line)

    def millis(self, node):
        if isinstance(node, A.Num):
            return str(int(round(float(node.value) * 1000)))
        return f"(unsigned long)(({self.expr(node)}) * 1000)"

    # ---------- the whole sketch ----------

    def function(self, t):
        gives = t.name in self.returns
        params = ", ".join(f"float {self.name(p)}" for p in t.params)
        head = f"{'float' if gives else 'void'} {self.name(t.name)}({params})"
        saved = dict(self.kinds)
        for p in t.params:
            self.kinds[p] = "float"
        body = self.block(t.body, 1)
        self.kinds = saved
        locals_ = sorted({x.name for x in walk(t.body) if isinstance(x, (A.SetVar, A.ForRange))}
                         - set(self.globals) - set(t.params))
        decl = [f"  {self.kinds.get(n, 'float')} {self.name(n)} = 0;" for n in locals_]
        tail = ["  return 0;"] if gives else []
        return [head + " {"] + decl + body + tail + ["}", ""]

    def sketch(self, program):
        first_buzzer = next((n for n in walk(program) if isinstance(n, A.Buzzer)), None)
        if first_buzzer is not None:
            self.buzzer = self.pin(first_buzzer.pin)
        for node in walk(program):
            if isinstance(node, A.Teach):
                self.functions[node.name] = node
                if any(isinstance(x, A.Return) for x in walk(node.body)):
                    self.returns.add(node.name)
        self.learn_kinds(program)
        top = [s for s in program if not isinstance(s, A.Teach)]
        self.globals = {x.name for x in walk(top) if isinstance(x, (A.SetVar, A.ChangeVar,
                                                                   A.ForRange))}
        # the last forever at the top becomes loop()
        loop_body = []
        if top and isinstance(top[-1], A.Forever):
            loop_body = top[-1].body
            top = top[:-1]
        functions = []
        for t in self.functions.values():
            functions += self.function(t)
        setup = self.block(top, 1)
        loop = self.block(loop_body, 1)

        head = ["// Made with Sparky for Arduino — sparky-code.web.app",
                "// This is the Arduino code for your Sparky program.", ""]
        if self.servos:
            head += ["#include <Servo.h>", ""]
            head += [f"Servo servo{p};" for p in sorted(self.servos)]
            head.append("")
        if self.buzzer is not None or any(isinstance(x, (A.PlaySound, A.Beep))
                                          for x in walk(program)):
            head += [f"int sparkyBuzzer = {self.buzzer or 8};", ""]
        for name in sorted(self.globals):
            kind = self.kinds.get(name, "float")
            start = {"float": "0", "String": '""', "bool": "false"}[kind]
            head.append(f"{kind} {self.name(name)} = {start};")
        if self.globals:
            head.append("")
        if self.uses_say_helpers:
            head += SAY_HELPERS
        if self.uses_math:
            head += NOTE_HELPER
        if self.uses_read_helper:
            head += ["int sparkyRead(int pin) {", "  pinMode(pin, INPUT);",
                     "  return digitalRead(pin);", "}", ""]
        out = head + functions + ["void setup() {"]
        if self.uses_serial:
            out.append("  Serial.begin(9600);")
        out += [f"  pinMode({p}, OUTPUT);" for p in sorted(self.pins_out)]
        out += [f"  pinMode({p}, INPUT);" for p in sorted(self.pins_in - self.pins_out)]
        out += [f"  servo{p}.attach({p});" for p in sorted(self.servos)]
        if any(isinstance(x, A.Random) for x in walk_expr(program)):
            out.append("  randomSeed(analogRead(A0));")
        out += setup + ["}", "", "void loop() {"] + loop + ["}", ""]
        return "\n".join(out)


SAY_HELPERS = [
    "// say: whole numbers print without .00, like in Sparky",
    "String sparkyText(float v) {",
    "  if (v == (long)v) return String((long)v);",
    "  return String(v, 2);",
    "}",
    "String sparkyText(const String &s) { return s; }",
    "String sparkyText(const char *s) { return String(s); }",
    'String sparkyText(bool b) { return b ? "true" : "false"; }',
    "void sparkySay(float v) { Serial.println(sparkyText(v)); }",
    "void sparkySay(const String &s) { Serial.println(s); }",
    "void sparkySay(const char *s) { Serial.println(s); }",
    'void sparkySay(bool b) { Serial.println(b ? "true" : "false"); }',
    "",
]

NOTE_HELPER = [
    "// note 1..14: two do-re-mi octaves from middle C, like Sparky's notes",
    "int sparkyNote(float n) {",
    "  const int steps[7] = {0, 2, 4, 5, 7, 9, 11};",
    "  int k = constrain((int)n, 1, 14) - 1;",
    "  return (int)(261.63 * pow(2.0, ((k / 7) * 12 + steps[k % 7]) / 12.0) + 0.5);",
    "}",
    "",
]


def walk(body):
    for s in body:
        yield s
        for attr in ("body", "else_body", "oops_body"):
            inner = getattr(s, attr, None)
            if isinstance(inner, list):
                yield from walk(inner)
        if isinstance(s, A.If):
            for _, b in s.branches:
                yield from walk(b)


def walk_expr(body):
    """Every expression node in a program (for spotting random etc.)."""
    stack = list(walk(body))
    while stack:
        node = stack.pop()
        yield node
        for value in vars(node).values():
            if isinstance(value, A.Node):
                stack.append(value)
            elif isinstance(value, list):
                stack += [v for v in value if isinstance(v, A.Node)]
                for v in value:
                    if isinstance(v, tuple):
                        stack += [x for x in v if isinstance(x, A.Node)]


def to_arduino(source):
    """Translate a Sparky program into an Arduino sketch (C++)."""
    return ArduinoTranslator().sketch(parse(source))


def is_arduino_program(source):
    """True when a Sparky program is meant for a board (it uses pin, servo, buzzer...)."""
    try:
        program = parse(source)
    except SparkyError:
        return bool(re.search(r"^\s*(pin|servo|buzzer)\s", source, re.M | re.I))
    return any(isinstance(n, (A.Pin, A.Servo, A.Buzzer, A.ReadPin)) for n in walk_expr(program))
