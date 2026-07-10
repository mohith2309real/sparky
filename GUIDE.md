# ⚡ The Sparky Guide

Welcome! This is the complete guide to Sparky — for kids starting out,
and for grown-ups who want the full picture. The same lessons live
inside the IDE under **Learn**, where every lesson has a
**Try this code** button.

## Part 1 — First steps

### Your first program

Open Sparky (double-click `Sparky.command` on Mac, `sparky.bat` on
Windows, `sparky.sh` on Linux). Type this and press **Run**:

```
say "Hello, world!"
```

Sparky says it in the console AND in a speech bubble. That's the whole
loop of coding: write → run → see what happens → change it → run again.

### Talking and asking

```
ask "What's your name?" into name
say "Nice to meet you, " + name + "!"
```

`ask` waits for an answer in the console and saves it **into** a
variable. `+` glues text together.

### Remembering things (variables)

```
set score to 0
change score by 10
say "Score: " + score
```

A variable is a box with a name. `set` puts something in the box,
`change` adds to it (negative numbers subtract).

### Making choices

```
ask "Pick a number!" into num
if num > 100 then
  say "Whoa, BIG!"
else if num > 10 then
  say "Medium."
else
  say "Small and mighty!"
end
```

Compare with `>` `<` `=` `>=` `<=`, `is`, `is not`.
Combine checks with `and`, `or`, `not`.

### Loops

```
repeat 3 times
  say "hip hip hooray!"
end

set n to 5
repeat until n = 0
  say n + "..."
  change n by -1
end

forever
  say "this never stops (press Stop!)"
end
```

`stop loop` jumps out of a loop. `stop program` ends everything.
`wait 0.5` pauses for half a second.

## Part 2 — The stage

The stage works like Scratch: **(0,0) is the center**, x grows right,
**y grows up**. Heading 0 points up; `turn` goes clockwise.

### Drawing

```
speed 6
pen color "blue"
pen size 5
repeat 4 times
  move 100
  turn 90
end
```

That's a square! The pen starts **down** (drawing). `pen up` lets
Sparky travel without drawing. Colors: red orange yellow green blue
purple pink brown black white gray cyan magenta lime navy cream ink —
or any `"#ff8800"` hex code.

More stage commands: `back`, `turn left`, `point`, `goto x y`, `home`,
`hide` / `show`, `size 150`, `stamp`, `background "ink"`, `clear`,
`write "text"`, `beep`, `speed 1..10`.

### The shape secret

A closed shape's turns add up to 360 (or a multiple). Square:
4 × 90. Triangle: 3 × 120. Five-point star: 5 × 144 (that's 720 —
two full spins!). Try `repeat 60 times / move length / turn 59` with a
growing `length` — that's the spiral example.

## Part 3 — Your own commands

```
teach square length
  repeat 4 times
    move length
    turn 90
  end
end

do square 40
do square 80
```

`teach` invents a new command; `do` uses it. Inputs (like `length`)
are local — they don't leak out.

**The boss move — recursion.** A command can `do` *itself*:

```
teach branch length
  if length > 7 then
    move length
    turn left 24
    do branch length * 0.72
    turn 48
    do branch length * 0.72
    turn left 24
    back length
  end
end
```

Each branch grows two smaller branches until they're too small. Open
**Examples ▸ Fractal Tree** to see the full colored version. This is a
technique professional programmers use constantly — and it fits in
15 lines of Sparky.

## Part 4 — Randomness and games

```
set secret to random 1 to 20
```

`random` makes games unpredictable. The recipe for almost every
guessing game: pick a secret, `repeat until` the guess matches, give a
hint each round. See **Examples ▸ Guess The Number**.

Answers from `ask` compare naturally with numbers: if the player types
`5`, then `guess = 5` is true.

## Part 5 — Beyond the editor

- **Make an App** (More ▾ menu): packages your program into a folder
  with double-clickable Play launchers for Mac/Windows/Linux. It runs
  in the Sparky **player** — stage and console only, no editor.
  (The computer needs Sparky installed; the app's README explains.)
- **Community** (More ▾): share `.spark` files with friends; drop
  received ones into the `gallery/` folder and they appear in the
  Community window.
- **Terminal nerds:** `.venv/bin/python -m sparky run file.spark`
  runs text programs in the terminal;
  `... -m sparky play file.spark` opens the player.

## Part 6 — For grown-ups

Sparky is a real language implementation you can read: a tokenizer,
recursive-descent parser, and tree-walking interpreter in
`sparky/lang/` (~900 lines, pure standard library, no dependencies).
The IDE is native PyQt6 in `sparky/ide/`. Nice entry points:

- Add a language command: one `stmt_*` method in `parser.py`, one AST
  node, one `exec_*` method in `interpreter.py`.
- Add a block: one line in `ide/blocks.py`.
- Add a lesson: one dict in `ide/lessons_data.py`.
- The interpreter is a generator — it `yield`s a tick after each
  statement, which is how Run/Stop/speed work without threads fighting.

Errors are always friendly (`Oops! Line 2 ... Did you mean "move"?`),
including "did you mean" suggestions from `difflib`.

## Full command reference

| Command | What it does |
|---|---|
| `say "hi"` | print + speech bubble |
| `ask "..?" into name` | ask, save answer |
| `set x to 0` / `change x by 1` | make / add to a variable |
| `if ... then / else if / else / end` | choices |
| `repeat N times ... end` | loop N times |
| `repeat until COND ... end` | loop until true |
| `forever ... end` | loop until Stop |
| `stop loop` / `stop program` | escape / end |
| `wait 0.5` | pause (seconds) |
| `teach name inputs... end` / `do name args...` | own commands |
| `move` `back` `turn` `turn left` `point` | walking & turning |
| `goto x y` / `home` | jump / center |
| `pen up/down/color/size` | drawing |
| `background "c"` / `clear` | stage paint / erase |
| `hide` `show` `size 150` `stamp` | sprite looks |
| `write "text"` / `beep` | stage text / sound |
| `play "pop"` | sound effects: pop ding boing laser drum tada jump |
| `play note 4 for 0.5` | notes 1–14 (two do-re-mi octaves) — make songs! |
| `speed 1..10` | how fast |
| `random A to B`, `round x`, `abs x` | numbers |
| `+ - * / mod`, `= > < >= <=`, `is`, `is not`, `and or not` | math & logic |

---

Sparky was created by **Mohith** — [mohith2309.github.io](https://mohith2309.github.io)
