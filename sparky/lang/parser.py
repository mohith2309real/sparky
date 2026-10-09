# Sparky parser: turns tokens into an AST.
# The grammar reads like English on purpose:
#
#   say "hello"
#   ask "name?" into name
#   set score to 0
#   change score by 1
#   repeat 10 times ... end
#   repeat until score > 5 ... end
#   forever ... end
#   if x > 3 then ... else if ... then ... else ... end
#   teach square size ... end
#   do square 50
#   move 100 / turn 90 / pen down / goto 0 0 ...
#
# Sparky 2.0 adds lists, functions that give back results, and for loops:
#   set pets to ["cat", "dog"]         add "fish" to pets
#   say item 1 of pets                 remove "cat" from pets
#   for each pet in pets ... end       for i from 1 to 10 ... end
#   teach double n / give back n * 2 / end    say double(21)
#   say length(pets)   upper(name)   sqrt(16)   pick(pets) ...
#
# Sparky 3.0 adds:
#   say "Hi {name}!"                   set pet to {name: "Rex", age: 3}
#   say name of pet                    set age of pet to 4
#   repeat while x < 10 ... end        wait until score > 5
#   ask number "Age?" into age         ask "Pick" choices ["a", "b"] into c
#   try ... oops ... end               use "shapes.spark"
#   when key "space" pressed ... end   when clicked / when stage clicked
#   broadcast "go" (and wait)          when message "go" ... end
#   make sprite rocket with costume "🚀"   tell rocket ... end
#   circle 50  rectangle 80 by 40  polygon 6 sides 40  star 5 points 40
#   fill color "yellow"  no fill  pen style dashed  pen color rainbow
#   glide to 100 50 in 2 seconds   bounce if on edge   next frame
#   save score as "best"   load "best" into best   speak "Hello"
# and Sparky for Arduino (see sparky/arduino/translate.py):
#   pin 13 on   pin 13 off   pin 9 to 128   servo 9 to 90   buzzer 8   read pin A0

from . import ast_nodes as A
from .errors import SparkyError, attach_example, did_you_mean
from .tokenizer import tokenize, NUMBER, STRING, WORD, OP, NEWLINE, EOF

# every word that starts a statement (used for error suggestions too)
STATEMENT_WORDS = [
    "say", "ask", "set", "change", "repeat", "forever", "if", "wait", "stop",
    "teach", "do", "move", "back", "turn", "point", "goto", "home", "pen",
    "clear", "hide", "show", "stamp", "background", "speed", "write", "beep",
    "size", "play", "for", "add", "remove", "give", "return", "end", "else",
]

# Sparky 3.0 statements. They are NOT reserved, so programs that used these
# words as variable names (timer, circle, fill...) keep working.
NEW_STATEMENT_WORDS = [
    "insert", "reset", "use", "try", "oops", "think", "speak", "when", "broadcast",
    "next", "make", "tell", "costume", "ghost", "layer", "bounce", "glide",
    "circle", "rectangle", "polygon", "star", "dot", "arc", "fill", "no",
    "backdrop", "save", "load", "pin", "servo", "buzzer",
]

# words that may appear inside statements/expressions
HELPER_WORDS = [
    "to", "into", "by", "times", "until", "then", "with", "and", "or", "not",
    "is", "true", "false", "left", "right", "up", "down", "color", "loop",
    "program", "seconds", "second", "random", "round", "abs", "note",
    "each", "in", "from", "item", "of", "nothing",
]

ALL_WORDS = STATEMENT_WORDS + HELPER_WORDS

# words that can never be a variable name
RESERVED = set(ALL_WORDS) - {"color", "left", "right", "up", "down"}

# reserved words that still work as values: "say second", "say size"
VALUE_WORDS = {"second", "size"}

SHAPES = ("circle", "rectangle", "polygon", "star", "dot", "arc")


