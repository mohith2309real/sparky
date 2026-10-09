# What every Sparky word does, with an example — for hover help, the
# autocomplete list, and "Learn about this" links on errors.

COMMANDS = {
    # talking
    "say": ("Say something in a speech bubble and the console.", 'say "Hello!"'),
    "think": ("Show a thought bubble.", 'think "Hmm..."'),
    "speak": ("Say it out loud with the computer's voice.", 'speak "Hello"'),
    "ask": ("Ask a question and keep the answer in a variable.", 'ask "Your name?" into name'),
    "write": ("Write text on the stage where the sprite is.", 'write "Score: {score}" size 24 bold'),
    # variables
    "set": ("Make a variable, or change what it holds.", "set score to 0"),
    "change": ("Add to a variable (use a minus number to take away).", "change score by 1"),
    "add": ("Put something at the end of a list (or add to a number).", 'add "fish" to pets'),
    "remove": ("Take something out of a list.", 'remove "cat" from pets'),
    "insert": ("Put something into a list at a spot.", 'insert "fish" at 1 in pets'),
    "save": ("Keep a value for next time, even after Sparky closes.", 'save score as "best"'),
    "load": ("Get a saved value back (0 if nothing was saved).", 'load "best" into best'),
    "reset": ("Start the timer from 0 again.", "reset timer"),
    # control
    "repeat": ("Do the lines inside again and again.", "repeat 4 times\n  move 50\n  turn 90\nend"),
    "forever": ("Keep going until you press Stop.", "forever\n  turn 5\nend"),
    "if": ("Only do it when something is true.", 'if score > 5 then\n  say "Wow!"\nend'),
    "else": ("What to do when the if wasn't true.", 'if x > 0 then\n  say "yes"\nelse\n  say "no"\nend'),
    "for": ("Count, or go through every item of a list.", "for i from 1 to 10\n  say i\nend"),
    "wait": ("Pause for some seconds, or until something is true.", "wait 0.5"),
    "stop": ("Jump out of a loop, or end the program.", "stop loop"),
    "try": ("Catch a problem without stopping the program.", 'try\n  say 1 / 0\noops\n  say problem\nend'),
    "oops": ("What to do when the try had a problem. `problem` says what it was.", "oops\n  say problem"),
    "use": ("Use the commands taught in another file.", 'use "shapes.spark"'),
    "end": ("Closes a repeat, forever, if, for, try, when, tell or teach.", "end"),
    # my blocks
    "teach": ("Teach Sparky a new command.", "teach square side\n  repeat 4 times\n    move side\n    turn 90\n  end\nend"),
    "do": ("Use a command you taught.", "do square 50"),
    "give": ("Give back an answer from a command you taught.", "give back n * 2"),
    "return": ("Same as give back.", "return n * 2"),
    # events
    "when": ("Run some lines when something happens.", 'when key "space" pressed\n  say "jump!"\nend'),
    "broadcast": ("Send a message to every `when message` block.", 'broadcast "go"'),
    "next": ("Wait for the next frame (60 a second), or switch costume.", "next frame"),
    # sprites
    "make": ("Make a new sprite.", 'make sprite rocket with costume "rocket"'),
    "tell": ("Give commands to one sprite.", "tell rocket\n  move 50\nend"),
    "costume": ("Change how a sprite looks: a name like cat or rocket, or any emoji.", 'costume "cat"'),
    "ghost": ("See-through: 0 is solid, 100 is invisible.", "ghost 50"),
    "layer": ("Bring a sprite to the front (or the back).", "layer front"),
    "bounce": ("Turn around at the edge of the stage.", "bounce if on edge"),
    "glide": ("Slide smoothly to a spot.", "glide to 100 50 in 2 seconds"),
    "move": ("Walk forward (a minus number walks backward).", "move 100"),
    "back": ("Walk backward.", "back 50"),
    "turn": ("Turn right (or left) by degrees.", "turn left 90"),
    "point": ("Face a direction: 0 up, 90 right, 180 down, 270 left.", "point 90"),
    "goto": ("Jump to a spot. 0 0 is the middle.", "goto 100 -50"),
    "home": ("Back to the middle, facing up.", "home"),
    "hide": ("Make the sprite invisible.", "hide"),
    "show": ("Make the sprite visible again.", "show"),
    "size": ("Make the sprite bigger or smaller (100 is normal).", "size 150"),
    "stamp": ("Leave a copy of the sprite on the stage.", "stamp"),
    "speed": ("How fast: 1 slow, 10 instant.", "speed 8"),
    # drawing
    "pen": ("Draw while moving: pen down, pen up, pen color, pen size, pen style, pen opacity.",
            'pen color "orange"'),
    "clear": ("Erase every drawing.", "clear"),
    "background": ("Paint the whole stage one color.", 'background "ink"'),
    "backdrop": ("A picture behind everything: space, ocean, grass, sunset, night, grid.",
                 'backdrop "space"'),
    "circle": ("A circle around the sprite.", "circle 50"),
    "rectangle": ("A rectangle around the sprite.", "rectangle 80 by 40"),
    "polygon": ("A shape with that many sides.", "polygon 6 sides 40"),
    "star": ("A star with that many points.", "star 5 points 40"),
    "dot": ("A filled dot.", "dot 10"),
    "arc": ("Part of a circle.", "arc 90 radius 50"),
    "fill": ("Fill the shapes that come next.", 'fill color "yellow"'),
    "no": ("Stop filling shapes.", "no fill"),
    # sound
    "play": ("Play a sound (pop, ding, boing, laser, drum, tada, jump) or a note 1–14.",
             "play note 4 for 0.5"),
    "beep": ("A little beep.", "beep"),
    # arduino
    "pin": ("Sparky for Arduino: turn a pin on or off, or set its power 0–255.", "pin 13 on"),
    "servo": ("Sparky for Arduino: turn a servo motor to an angle.", "servo 9 to 90"),
    "buzzer": ("Sparky for Arduino: where the buzzer is plugged in.", "buzzer 8"),
}

