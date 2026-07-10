# All Learn-panel content: 10 lessons, challenges, and the full language
# reference. Pure data — no Qt imports — so tests can check every snippet.

LESSONS = [
    {
        "title": "1. Say hello!",
        "emoji": "👋",
        "html": """
<h2>👋 Say hello!</h2>
<p><b>say</b> makes Sparky talk. Whatever you put between the quotes
shows up in the console <i>and</i> in a speech bubble on the stage.</p>
<p>The <b>+</b> glues pieces of text together.</p>
<p>Press <b>Try this code</b>, then hit the orange <b>Run</b> button.
Then change the words and run it again — that's how coders learn!</p>
""",
        "code": '''say "Hello, world!"
say "My name is Sparky."
say "2 + 2 is " + (2 + 2)
''',
    },
    {
        "title": "2. Ask questions",
        "emoji": "❓",
        "html": """
<h2>❓ Ask questions</h2>
<p><b>ask</b> asks a question and waits for an answer in the console.
The answer gets saved <b>into</b> a variable — a box with a name.</p>
<p>After this runs, the box called <b>name</b> holds whatever you typed,
and you can use it anywhere.</p>
""",
        "code": '''ask "What's your name?" into name
say "Nice to meet you, " + name + "!"
ask "How old are you?" into age
say "Wow, " + age + " is a great age to code!"
''',
    },
    {
        "title": "3. Remember things",
        "emoji": "📦",
        "html": """
<h2>📦 Remember things (variables)</h2>
<p><b>set</b> makes a variable. <b>change</b> adds to it
(use a negative number to subtract).</p>
<p>Variables are how games keep score!</p>
""",
        "code": '''set score to 0
say "Score: " + score
change score by 10
say "You found a star! Score: " + score
change score by -3
say "Ouch, a rock. Score: " + score
''',
    },
    {
        "title": "4. Make choices",
        "emoji": "🔀",
        "html": """
<h2>🔀 Make choices (if)</h2>
<p><b>if ... then</b> runs code only when something is true.
<b>else</b> runs when it isn't. You can chain more checks
with <b>else if</b>.</p>
<p>You can compare with <b>&gt;</b> <b>&lt;</b> <b>=</b>
<b>is</b> and <b>is not</b>.</p>
""",
        "code": '''ask "Pick a number!" into num
if num > 100 then
  say "Whoa, that's a BIG number!"
else if num > 10 then
  say "Nice medium-sized number."
else
  say "A small and mighty number!"
end
''',
    },
    {
        "title": "5. Loops!",
        "emoji": "🔁",
        "html": """
<h2>🔁 Loops!</h2>
<p><b>repeat ... times</b> does something again and again.
<b>repeat until</b> keeps going until something becomes true.</p>
<p>Computers LOVE repeating things. That's their superpower —
and now it's yours.</p>
""",
        "code": '''repeat 3 times
  say "hip hip hooray!"
end

set countdown to 5
repeat until countdown = 0
  say countdown + "..."
  change countdown by -1
end
say "LIFT OFF! 🚀"
''',
    },
    {
        "title": "6. Draw with the pen",
        "emoji": "🖊️",
        "html": """
<h2>🖊️ Draw with the pen</h2>
<p>Sparky carries a pen. <b>move</b> walks forward, <b>turn</b> spins.
While the pen is <b>down</b>, walking draws a line!</p>
<p>Try changing the <b>turn 90</b> — what happens with 120? With 60?</p>
""",
        "code": '''speed 6
pen color "blue"
pen size 5

repeat 4 times
  move 100
  turn 90
end

say "I drew a square!"
''',
    },
    {
        "title": "7. Shapes everywhere",
        "emoji": "✨",
        "html": """
<h2>✨ Shapes everywhere</h2>
<p>Loops + drawing = magic. A tiny change makes a totally new shape.</p>
<p>The secret of a closed star or polygon: the turns must add up to a
full circle (or a few full circles).</p>
<p><b>goto</b> jumps somewhere, <b>pen up</b> travels without drawing,
and <b>stamp</b> leaves a Sparky sticker.</p>
""",
        "code": '''speed 8
background "ink"
pen color "yellow"
pen size 3

# a star
repeat 5 times
  move 120
  turn 144
end

# hop somewhere and stamp
pen up
goto 150 100
stamp
goto -150 100
stamp
hide
''',
    },
    {
        "title": "8. Teach new tricks",
        "emoji": "🎓",
        "html": """
<h2>🎓 Teach new tricks (your own commands!)</h2>
<p><b>teach</b> creates a brand-new command. Give it a name, teach it
what to do, close with <b>end</b> — then use it with <b>do</b>.</p>
<p>Commands can take <b>inputs</b>. Below, <i>length</i> changes how
big each square is. One recipe, endless squares!</p>
""",
        "code": '''speed 9
pen color "purple"

teach square length
  repeat 4 times
    move length
    turn 90
  end
end

do square 40
do square 70
do square 100

hide
''',
    },
    {
        "title": "9. Surprise!",
        "emoji": "🎲",
        "html": """
<h2>🎲 Surprise! (random)</h2>
<p><b>random 1 to 10</b> gives a surprise number every time.
Random makes games exciting — nobody knows what happens next,
not even you!</p>
""",
        "code": '''set secret to random 1 to 10
set guess to 0
say "I picked a number from 1 to 10!"

repeat until guess = secret
  ask "Your guess?" into guess
  if guess > secret then
    say "Too big!"
  else if guess < secret then
    say "Too small!"
  end
end

say "YES! It was " + secret + "!"
beep
''',
    },
    {
        "title": "10. Forever & speed",
        "emoji": "🌀",
        "html": """
<h2>🌀 Forever &amp; speed</h2>
<p><b>forever</b> loops until you press <b>Stop</b> (or the program says
<b>stop loop</b>). <b>wait</b> pauses. <b>speed</b> sets how fast Sparky
moves: 1 is slow-motion, 10 is instant.</p>
<p>This one never stops on its own — press the Stop button when
you're done watching!</p>
""",
        "code": '''speed 10
background "ink"
pen size 2

forever
  set shade to random 1 to 3
  if shade = 1 then
    pen color "orange"
  else if shade = 2 then
    pen color "cyan"
  else
    pen color "pink"
  end
  move random 20 to 120
  turn random 30 to 150
  wait 0.05
end
''',
    },
    {
        "title": "🏆 Challenges",
        "emoji": "🏆",
        "html": """
<h2>🏆 Challenges</h2>
<p>Ready to code without training wheels? Try these — in any order.</p>
<ol>
<li><b>Name rocket:</b> ask for a name, then count down from 10 and
blast off with their name in the message.</li>
<li><b>Rainbow staircase:</b> draw stairs where every step is a
different color.</li>
<li><b>Polygon machine:</b> teach a command <i>polygon sides</i> that
can draw ANY shape. (Hint: turn 360 / sides.)</li>
<li><b>Quiz show:</b> 3 questions, keep score, say the total at the
end with a beep for a perfect score.</li>
<li><b>Snowfall:</b> forever loop — jump to a random spot near the top,
stamp, repeat. (pen up first!)</li>
<li><b>Boss level — fractal tree:</b> open Examples ▸ Fractal Tree and
figure out how a command can <i>do itself</i>. That trick is called
recursion, and real programmers use it every day.</li>
</ol>
<p>Starter code for the polygon machine is on the right — finish it!</p>
""",
        "code": '''# Finish the polygon machine!
# A triangle turns 120 (that's 360/3). A square turns 90 (360/4).
# So ANY shape turns 360 / sides. Fill in the ??? and run it!

teach polygon sides
  repeat sides times
    move 60
    turn 360 / sides
  end
end

do polygon 3
do polygon 4
do polygon 6
''',
    },
]