class Parser:
    def __init__(self, source):
        self.tokens = tokenize(source)
        self.pos = 0
        self.depth = 0          # how many blocks deep we are (when-blocks go at the top)

    # ---------- token helpers ----------

    def peek(self, ahead=0):
        return self.tokens[min(self.pos + ahead, len(self.tokens) - 1)]

    def next(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def at_word(self, *words):
        tok = self.peek()
        return tok.kind == WORD and tok.value in words

    def at_op(self, *ops):
        tok = self.peek()
        return tok.kind == OP and tok.value in ops

    def accept_word(self, *words):
        if self.at_word(*words):
            return self.next()
        return None

    def expect_word(self, word, hint):
        tok = self.next()
        if tok.kind != WORD or tok.value != word:
            got = repr(tok.value) if tok.kind != NEWLINE else "the end of the line"
            raise SparkyError(f'I expected the word "{word}" here ({hint}), '
                              f"but found {got}.", tok.line)
        return tok

    def expect_newline(self):
        tok = self.next()
        if tok.kind == EOF:
            return tok
        if tok.kind != NEWLINE:
            raise SparkyError(f'I expected this line to end, but found "{tok.value}". '
                              "Each command goes on its own line.", tok.line)
        return tok

    def skip_newlines(self):
        while self.peek().kind == NEWLINE:
            self.next()

    def expect_name(self, what):
        tok = self.next()
        if tok.kind != WORD:
            raise SparkyError(f"I expected a name for {what} here.", tok.line)
        if tok.value in RESERVED:
            raise SparkyError(f'"{tok.value}" is a Sparky word, so it can\'t be '
                              f"a name for {what}. Try another name.", tok.line)
        return tok.value

    def glued_call_next(self):
        """True when the token after this one is a ( glued to it: name(...)."""
        after = self.peek(1)
        return after.kind == OP and after.value == "(" and after.glued

    def seconds_word(self):
        self.accept_word("seconds") or self.accept_word("second")

    # ---------- program & blocks ----------

    def parse_program(self):
        body = []
        self.skip_newlines()
        while self.peek().kind != EOF:
            body.append(self.parse_statement())
            self.skip_newlines()
        return body

    def parse_block(self, opener, opener_line, stops=("end", "else")):
        """Parse statements until one of the stop words ('end', 'else'...)."""
        body = []
        self.depth += 1
        self.skip_newlines()
        try:
            while True:
                tok = self.peek()
                if tok.kind == EOF:
                    raise SparkyError(f'Your "{opener}" on line {opener_line} never '
                                      'found its "end". Add "end" to close it.',
                                      opener_line, example=None)
                if self.at_word(*stops):
                    return body
                body.append(self.parse_statement())
                self.skip_newlines()
        finally:
            self.depth -= 1

    def close_block(self, what):
        self.expect_word("end", f"to close the {what}")
        self.expect_newline()

    # ---------- statements ----------

    def parse_statement(self):
        tok = self.peek()
        if tok.kind != WORD:
            raise SparkyError(f'I expected a command here, but found "{tok.value}". '
                              'Commands are words like say, move, or repeat.', tok.line)

        word = tok.value
        method = getattr(self, f"stmt_{word}", None)
        if self.glued_call_next() and (method is None or word not in RESERVED):
            # a bare function call on its own line, like: greet("Sam")
            expr = self.parse_expression()
            self.expect_newline()
            return A.ExprStatement(expr, tok.line)
        if method is None:
            if word in HELPER_WORDS:
                raise SparkyError(f'"{word}" can\'t start a line by itself.', tok.line)
            hint = did_you_mean(word, STATEMENT_WORDS + NEW_STATEMENT_WORDS)
            raise SparkyError(f'I don\'t know the command "{word}".{hint}', tok.line)
        return method()

    def stmt_end(self):
        tok = self.peek()
        raise SparkyError('This "end" has nothing to close. Every "end" needs a '
                          "repeat, forever, for, if, try, when or teach above it.", tok.line)

    def stmt_else(self):
        tok = self.peek()
        raise SparkyError('"else" only works inside an "if ... end" block.', tok.line)

    def stmt_oops(self):
        tok = self.peek()
        raise SparkyError('"oops" only works inside a "try ... end" block.', tok.line)

    def stmt_say(self):
        tok = self.next()
        value = self.parse_expression()
        duration = None
        if self.accept_word("for"):
            duration = self.parse_expression()
            self.seconds_word()
        self.expect_newline()
        return A.Say(value, tok.line, duration)

    def stmt_think(self):
        tok = self.next()
        value = self.parse_expression()
        duration = None
        if self.accept_word("for"):
            duration = self.parse_expression()
            self.seconds_word()
        self.expect_newline()
        return A.Think(value, tok.line, duration)

    def stmt_speak(self):
        tok = self.next()
        value = self.parse_expression()
        self.expect_newline()
        return A.Speak(value, tok.line)

    def stmt_ask(self):
        tok = self.next()
        mode = "text"
        if self.at_word("number") and not self.glued_call_next():
            self.next()
            mode = "number"
        prompt = self.parse_expression()
        choices = None
        if self.accept_word("choices"):
            choices = self.parse_expression()
        self.expect_word("into", 'like: ask "What\'s your name?" into name')
        target = self.expect_name("your answer")
        self.expect_newline()
        return A.Ask(prompt, target, tok.line, mode=mode, choices=choices)

    def at_field(self):
        """FIELD of ...  (a word followed by "of")"""
        return self.peek().kind == WORD and self.peek(1).kind == WORD and self.peek(1).value == "of"

    def stmt_set(self):
        tok = self.next()
        if self.accept_word("item"):
            index = self.parse_factor()
            self.expect_word("of", "like: set item 1 of pets to \"cat\"")
            name = self.expect_name("a list")
            self.expect_word("to", "like: set item 1 of pets to \"cat\"")
            value = self.parse_expression()
            self.expect_newline()
            return A.SetItem(name, index, value, tok.line)
        if self.at_field():
            field = self.next().value
            self.next()   # of
            target = self.parse_factor()
            self.expect_word("to", "like: set age of pet to 4")
            value = self.parse_expression()
            self.expect_newline()
            return A.SetField(field, target, value, tok.line)
        name = self.expect_name("a variable")
        self.expect_word("to", "like: set score to 0")
        value = self.parse_expression()
        self.expect_newline()
        return A.SetVar(name, value, tok.line)

    def stmt_change(self):
        tok = self.next()
        if self.at_field():
            field = self.next().value
            self.next()   # of
            target = self.parse_factor()
            self.expect_word("by", "like: change age of pet by 1")
            amount = self.parse_expression()
            self.expect_newline()
            return A.ChangeField(field, target, amount, tok.line)
        name = self.expect_name("a variable")
        self.expect_word("by", "like: change score by 1")
        amount = self.parse_expression()
        self.expect_newline()
        return A.ChangeVar(name, amount, tok.line)

    def stmt_repeat(self):
        tok = self.next()
        if self.accept_word("until"):
            condition = self.parse_expression()
            self.expect_newline()
            body = self.parse_block("repeat until", tok.line)
            self.close_block("repeat")
            return A.RepeatUntil(condition, body, tok.line)
        if self.accept_word("while"):
            condition = self.parse_expression()
            self.expect_newline()
            body = self.parse_block("repeat while", tok.line)
            self.close_block("repeat")
            return A.RepeatWhile(condition, body, tok.line)
        count = self.parse_expression()
        self.expect_word("times", "like: repeat 10 times")
        self.expect_newline()
        body = self.parse_block("repeat", tok.line)
        self.close_block("repeat")
        return A.RepeatTimes(count, body, tok.line)

    def stmt_forever(self):
        tok = self.next()
        self.expect_newline()
        body = self.parse_block("forever", tok.line)
        self.close_block("forever")
        return A.Forever(body, tok.line)

    def stmt_if(self):
        tok = self.next()
        branches = []
        condition = self.parse_expression()
        self.expect_word("then", "like: if score > 5 then")
        self.expect_newline()
        body = self.parse_block("if", tok.line)
        branches.append((condition, body))
        else_body = None
        while self.at_word("else"):
            else_tok = self.next()
            if self.accept_word("if"):
                condition = self.parse_expression()
                self.expect_word("then", "like: else if score > 5 then")
                self.expect_newline()
                body = self.parse_block("else if", else_tok.line)
                branches.append((condition, body))
            else:
                self.expect_newline()
                else_body = self.parse_block("else", else_tok.line)
                break
        self.close_block("if")
        return A.If(branches, else_body, tok.line)

    def stmt_wait(self):
        tok = self.next()
        if self.accept_word("until"):
            condition = self.parse_expression()
            self.expect_newline()
            return A.WaitUntil(condition, tok.line)
        seconds = self.parse_expression()
        self.seconds_word()
        self.expect_newline()
        return A.Wait(seconds, tok.line)

    def stmt_stop(self):
        tok = self.next()
        if self.accept_word("loop"):
            self.expect_newline()
            return A.StopLoop(tok.line)
        self.accept_word("program")
        self.expect_newline()
        return A.StopProgram(tok.line)

    def stmt_teach(self):
        tok = self.next()
        name = self.expect_name("your new command")
        params = []
        while self.peek().kind == WORD:
            params.append(self.expect_name("an input"))
        self.expect_newline()
        body = self.parse_block("teach", tok.line)
        self.close_block("teach")
        return A.Teach(name, params, body, tok.line)

    def stmt_for(self):
        tok = self.next()
        if self.accept_word("each"):
            name = self.expect_name("each item")
            self.expect_word("in", "like: for each pet in pets")
            iterable = self.parse_expression()
            self.expect_newline()
            body = self.parse_block("for each", tok.line)
            self.close_block("for")
            return A.ForEach(name, iterable, body, tok.line)
        name = self.expect_name("the counter")
        self.expect_word("from", "like: for i from 1 to 10")
        start = self.parse_expression()
        self.expect_word("to", "like: for i from 1 to 10")
        stop = self.parse_expression()
        step = None
        if self.accept_word("by"):
            step = self.parse_expression()
        self.expect_newline()
        body = self.parse_block("for", tok.line)
        self.close_block("for")
        return A.ForRange(name, start, stop, step, body, tok.line)

    def stmt_add(self):
        tok = self.next()
        value = self.parse_expression()
        self.expect_word("to", 'like: add "fish" to pets')
        name = self.expect_name("a list or variable")
        self.expect_newline()
        return A.AddTo(value, name, tok.line)

    def stmt_remove(self):
        tok = self.next()
        value = self.parse_expression()
        self.expect_word("from", 'like: remove "cat" from pets')
        name = self.expect_name("a list")
        self.expect_newline()
        return A.RemoveFrom(value, name, tok.line)

    def stmt_insert(self):
        tok = self.next()
        value = self.parse_expression()
        self.expect_word("at", 'like: insert "fish" at 2 in pets')
        index = self.parse_expression()
        self.expect_word("in", 'like: insert "fish" at 2 in pets')
        name = self.expect_name("a list")
        self.expect_newline()
        return A.InsertAt(value, index, name, tok.line)

    def stmt_give(self):
        tok = self.next()
        self.expect_word("back", "like: give back answer")
        value = self.parse_expression()
        self.expect_newline()
        return A.Return(value, tok.line)

    def stmt_return(self):
        tok = self.next()
        value = self.parse_expression()
        self.expect_newline()
        return A.Return(value, tok.line)

    def stmt_do(self):
        tok = self.next()
        name = self.expect_name("the command to do")
        args = []
        while self.peek().kind not in (NEWLINE, EOF):
            args.append(self.parse_expression())
            self.accept_word("and")  # optional: do greet with-style "and" separators
            if self.at_op(","):
                self.next()
        self.expect_newline()
        return A.Do(name, args, tok.line)

    def stmt_reset(self):
        tok = self.next()
        self.expect_word("timer", "like: reset timer")
        self.expect_newline()
        return A.ResetTimer(tok.line)

    def stmt_use(self):
        tok = self.next()
        path = self.parse_expression()
        self.expect_newline()
        return A.Use(path, tok.line)

    def stmt_try(self):
        tok = self.next()
        self.expect_newline()
        body = self.parse_block("try", tok.line, stops=("end", "oops"))
        oops_body = []
        if self.accept_word("oops"):
            self.expect_newline()
            oops_body = self.parse_block("oops", tok.line, stops=("end",))
        self.close_block("try")
        return A.Try(body, oops_body, tok.line)

    # ---------- events ----------

    def stmt_when(self):
        tok = self.next()
        if self.depth:
            raise SparkyError('"when" blocks go at the top of your program, not inside '
                              "another block.", tok.line)
        sprite = "sparky"
        value = None
        if self.accept_word("key"):
            kind = "key"
            value = self.parse_sum()
            self.accept_word("pressed")
        elif self.accept_word("message"):
            kind = "message"
            value = self.parse_sum()
        elif self.accept_word("clicked"):
            kind = "clicked"
        elif self.accept_word("stage"):
            self.expect_word("clicked", "like: when stage clicked")
            kind = "stage"
        else:
            name = self.next()
            if name.kind != WORD:
                raise SparkyError('After "when" I expected key, message, clicked or a '
                                  'sprite name — like: when key "space" pressed', tok.line)
            self.expect_word("clicked", "like: when rocket clicked")
            kind, sprite = "clicked", name.value
        self.expect_newline()
        body = self.parse_block("when", tok.line)
        self.close_block("when")
        return A.When(kind, value, sprite, body, tok.line)

    def stmt_broadcast(self):
        tok = self.next()
        message = self.parse_sum()
        wait = False
        if self.accept_word("and"):
            self.expect_word("wait", 'like: broadcast "go" and wait')
            wait = True
        self.expect_newline()
        return A.Broadcast(message, wait, tok.line)

    def stmt_next(self):
        tok = self.next()
        if self.accept_word("frame"):
            self.expect_newline()
            return A.NextFrame(tok.line)
        if self.accept_word("costume"):
            self.expect_newline()
            return A.Costume(None, tok.line)
        raise SparkyError('After "next" I expected frame or costume — like: next frame',
                          tok.line)

    # ---------- sprites ----------

    def stmt_make(self):
        tok = self.next()
        self.expect_word("sprite", 'like: make sprite rocket with costume "🚀"')
        name = self.expect_name("your sprite")
        costume = None
        if self.accept_word("with"):
            self.accept_word("costume")
            costume = self.parse_expression()
        self.expect_newline()
        return A.MakeSprite(name, costume, tok.line)

    def stmt_tell(self):
        tok = self.next()
        name = self.next()
        if name.kind != WORD:
            raise SparkyError("I expected a sprite name here — like: tell rocket", tok.line)
        self.expect_newline()
        body = self.parse_block("tell", tok.line)
        self.close_block("tell")
        return A.Tell(name.value, body, tok.line)

    def stmt_costume(self):
        tok = self.next()
        value = self.parse_expression()
        self.expect_newline()
        return A.Costume(value, tok.line)

    def stmt_ghost(self):
        tok = self.next()
        value = self.parse_expression()
        self.expect_newline()
        return A.Ghost(value, tok.line)

    def stmt_layer(self):
        tok = self.next()
        where = self.accept_word("front", "back")
        if where is None:
            raise SparkyError('After "layer" I expected front or back — like: layer front',
                              tok.line)
        self.expect_newline()
        return A.Layer(where.value, tok.line)

    def stmt_bounce(self):
        tok = self.next()
        if self.accept_word("if"):
            self.expect_word("on", "like: bounce if on edge")
            self.expect_word("edge", "like: bounce if on edge")
        self.expect_newline()
        return A.Bounce(tok.line)

    def stmt_glide(self):
        tok = self.next()
        self.expect_word("to", "like: glide to 100 50 in 2 seconds")
        x = self.parse_expression()
        if self.at_op(","):
            self.next()
        y = self.parse_expression()
        self.expect_word("in", "like: glide to 100 50 in 2 seconds")
        seconds = self.parse_expression()
        self.seconds_word()
        self.expect_newline()
        return A.Glide(x, y, seconds, tok.line)

    # ---------- shapes and colors ----------

    def shape(self, kind, middle=None, example=""):
        tok = self.next()
        first = self.parse_expression()
        args = [first]
        if middle:
            self.expect_word(middle, f"like: {example}")
            args.append(self.parse_expression())
        self.expect_newline()
        return A.Shape(kind, args, tok.line)

    def stmt_circle(self):
        return self.shape("circle")

    def stmt_rectangle(self):
        return self.shape("rectangle", "by", "rectangle 80 by 40")

    def stmt_polygon(self):
        return self.shape("polygon", "sides", "polygon 6 sides 40")

    def stmt_star(self):
        return self.shape("star", "points", "star 5 points 40")

    def stmt_dot(self):
        return self.shape("dot")

    def stmt_arc(self):
        return self.shape("arc", "radius", "arc 90 radius 50")

    def stmt_fill(self):
        tok = self.next()
        self.accept_word("color")
        value = self.parse_expression()
        self.expect_newline()
        return A.Fill(value, tok.line)

    def stmt_no(self):
        tok = self.next()
        self.expect_word("fill", "like: no fill")
        self.expect_newline()
        return A.Fill(None, tok.line)

    def stmt_backdrop(self):
        tok = self.next()
        value = self.parse_expression()
        self.expect_newline()
        return A.Backdrop(value, tok.line)

    def stmt_save(self):
        tok = self.next()
        value = self.parse_expression()
        self.expect_word("as", 'like: save score as "best"')
        name = self.parse_expression()
        self.expect_newline()
        return A.Save(value, name, tok.line)

    def stmt_load(self):
        tok = self.next()
        name = self.parse_expression()
        self.expect_word("into", 'like: load "best" into best')
        target = self.expect_name("what you load")
        self.expect_newline()
        return A.Load(name, target, tok.line)

    # ---------- Sparky for Arduino ----------

    def stmt_pin(self):
        tok = self.next()
        pin = self.parse_sum()
        if self.accept_word("on"):
            mode, value = "on", None
        elif self.accept_word("off"):
            mode, value = "off", None
        elif self.accept_word("to"):
            mode, value = "to", self.parse_expression()
        else:
            raise SparkyError('After the pin number I expected on, off or to — like: '
                              "pin 13 on", tok.line)
        self.expect_newline()
        return A.Pin(pin, mode, value, tok.line)

    def stmt_servo(self):
        tok = self.next()
        self.accept_word("pin")
        pin = self.parse_sum()
        self.expect_word("to", "like: servo 9 to 90")
        angle = self.parse_expression()
        self.expect_newline()
        return A.Servo(pin, angle, tok.line)

    def stmt_buzzer(self):
        tok = self.next()
        self.accept_word("pin")
        pin = self.parse_expression()
        self.expect_newline()
        return A.Buzzer(pin, tok.line)

    # ---------- sprite / stage statements ----------

    def stmt_move(self):
        tok = self.next()
        distance = self.parse_expression()
        self.expect_newline()
        return A.Move(distance, tok.line)

    def stmt_back(self):
        tok = self.next()
        distance = self.parse_expression()
        self.expect_newline()
        return A.Move(A.UnOp("-", distance, tok.line), tok.line)

    def stmt_turn(self):
        tok = self.next()
        direction = 1
        if self.accept_word("left"):
            direction = -1
        else:
            self.accept_word("right")
        degrees = self.parse_expression()
        self.expect_newline()
        return A.Turn(degrees, direction, tok.line)

    def stmt_point(self):
        tok = self.next()
        heading = self.parse_expression()
        self.expect_newline()
        return A.Point(heading, tok.line)

    def stmt_goto(self):
        tok = self.next()
        x = self.parse_expression()
        if self.at_op(","):
            self.next()
        y = self.parse_expression()
        self.expect_newline()
        return A.Goto(x, y, tok.line)

    def stmt_home(self):
        tok = self.next()
        self.expect_newline()
        return A.Home(tok.line)

    def stmt_pen(self):
        tok = self.next()
        if self.accept_word("up"):
            self.expect_newline()
            return A.Pen("up", None, tok.line)
        if self.accept_word("down"):
            self.expect_newline()
            return A.Pen("down", None, tok.line)
        if self.accept_word("color"):
            if self.at_word("rainbow"):
                value = A.Str("rainbow", self.next().line)
            else:
                value = self.parse_expression()
            self.expect_newline()
            return A.Pen("color", value, tok.line)
        if self.accept_word("size"):
            value = self.parse_expression()
            self.expect_newline()
            return A.Pen("size", value, tok.line)
        if self.accept_word("style"):
            if self.at_word("solid", "dashed", "dotted"):
                value = A.Str(self.next().value, tok.line)
            else:
                value = self.parse_expression()
            self.expect_newline()
            return A.Pen("style", value, tok.line)
        if self.accept_word("opacity"):
            value = self.parse_expression()
            self.expect_newline()
            return A.Pen("opacity", value, tok.line)
        bad = self.peek()
        raise SparkyError('After "pen" I expected up, down, color, size, style or opacity — '
                          'like "pen down" or "pen color \"red\"".', bad.line)

    def stmt_clear(self):
        tok = self.next()
        self.expect_newline()
        return A.Clear(tok.line)

    def stmt_hide(self):
        tok = self.next()
        self.expect_newline()
        return A.HideShow(False, tok.line)

    def stmt_show(self):
        tok = self.next()
        self.expect_newline()
        return A.HideShow(True, tok.line)

    def stmt_stamp(self):
        tok = self.next()
        self.expect_newline()
        return A.Stamp(tok.line)

    def stmt_background(self):
        tok = self.next()
        color = self.parse_expression()
        self.expect_newline()
        return A.Background(color, tok.line)

    def stmt_speed(self):
        tok = self.next()
        value = self.parse_expression()
        self.expect_newline()
        return A.Speed(value, tok.line)

    def stmt_write(self):
        tok = self.next()
        value = self.parse_expression()
        style = {}
        while self.at_word("size", "bold", "italic"):
            word = self.next().value
            if word == "size":
                style["size"] = self.parse_expression()
            else:
                style[word] = True
        self.expect_newline()
        return A.WriteText(value, tok.line, style)

    def stmt_beep(self):
        tok = self.next()
        self.expect_newline()
        return A.Beep(tok.line)

    def stmt_size(self):
        tok = self.next()
        percent = self.parse_expression()
        self.expect_newline()
        return A.SpriteSize(percent, tok.line)

    def stmt_play(self):
        tok = self.next()
        if self.accept_word("note"):
            note = self.parse_expression()
            duration = None
            if self.accept_word("for"):
                duration = self.parse_expression()
            self.expect_newline()
            return A.PlaySound("note", note, duration, tok.line)
        value = self.parse_expression()
        self.expect_newline()
        return A.PlaySound("name", value, None, tok.line)

    # ---------- expressions (lowest to highest precedence) ----------

    def parse_expression(self):
        return self.parse_or()

    def parse_or(self):
        left = self.parse_and()
        while self.at_word("or"):
            tok = self.next()
            right = self.parse_and()
            left = A.BinOp("or", left, right, tok.line)
        return left

    def parse_and(self):
        left = self.parse_not()
        while self.at_word("and"):
            tok = self.next()
            right = self.parse_not()
            left = A.BinOp("and", left, right, tok.line)
        return left

    def parse_not(self):
        if self.at_word("not"):
            tok = self.next()
            return A.UnOp("not", self.parse_not(), tok.line)
        return self.parse_comparison()

    def parse_comparison(self):
        left = self.parse_sum()
        tok = self.peek()
        op = None
        if self.at_op("=", ">", "<", ">=", "<="):
            op = self.next().value
        elif self.at_word("is"):
            self.next()
            op = "="
            if self.at_word("not"):
                self.next()
                op = "!="
        if op is None:
            return left
        right = self.parse_sum()
        return A.BinOp(op, left, right, tok.line)

    def parse_sum(self):
        left = self.parse_term()
        while self.at_op("+", "-"):
            tok = self.next()
            right = self.parse_term()
            left = A.BinOp(tok.value, left, right, tok.line)
        return left

    def parse_term(self):
        left = self.parse_factor()
        while self.at_op("*", "/") or self.at_word("mod"):
            tok = self.next()
            op = tok.value if tok.kind == OP else "mod"
            right = self.parse_factor()
            left = A.BinOp(op, left, right, tok.line)
        return left

    def parse_factor(self):
        tok = self.peek()
        if self.at_op("-"):
            self.next()
            return A.UnOp("-", self.parse_factor(), tok.line)
        if self.at_word("round", "abs"):
            if self.glued_call_next():          # round(x, 2) and abs(x)
                return self.parse_primary()
            self.next()
            return A.UnOp(tok.value, self.parse_factor(), tok.line)
        if self.at_word("item"):
            self.next()
            index = self.parse_factor()
            self.expect_word("of", "like: item 1 of pets")
            target = self.parse_factor()
            return A.Index(target, index, tok.line)
        if self.at_word("random"):
            self.next()
            if self.accept_word("color"):
                return A.RandomColor(tok.line)
            low = self.parse_factor()
            self.expect_word("to", "like: random 1 to 10")
            high = self.parse_factor()
            return A.Random(low, high, tok.line)
        return self.parse_primary()

    def parse_list_items(self, closer, opener_line, what):
        items = []
        self.skip_newlines()
        if not self.at_op(closer):
            items.append(self.parse_expression())
            self.skip_newlines()
            while self.at_op(","):
                self.next()
                self.skip_newlines()
                items.append(self.parse_expression())
                self.skip_newlines()
        end = self.next()
        if end.kind != OP or end.value != closer:
            raise SparkyError(what, opener_line)
        return items

    def parse_record(self, tok):
        pairs = []
        self.skip_newlines()
        while not self.at_op("}"):
            key = self.next()
            if key.kind not in (WORD, STRING):
                raise SparkyError("Records look like {name: \"Rex\", age: 3} — each field "
                                  "is a name, a colon, and a value.", tok.line)
            if not self.at_op(":"):
                raise SparkyError(f'I expected a ":" after "{key.value}" — like: '
                                  '{name: "Rex"}', tok.line)
            self.next()
            pairs.append((str(key.value).lower(), self.parse_expression()))
            self.skip_newlines()
            if self.at_op(","):
                self.next()
                self.skip_newlines()
            elif not self.at_op("}"):
                if self.peek().kind in (NEWLINE, EOF):
                    break
                raise SparkyError("Put commas between the fields of a record, like "
                                  '{name: "Rex", age: 3}.', tok.line)
        end = self.next()
        if end.kind != OP or end.value != "}":
            raise SparkyError("This record starts with { but never closes. End it with }.",
                              tok.line)
        return A.RecordLit(pairs, tok.line)

    def parse_template(self, text, line):
        """'Hi {name}!' -> Template(["Hi ", Var(name), "!"]). {{ and }} are braces."""
        parts, buf, i = [], [], 0
        while i < len(text):
            ch = text[i]
            if ch == "{" and text[i + 1:i + 2] == "{":
                buf.append("{")
                i += 2
            elif ch == "}" and text[i + 1:i + 2] == "}":
                buf.append("}")
                i += 2
            elif ch == "{":
                close = text.find("}", i + 1)
                if close < 0:
                    raise SparkyError("A { in your text never closes. Put the name between "
                                      'braces, like "Hi {name}!", or write {{ for a brace.',
                                      line)
                inner = text[i + 1:close].strip()
                if not inner:
                    raise SparkyError("There's nothing between { and } in your text. Put a "
                                      'name there, like "Hi {name}!".', line)
                if buf:
                    parts.append("".join(buf))
                    buf = []
                sub = Parser(inner)
                for t in sub.tokens:
                    t.line = line
                expr = sub.parse_expression()
                if sub.peek().kind not in (NEWLINE, EOF):
                    raise SparkyError(f'I couldn\'t read "{{{inner}}}" in your text.', line)
                parts.append(expr)
                i = close + 1
            else:
                buf.append(ch)
                i += 1
        if buf:
            parts.append("".join(buf))
        return A.Template(parts, line)

    def parse_primary(self):
        tok = self.next()
        if tok.kind == NUMBER:
            return A.Num(tok.value, tok.line)
        if tok.kind == STRING:
            if "{" in tok.value or "}}" in tok.value:
                return self.parse_template(tok.value, tok.line)
            return A.Str(tok.value, tok.line)
        if tok.kind == OP and tok.value == "[":
            items = self.parse_list_items(
                "]", tok.line, "This list starts with [ but never closes. "
                "Put commas between items and end with ].")
            return A.ListLit(items, tok.line)
        if tok.kind == OP and tok.value == "{":
            return self.parse_record(tok)
        if tok.kind == OP and tok.value == "(":
            expr = self.parse_expression()
            closer = self.next()
            if closer.kind != OP or closer.value != ")":
                raise SparkyError("This ( never found its ).", tok.line)
            return expr
        if tok.kind == WORD:
            word = tok.value
            if word == "true":
                return A.Bool(True, tok.line)
            if word == "false":
                return A.Bool(False, tok.line)
            if word == "nothing":
                return A.Nothing(tok.line)
            after = self.peek()
            if after.kind == OP and after.value == "(" and after.glued:
                if word in RESERVED and word not in ("round", "abs"):
                    raise SparkyError(f'"{word}" is a Sparky word, not a '
                                      "function.", tok.line)
                self.next()
                args = self.parse_list_items(
                    ")", tok.line, f'The call to "{word}" starts with ( but never closes. '
                    "Put commas between inputs and end with ).")
                return A.Call(word, args, tok.line)
            # sensing and sprite questions
            if word == "distance" and after.kind == WORD and after.value == "to":
                self.next()
                return A.DistanceTo(self.next().value, tok.line)
            if word == "touching" and after.kind == WORD:
                return A.Touching(self.next().value, tok.line)
            if word == "key" and after.kind == STRING:
                key = self.parse_primary()
                self.accept_word("down") or self.accept_word("pressed")
                return A.KeyDown(key, tok.line)
            if word == "mouse" and after.kind == WORD and after.value in ("x", "y", "down"):
                return A.Mouse(self.next().value, tok.line)
            if word == "read" and after.kind == WORD and after.value == "pin":
                self.next()
                return A.ReadPin(self.parse_factor(), tok.line)
            # FIELD of RECORD   (and "length of list")
            if after.kind == WORD and after.value == "of" and word != "item":
                self.next()
                target = self.parse_factor()
                if word == "length":
                    return A.Call("length", [target], tok.line)
                return A.Field(word, target, tok.line)
            if word in VALUE_WORDS:
                return A.Var(word, tok.line)
            if word in RESERVED:
                raise SparkyError(f'I wasn\'t expecting "{word}" here.', tok.line)
            return A.Var(word, tok.line)
        if tok.kind in (NEWLINE, EOF):
            raise SparkyError("This line ends too early — I expected a number, "
                              "some text, or a variable here.", tok.line)
        raise SparkyError(f'I wasn\'t expecting "{tok.value}" here.', tok.line)


def parse(source):
    try:
        return Parser(source).parse_program()
    except SparkyError as err:
        raise attach_example(err, source)