FUNCTIONS = {
    "length": ("How many items (or letters).", "length(pets)"),
    "upper": ("TEXT IN CAPITALS.", 'upper("hi")'),
    "lower": ("text in small letters.", 'lower("HI")'),
    "trim": ("Text without spaces at the ends.", 'trim("  hi ")'),
    "capital": ("Text with a capital first letter.", 'capital("sparky")'),
    "text": ("Turn anything into text.", "text(42)"),
    "number": ("Turn text into a number.", 'number("42")'),
    "sqrt": ("Square root.", "sqrt(16)"),
    "power": ("A number times itself, again and again.", "power(2, 10)"),
    "round": ("Round to a whole number, or to some decimal places.", "round(3.14159, 2)"),
    "abs": ("Without the minus sign.", "abs(-5)"),
    "floor": ("Round down.", "floor(3.7)"),
    "ceil": ("Round up.", "ceil(3.2)"),
    "log": ("How many 10s multiply to make it.", "log(1000)"),
    "ln": ("The natural logarithm.", "ln(10)"),
    "clamp": ("Keep a number between two others.", "clamp(x, 0, 100)"),
    "sin": ("Sine (degrees).", "sin(30)"),
    "cos": ("Cosine (degrees).", "cos(60)"),
    "tan": ("Tangent (degrees).", "tan(45)"),
    "min": ("The smallest.", "min(3, 7, 1)"),
    "max": ("The biggest.", "max(scores)"),
    "sum": ("All the numbers in a list added up.", "sum([1, 2, 3])"),
    "distance": ("How far the sprite is from a spot.", "distance(0, 0)"),
    "angle": ("Which way to point to face a spot.", "angle(100, 50)"),
    "rgb": ("A color from red, green and blue (0–255 each).", "rgb(255, 136, 0)"),
    "join": ("Join a list into text.", 'join(pets, ", ")'),
    "split": ("Split text into a list.", 'split("a b c")'),
    "contains": ("true if it's in the list or text.", 'contains(pets, "cat")'),
    "replace": ("Swap words in text.", 'replace("I like cats", "cats", "dogs")'),
    "begins": ("true if the text begins with it.", 'begins("hello", "he")'),
    "ends": ("true if the text ends with it.", 'ends("hello", "lo")'),
    "find": ("Where something is in the text (0 if it isn't).", 'find("banana", "nan")'),
    "words": ("The words of some text, as a list.", 'words("a big dog")'),
    "letters": ("The letters of some text, as a list.", 'letters("abc")'),
    "pick": ("A random item.", "pick(pets)"),
    "reverse": ("Backwards.", 'reverse("abc")'),
    "sort": ("In order.", "sort([3, 1, 2])"),
    "index": ("Where an item is in a list (0 if it isn't).", 'index(pets, "dog")'),
    "slice": ("Some of the items, from one spot to another.", "slice(pets, 2, 3)"),
    "range": ("A list of numbers.", "range(1, 10)"),
    "shuffle": ("The list in a random order.", "shuffle(cards)"),
    "unique": ("The list without repeats.", "unique([1, 1, 2])"),
    "count": ("How many times something is in it.", "count(rolls, 6)"),
    "keys": ("The field names of a record.", "keys(pet)"),
    "xpos": ("The sprite's x.", "xpos()"),
    "ypos": ("The sprite's y.", "ypos()"),
    "direction": ("Which way the sprite points.", "direction()"),
}

VALUES = {
    "timer": ("Seconds since the program started (or reset timer).", "say timer"),
    "pi": ("3.14159…", "say pi * 2"),
    "hour": ("The hour now (0–23).", "say hour"),
    "minute": ("The minute now.", "say minute"),
    "second": ("The second now.", "say second"),
    "today": ("Today's date.", "say today"),
    "weekday": ("Today's day, like Friday.", "say weekday"),
    "problem": ("Inside oops: what went wrong.", "say problem"),
    "random": ("A surprise number between two numbers, or a random color.", "random 1 to 6"),
    "touching": ("true when the sprite touches another sprite, the edge, or the mouse.",
                 "if touching edge then"),
    "mouse": ("mouse x, mouse y, mouse down.", "goto mouse x mouse y"),
    "key": ('true while a key is held down.', 'if key "left" down then'),
    "item": ("One item of a list (item -1 is the last).", "item 1 of pets"),
    "read": ("Sparky for Arduino: read a pin (A0–A5 give 0–1023).", "read pin A0"),
}


def lookup(word):
    """(what it does, example) for a word, or None."""
    word = word.lower()
    return COMMANDS.get(word) or FUNCTIONS.get(word) or VALUES.get(word)


def tooltip_html(word):
    info = lookup(word)
    if info is None:
        return None
    text, example = info
    example_html = example.replace("&", "&amp;").replace("<", "&lt;").replace("\n", "<br>") \
        .replace("  ", "&nbsp;&nbsp;")
    return (f"<b>{word}</b> — {text}<br><span style='font-family: monospace'>{example_html}</span>")


# which lesson teaches the fix for an error (words in the message -> lesson title start)
ERROR_LESSONS = [
    (("variable called", "make it with: set"), "Variables"),
    (("repeat", "times", "loop"), "Loops"),
    (("never found its", "nothing to close", '"end"'), "Loops"),
    (("then", "if", "else"), "Making choices"),
    (("teach", "give back", "command", "input"), "Your own commands"),
    (("list", "item"), "Lists"),
    (("color",), "Drawing"),
    (("text starts with", "quote"), "Talking"),
]
