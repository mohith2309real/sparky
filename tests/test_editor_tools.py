# The editor's brains: block matching, folding, breadcrumbs, auto end,
# outline, re-indent, go to definition, rename, colors and numbers.
# Run with: python3 tests/test_editor_tools.py

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sparky.ide import code_tools as ct  # noqa: E402

passed = 0


def check(name, got, want):
    global passed
    assert got == want, f"FAILED: {name}\n  got:  {got!r}\n  want: {want!r}"
    passed += 1
    print(f"  ok - {name}")


PROGRAM = """teach star size
  repeat 5 times
    move size
    turn 144
  end
end
if score > 3 then
  say "big"
else
  say "small"
end
try
  say 1 / 0
oops
  say problem
end
when key "space" pressed
  say "jump"
end
""".split("\n")

check("end matches its opener", ct.matching_line(PROGRAM, 5), 2)
check("opener matches its end", ct.matching_line(PROGRAM, 1), 6)
check("else belongs to its if", ct.matching_line(PROGRAM, 9), 7)
check("oops belongs to its try", ct.matching_line(PROGRAM, 14), 12)
check("foldable blocks", ct.foldable(PROGRAM), {1: 6, 2: 5, 7: 11, 12: 16, 17: 19})
check("breadcrumbs", ct.breadcrumbs(PROGRAM, 3), ["teach star size", "repeat 5 times"])
check("breadcrumbs drop 'then'", ct.breadcrumbs(PROGRAM, 8), ["if score > 3"])
check("needs end (open block)", ct.needs_end(["repeat 4 times", "  move 10"], 1), True)
check("no end needed (closed)", ct.needs_end(["repeat 4 times", "  move 10", "end"], 1), False)
check("no end for plain lines", ct.needs_end(["say 1"], 1), False)
check("nested open block needs end",
      ct.needs_end(["forever", "  repeat 2 times", "end"], 2), True)
check("comments don't open blocks", ct.needs_end(["# repeat this"], 1), False)

# outline
check("sparky outline", [(n, k, name) for n, k, name in ct.outline(PROGRAM + ["set score to 0",
                                                                              "make sprite rocket"])],
      [(1, "command", "star size"), (17, "event", 'when key "space" pressed'),
       (21, "variable", "score"), (22, "sprite", "rocket")])
check("python outline", ct.outline(["class Pet:", "    def speak(self):", "def main():"], "python"),
      [(1, "class", "Pet"), (2, "function", "  speak"), (3, "function", "main")])
check("arduino outline", ct.outline(["void setup() {", "  if (x) {", "int readLight(int pin) {"],
                                    "arduino"),
      [(1, "function", "setup"), (3, "function", "readLight")])

# re-indent
messy = "repeat 4 times\nmove 10\n      if x > 1 then\nsay x\n   else\nsay 0\nend\nend"
check("sparky re-indent", ct.reindent(messy),
      "repeat 4 times\n  move 10\n  if x > 1 then\n    say x\n  else\n    say 0\n  end\nend")
c_messy = "void loop() {\nif (x) {\ndelay(1); // {\n}\nString s = \"}\";\n}"
check("c re-indent ignores braces in text and comments", ct.reindent(c_messy, "arduino"),
      "void loop() {\n  if (x) {\n    delay(1); // {\n  }\n  String s = \"}\";\n}")

# definitions
check("go to a taught command", ct.definition_line(PROGRAM, "star"), 1)
check("go to an input", ct.definition_line(PROGRAM, "size"), 1)
check("go to a variable", ct.definition_line(["say 1", "set score to 0", "set score to 2"], "score"), 2)
check("go to an asked variable", ct.definition_line(['ask "name?" into name'], "name"), 1)
check("python definition", ct.definition_line(["x = 1", "def go():"], "go", "python"), 2)
check("arduino definition", ct.definition_line(["int ledPin = 13;", "void blink(int n) {"], "blink",
                                               "arduino"), 2)

# rename
src = 'set score to 0\nsay "score: {score}"  # score here stays\nchange score by 1\nsay scores'
check("rename skips text and comments but not {templates}",
      ct.rename(src, "score", "points"),
      'set points to 0\nsay "score: {points}"  # score here stays\nchange points by 1\nsay scores')

# colors and numbers
check("color names and hex", ct.colors_in_line('pen color "red"  fill color "#f80"'),
      [(11, 14, "#e5484d"), (29, 33, "#ff8800")])
check("not a color", ct.colors_in_line('say "hello"'), [])
check("number under the cursor", ct.number_at("move 100", 6), (5, 8, 100.0))
check("negative numbers", ct.number_at("goto 10 -60", 9), (8, 11, -60.0))
check("no number in a word", ct.number_at("set x2 to 4", 5), None)
check("no number inside text", ct.number_at('say "3 cats"', 6), None)
check("keeps decimals", (ct.format_number(0.5, "0.25"), ct.format_number(12.6, "10")), ("0.50", "13"))

print(f"\nAll {passed} editor tool checks passed!")