REFERENCE_HTML = """
<h1>The Sparky Language</h1>
<p>Everything Sparky understands, on one page. Commands are not
case-sensitive. Comments start with <b>#</b>.</p>

<h2>Talking</h2>
<table cellpadding="4">
<tr><td><b>say "hi"</b></td><td>print to the console + speech bubble</td></tr>
<tr><td><b>ask "..?" into name</b></td><td>ask, save the answer in a variable</td></tr>
<tr><td><b>write "hi"</b></td><td>paint text on the stage at Sparky's spot</td></tr>
<tr><td><b>beep</b></td><td>play a beep</td></tr>
</table>

<h2>Variables &amp; math</h2>
<table cellpadding="4">
<tr><td><b>set score to 0</b></td><td>make / overwrite a variable</td></tr>
<tr><td><b>change score by 1</b></td><td>add (negative subtracts)</td></tr>
<tr><td><b>+ - * / mod</b></td><td>math; <b>+</b> also joins text</td></tr>
<tr><td><b>round x, abs x</b></td><td>rounding and absolute value</td></tr>
<tr><td><b>random 1 to 10</b></td><td>surprise number between two numbers</td></tr>
</table>

<h2>Deciding</h2>
<p><b>if ... then / else if ... then / else / end</b></p>
<p>Compare with <b>= &gt; &lt; &gt;= &lt;=</b>, <b>is</b>,
<b>is not</b>. Combine with <b>and</b>, <b>or</b>, <b>not</b>.
True/false values are written <b>true</b> and <b>false</b>.</p>

<h2>Loops</h2>
<table cellpadding="4">
<tr><td><b>repeat 10 times ... end</b></td><td>fixed number of loops</td></tr>
<tr><td><b>repeat until x = 5 ... end</b></td><td>loop until true</td></tr>
<tr><td><b>forever ... end</b></td><td>loop until Stop</td></tr>
<tr><td><b>stop loop</b></td><td>jump out of the current loop</td></tr>
<tr><td><b>stop program</b></td><td>end everything</td></tr>
<tr><td><b>wait 0.5</b></td><td>pause (seconds)</td></tr>
</table>

<h2>Your own commands</h2>
<pre>teach square length
  repeat 4 times
    move length
    turn 90
  end
end

do square 50</pre>
<p>Inputs are local to the command. Commands can even <b>do</b>
themselves — that's recursion (see the Fractal Tree example).</p>

<h2>Moving (the stage is like Scratch)</h2>
<p>(0,0) is the center. x grows right, y grows <b>up</b>.
Heading 0 points up; <b>turn</b> goes clockwise.</p>
<table cellpadding="4">
<tr><td><b>move 100</b> / <b>back 100</b></td><td>walk forward / backward</td></tr>
<tr><td><b>turn 90</b> / <b>turn left 90</b></td><td>rotate</td></tr>
<tr><td><b>point 90</b></td><td>face a direction (0 up, 90 right)</td></tr>
<tr><td><b>goto 0 0</b> / <b>home</b></td><td>jump to a spot / to the center</td></tr>
<tr><td><b>hide</b> / <b>show</b></td><td>invisible / visible</td></tr>
<tr><td><b>size 150</b></td><td>sprite size in percent</td></tr>
<tr><td><b>stamp</b></td><td>leave a Sparky sticker</td></tr>
<tr><td><b>speed 8</b></td><td>1 slow ... 10 instant</td></tr>
</table>

<h2>Sounds</h2>
<table cellpadding="4">
<tr><td><b>play "pop"</b></td><td>sound effects: pop, ding, boing, laser,
drum, tada, jump</td></tr>
<tr><td><b>play note 4</b></td><td>notes 1–14 = two do-re-mi octaves</td></tr>
<tr><td><b>play note 4 for 0.5</b></td><td>hold the note — chain notes
into songs (see the Music example)</td></tr>
<tr><td><b>beep</b></td><td>the classic</td></tr>
</table>

<h2>Drawing</h2>
<table cellpadding="4">
<tr><td><b>pen down</b> / <b>pen up</b></td><td>draw while moving, or not</td></tr>
<tr><td><b>pen color "red"</b></td><td>also: orange yellow green blue purple
pink brown black white gray cyan magenta lime navy cream ink —
or "#ff8800"</td></tr>
<tr><td><b>pen size 5</b></td><td>line thickness</td></tr>
<tr><td><b>background "ink"</b></td><td>paint the whole stage</td></tr>
<tr><td><b>clear</b></td><td>erase all drawings</td></tr>
</table>

<h2>Numbers with a minus</h2>
<p><b>goto 10 -60</b> and <b>move -50</b> work the way you'd hope.
Write subtraction with spaces (<b>5 - 3</b>) or none (<b>5-3</b>).</p>
"""
