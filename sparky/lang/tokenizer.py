# Sparky tokenizer: turns source text into a flat list of tokens.
# Sparky is case-insensitive (kids shouldn't fight the shift key),
# comments start with #, and blocks are closed with the word "end".

from .errors import SparkyError

# Token kinds
NUMBER = "NUMBER"
STRING = "STRING"
WORD = "WORD"      # keywords and variable names (lowercased)
OP = "OP"          # + - * / ( ) , = > < >= <=
NEWLINE = "NEWLINE"
EOF = "EOF"

TWO_CHAR_OPS = (">=", "<=")
ONE_CHAR_OPS = "+-*/(),=><"

# words after which a "-" is still an operator, not a negative number
# (so "set x to -5" and "wait 2 - 1" both behave sensibly)
OPERATOR_WORDS = {"to", "by", "into", "times", "until", "then", "with",
                  "and", "or", "not", "is", "mod"}


class Token:
    def __init__(self, kind, value, line):
        self.kind = kind
        self.value = value
        self.line = line

    def __repr__(self):
        return f"Token({self.kind}, {self.value!r}, line {self.line})"


def tokenize(source):
    tokens = []
    line = 1
    i = 0
    n = len(source)

    while i < n:
        ch = source[i]

        # comments run to the end of the line
        if ch == "#":
            while i < n and source[i] != "\n":
                i += 1
            continue

        if ch == "\n":
            # collapse repeated blank lines into one NEWLINE
            if tokens and tokens[-1].kind != NEWLINE:
                tokens.append(Token(NEWLINE, "\n", line))
            line += 1
            i += 1
            continue

        if ch in " \t\r":
            i += 1
            continue

        if ch == '"' or ch == "'":
            quote = ch
            i += 1
            start_line = line
            text = []
            while i < n and source[i] != quote:
                if source[i] == "\n":
                    raise SparkyError(
                        f'This text starts with {quote} but never closes. '
                        f'Add a {quote} at the end of your text.', start_line)
                text.append(source[i])
                i += 1
            if i >= n:
                raise SparkyError(
                    f'This text starts with {quote} but never closes. '
                    f'Add a {quote} at the end of your text.', start_line)
            i += 1  # skip closing quote
            tokens.append(Token(STRING, "".join(text), start_line))
            continue

        # "move 10 -60"-style negative numbers: a "-" glued to a digit,
        # with a space before it, right after something that ends a value.
        # "5 - 3" (spaces both sides) and "5-3" (no spaces) stay subtraction.
        if (ch == "-" and i + 1 < n
                and (source[i + 1].isdigit() or source[i + 1] == ".")
                and i > 0 and source[i - 1] in " \t"
                and tokens
                and (tokens[-1].kind in (NUMBER, STRING)
                     or (tokens[-1].kind == WORD
                         and tokens[-1].value not in OPERATOR_WORDS)
                     or (tokens[-1].kind == OP and tokens[-1].value == ")"))):
            start = i
            i += 1
            while i < n and (source[i].isdigit() or source[i] == "."):
                i += 1
            text = source[start:i]
            try:
                value = float(text)
            except ValueError:
                raise SparkyError(f'"{text}" looks like a number but I can\'t '
                                  "read it. Numbers look like 10 or 3.5.", line)
            tokens.append(Token(NUMBER, value, line))
            continue

        if ch.isdigit() or (ch == "." and i + 1 < n and source[i + 1].isdigit()):
            start = i
            while i < n and (source[i].isdigit() or source[i] == "."):
                i += 1
            text = source[start:i]
            try:
                value = float(text)
            except ValueError:
                raise SparkyError(f'"{text}" looks like a number but I can\'t read it. '
                                  'Numbers look like 10 or 3.5.', line)
            tokens.append(Token(NUMBER, value, line))
            continue

        if ch.isalpha() or ch == "_":
            start = i
            while i < n and (source[i].isalnum() or source[i] == "_"):
                i += 1
            tokens.append(Token(WORD, source[start:i].lower(), line))
            continue

        if source[i:i + 2] in TWO_CHAR_OPS:
            tokens.append(Token(OP, source[i:i + 2], line))
            i += 2
            continue

        if ch in ONE_CHAR_OPS:
            tokens.append(Token(OP, ch, line))
            i += 1
            continue

        raise SparkyError(f'I don\'t understand the symbol "{ch}".', line)

    if tokens and tokens[-1].kind != NEWLINE:
        tokens.append(Token(NEWLINE, "\n", line))
    tokens.append(Token(EOF, None, line))
    return tokens
