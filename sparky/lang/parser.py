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

from . import ast_nodes as A
from .errors import SparkyError, did_you_mean
from .tokenizer import tokenize, NUMBER, STRING, WORD, OP, NEWLINE, EOF

# every word that starts a statement (used for error suggestions too)
STATEMENT_WORDS = [
    "say", "ask", "set", "change", "repeat", "forever", "if", "wait", "stop",
    "teach", "do", "move", "back", "turn", "point", "goto", "home", "pen",
    "clear", "hide", "show", "stamp", "background", "speed", "write", "beep",
    "size", "play", "end", "else",
]

# words that may appear inside statements/expressions
HELPER_WORDS = [
    "to", "into", "by", "times", "until", "then", "with", "and", "or", "not",
    "is", "true", "false", "left", "right", "up", "down", "color", "loop",
    "program", "seconds", "second", "random", "round", "abs", "note", "for",
]

ALL_WORDS = STATEMENT_WORDS + HELPER_WORDS

# words that can never be a variable name
RESERVED = set(ALL_WORDS) - {"color", "left", "right", "up", "down"}


class Parser:
    def __init__(self, source):
        self.tokens = tokenize(source)
        self.pos = 0

    # ---------- token helpers ----------

    def peek(self):
        return self.tokens[self.pos]

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

    # ---------- program & blocks ----------

    def parse_program(self):
        body = []
        self.skip_newlines()
        while self.peek().kind != EOF:
            body.append(self.parse_statement())
            self.skip_newlines()
        return body

    def parse_block(self, opener, opener_line):
        """Parse statements until 'end' (or 'else' for if-blocks)."""
        body = []
        self.skip_newlines()
        while True:
            tok = self.peek()
            if tok.kind == EOF:
                raise SparkyError(f'Your "{opener}" on line {opener_line} never '
                                  'found its "end". Add "end" to close it.',
                                  opener_line)
            if self.at_word("end", "else"):
                return body
            body.append(self.parse_statement())
            self.skip_newlines()

    # ---------- statements ----------

    def parse_statement(self):
        tok = self.peek()
        if tok.kind != WORD:
            raise SparkyError(f'I expected a command here, but found "{tok.value}". '
                              'Commands are words like say, move, or repeat.', tok.line)

        word = tok.value
        method = getattr(self, f"stmt_{word}", None)
        if method is None:
            if word in HELPER_WORDS:
                raise SparkyError(f'"{word}" can\'t start a line by itself.', tok.line)
            hint = did_you_mean(word, STATEMENT_WORDS)
            raise SparkyError(f'I don\'t know the command "{word}".{hint}', tok.line)
        return method()

    def stmt_end(self):
        tok = self.peek()
        raise SparkyError('This "end" has nothing to close. Every "end" needs a '
                          "repeat, forever, if, or teach above it.", tok.line)

    def stmt_else(self):
        tok = self.peek()
        raise SparkyError('"else" only works inside an "if ... end" block.', tok.line)

    def stmt_say(self):
        tok = self.next()
        value = self.parse_expression()
        self.expect_newline()
        return A.Say(value, tok.line)

    def stmt_ask(self):
        tok = self.next()
        prompt = self.parse_expression()
        self.expect_word("into", 'like: ask "What\'s your name?" into name')
        target = self.expect_name("your answer")
        self.expect_newline()
        return A.Ask(prompt, target, tok.line)

    def stmt_set(self):
        tok = self.next()
        name = self.expect_name("a variable")
        self.expect_word("to", "like: set score to 0")
        value = self.parse_expression()
        self.expect_newline()
        return A.SetVar(name, value, tok.line)

    def stmt_change(self):
        tok = self.next()
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
            self.expect_word("end", "to close the repeat")
            self.expect_newline()
            return A.RepeatUntil(condition, body, tok.line)
        count = self.parse_expression()
        self.expect_word("times", "like: repeat 10 times")
        self.expect_newline()
        body = self.parse_block("repeat", tok.line)
        self.expect_word("end", "to close the repeat")
        self.expect_newline()
        return A.RepeatTimes(count, body, tok.line)

    def stmt_forever(self):
        tok = self.next()
        self.expect_newline()
        body = self.parse_block("forever", tok.line)
        self.expect_word("end", "to close the forever")
        self.expect_newline()
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
        self.expect_word("end", "to close the if")
        self.expect_newline()
        return A.If(branches, else_body, tok.line)

    def stmt_wait(self):
        tok = self.next()
        seconds = self.parse_expression()
        self.accept_word("seconds") or self.accept_word("second")
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
        self.expect_word("end", "to close the teach")
        self.expect_newline()
        return A.Teach(name, params, body, tok.line)

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
            value = self.parse_expression()
            self.expect_newline()
            return A.Pen("color", value, tok.line)
        if self.accept_word("size"):
            value = self.parse_expression()
            self.expect_newline()
            return A.Pen("size", value, tok.line)
        bad = self.peek()
        raise SparkyError('After "pen" I expected up, down, color, or size — '
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
        self.expect_newline()
        return A.WriteText(value, tok.line)

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
            self.next()
            return A.UnOp(tok.value, self.parse_factor(), tok.line)
        if self.at_word("random"):
            self.next()
            low = self.parse_factor()
            self.expect_word("to", "like: random 1 to 10")
            high = self.parse_factor()
            return A.Random(low, high, tok.line)
        return self.parse_primary()

    def parse_primary(self):
        tok = self.next()
        if tok.kind == NUMBER:
            return A.Num(tok.value, tok.line)
        if tok.kind == STRING:
            return A.Str(tok.value, tok.line)
        if tok.kind == OP and tok.value == "(":
            expr = self.parse_expression()
            closer = self.next()
            if closer.kind != OP or closer.value != ")":
                raise SparkyError("This ( never found its ).", tok.line)
            return expr
        if tok.kind == WORD:
            if tok.value == "true":
                return A.Bool(True, tok.line)
            if tok.value == "false":
                return A.Bool(False, tok.line)
            if tok.value in RESERVED:
                raise SparkyError(f'I wasn\'t expecting "{tok.value}" here.', tok.line)
            return A.Var(tok.value, tok.line)
        if tok.kind in (NEWLINE, EOF):
            raise SparkyError("This line ends too early — I expected a number, "
                              "some text, or a variable here.", tok.line)
        raise SparkyError(f'I wasn\'t expecting "{tok.value}" here.', tok.line)


def parse(source):
    return Parser(source).parse_program()
