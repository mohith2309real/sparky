# The block palette: Scratch-style clickable blocks down the left side.
# Clicking a block types real Sparky code into the editor at the cursor —
# kids click their way to a program, then start editing the text themselves.

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QLabel, QPushButton, QScrollArea, QVBoxLayout,
                             QWidget)

from .theme import HEADING_FONTS

# (category, accent-key, [(label, snippet, tooltip), ...])
CATEGORIES = [
    ("TALK", "accent", [
        ("say", 'say "hello!"', "Make Sparky say something."),
        ("say for 2 seconds", 'say "hello!" for 2 seconds', "Say it, then the bubble goes away."),
        ("think", 'think "Hmm..."', "A thought bubble instead of a speech bubble."),
        ("speak out loud", 'speak "Hello!"', "Say it out loud with the computer's voice."),
        ("ask", 'ask "What\'s your name?" into name',
         "Ask a question and keep the answer in a variable."),
        ("ask for a number", 'ask number "How old are you?" into age',
         "Keeps asking until the answer is a number."),
        ("ask with buttons", 'ask "Pick one" choices ["cat", "dog"] into pet',
         "Shows the choices as buttons."),
        ("text with {names}", 'say "Hi {name}! You are {age} years old."',
         "Put a name or a sum in braces to drop its value into the text."),
        ("write", 'write "hi"', "Write text on the stage with the pen color."),
        ("write big and bold", 'write "Score: {score}" size 30 bold', "Text size, bold, italic."),
    ]),
    ("EVENTS", "accent2", [
        ("when key pressed", 'when key "space" pressed\n  say "jump!"\nend',
         "Runs every time that key is pressed. Click the stage first so it hears the keys."),
        ("when clicked", 'when clicked\n  say "ouch!"\nend', "Runs when you click Sparky."),
        ("when stage clicked", 'when stage clicked\n  goto mouse x mouse y\nend',
         "Runs when you click an empty spot on the stage."),
        ("broadcast", 'broadcast "go"', "Send a message to every when message block."),
        ("when message", 'when message "go"\n  say "Let\'s go!"\nend', "Runs when that message is sent."),
        ("game loop", 'forever\n  if key "right" down then\n    move 5\n  end\n  next frame\nend',
         "next frame keeps games smooth at 60 frames a second."),
    ]),
    ("SOUND", "accent3", [
        ("play sound", 'play "pop"',
         "Sounds: pop, ding, boing, laser, drum, tada, jump."),
        ("play note", "play note 4 for 0.5",
         "Notes 1–14 are two do-re-mi octaves. Chain them into songs!"),
        ("beep", "beep", "Play a little beep."),
    ]),
    ("MOVE", "accent2", [
        ("move", "move 100", "Walk forward. Negative numbers walk backward."),
        ("turn right", "turn 90", "Turn clockwise by degrees."),
        ("turn left", "turn left 90", "Turn counter-clockwise by degrees."),
        ("go to", "goto 0 0", "Jump to a spot. (0,0) is the center."),
        ("glide", "glide to 100 50 in 2 seconds", "Slide smoothly to a spot."),
        ("point", "point 0", "Face a direction: 0 up, 90 right, 180 down."),
        ("bounce", "bounce if on edge", "Turn around when you hit the edge of the stage."),
        ("home", "home", "Back to the center, facing up."),
    ]),
    ("SPRITES", "accent", [
        ("make a sprite", 'make sprite rocket with costume "rocket"',
         "A new character on the stage. Costumes: cat, dog, rocket... or any emoji."),
        ("tell a sprite", "tell rocket\n  move 50\nend", "Give commands to one sprite."),
        ("costume", 'costume "cat"', "Change how a sprite looks (try the Costumes button)."),
        ("next costume", "next costume", "Switch to the next built-in costume."),
        ("touching", 'if touching rocket then\n  say "bump!"\nend',
         "true when two sprites touch. Also: touching edge, touching mouse."),
        ("distance to", "say distance to rocket", "How far away another sprite is."),
        ("ghost", "ghost 50", "See-through: 0 is solid, 100 is invisible."),
        ("layer", "layer front", "Bring a sprite to the front (or layer back)."),
        ("hide / show", "hide", "Make a sprite invisible (show brings it back)."),
        ("size", "size 150", "Make a sprite bigger or smaller (100 = normal)."),
        ("stamp", "stamp", "Leave a copy of the sprite on the stage."),
    ]),
    ("PEN", "accent3", [
        ("pen down", "pen down", "Start drawing while moving."),
        ("pen up", "pen up", "Stop drawing while moving."),
        ("pen color", 'pen color "blue"',
         'Colors: red orange yellow green blue purple pink black... or "#ff8800" or rgb(255, 136, 0).'),
        ("rainbow pen", "pen color rainbow", "Every line a new color."),
        ("pen size", "pen size 5", "How thick the pen line is."),
        ("pen style", "pen style dashed", "solid, dashed or dotted."),
        ("pen opacity", "pen opacity 50", "See-through lines: 100 is solid."),
        ("background", 'background "ink"', "Paint the whole stage."),
        ("backdrop", 'backdrop "space"', "Backdrops: space, ocean, grass, sunset, night, grid."),
        ("clear", "clear", "Erase every drawing on the stage."),
    ]),
    ("SHAPES", "accent", [
        ("circle", "circle 50", "A circle around the sprite."),
        ("rectangle", "rectangle 80 by 40", "A rectangle around the sprite."),
        ("polygon", "polygon 6 sides 40", "Triangles, hexagons... any number of sides."),
        ("star", "star 5 points 40", "A star."),
        ("dot", "dot 10", "A filled dot."),
        ("arc", "arc 90 radius 50", "Part of a circle."),
        ("fill color", 'fill color "yellow"', "Shapes after this are filled in."),
        ("no fill", "no fill", "Shapes after this are just outlines."),
    ]),
    ("CONTROL", "accent", [
        ("repeat", "repeat 10 times\n  move 20\n  turn 36\nend",
         "Do something again and again."),
        ("repeat until", 'repeat until score = 10\n  change score by 1\nend',
         "Keep going until something becomes true."),
        ("repeat while", "repeat while score < 10\n  change score by 1\nend",
         "Keep going while something is true."),
        ("count with for", "for i from 1 to 10\n  say i\nend",
         "Count from one number to another."),
        ("forever", "forever\n  turn 5\nend",
         "Loop until you press Stop (or use stop loop)."),
        ("if", 'if score > 5 then\n  say "wow!"\nend',
         "Only do it when something is true."),
        ("if / else", 'if score > 5 then\n  say "wow!"\nelse\n  say "keep going!"\nend',
         "Do one thing or the other."),
        ("wait", "wait 1", "Pause for that many seconds."),
        ("wait until", "wait until timer > 3", "Pause until something becomes true."),
        ("try / oops", 'try\n  say 10 / 0\noops\n  say "Something went wrong: " + problem\nend',
         "Catch a problem without stopping the program."),
        ("use another file", 'use "shapes.spark"', "Use the commands taught in another file."),
        ("stop loop", "stop loop", "Jump out of the loop you're in."),
        ("stop program", "stop program", "End the whole program."),
        ("speed", "speed 8", "How fast Sparky moves: 1 slow, 10 instant."),
    ]),
    ("LISTS", "accent3", [
        ("make a list", 'set pets to ["cat", "dog"]', "A list holds many things in order."),
        ("add to list", 'add "fish" to pets', "Put something at the end of a list."),
        ("insert into list", 'insert "fish" at 1 in pets', "Put something at a spot in the list."),
        ("remove from list", 'remove "cat" from pets', "Take something out of a list."),
        ("item of list", "say item 1 of pets", "Items count from 1. item -1 is the last one."),
        ("for each", "for each pet in pets\n  say pet\nend", "Do something with every item."),
        ("length", "say length(pets)", "How many items (or letters)."),
    ]),
    ("RECORDS", "accent2", [
        ("make a record", 'set pet to {name: "Rex", age: 3}', "A record keeps named facts together."),
        ("field of a record", "say name of pet", "Read one field."),
        ("set a field", "set age of pet to 4", "Change one field."),
    ]),
    ("VARIABLES", "accent2", [
        ("set", "set score to 0", "Make a variable (a box that holds a value)."),
        ("change", "change score by 1", "Add to a variable (or subtract)."),
        ("random", "set lucky to random 1 to 10",
         "A surprise number between two numbers."),
        ("save for next time", 'save score as "best"', "Keep a value even after Sparky closes."),
        ("load it back", 'load "best" into best', "Get a saved value back (0 if there isn't one)."),
        ("timer", "reset timer\nwait 2\nsay timer", "Seconds since the program started (or reset timer)."),
    ]),
    ("ARDUINO", "accent2", [
        ("pin on", "pin 13 on", "Turn on whatever is plugged into pin 13 (like an LED)."),
        ("pin off", "pin 13 off", "Turn it off again."),
        ("pin to (fade)", "pin 9 to 128", "0 is off, 255 is full power. Needs a ~ pin."),
        ("read a pin", "set light to read pin A0", "A0–A5 read 0–1023; other pins read 0 or 1."),
        ("servo", "servo 9 to 90", "Turn a servo motor to an angle from 0 to 180."),
        ("buzzer", "buzzer 8\nplay note 1 for 0.5", "Where the buzzer is, then play notes."),
        ("blink forever", "forever\n  pin 13 on\n  wait 0.5\n  pin 13 off\n  wait 0.5\nend",
         "The first program everyone uploads. Press Upload with a board plugged in."),
    ]),
    ("MY BLOCKS", "accent3", [
        ("teach", 'teach dance\n  turn 20\n  turn left 20\nend',
         "Teach Sparky a brand new command."),
        ("teach with input", 'teach square length\n  repeat 4 times\n'
         '    move length\n    turn 90\n  end\nend',
         "New commands can take inputs, like a square's side length."),
        ("do", "do dance", "Use a command you taught."),
        ("teach with answer", "teach double n\n  give back n * 2\nend\n\nsay double(21)",
         "A command that gives back an answer you can use."),
    ]),
]


# blocks for Arduino sketches (.ino): real Arduino code
ARDUINO_CATEGORIES = [
    ("SKETCH", "accent", [
        ("setup and loop", "void setup() {\n  \n}\n\nvoid loop() {\n  \n}",
         "Every sketch has these two: setup runs once, loop runs forever."),
        ("a variable", "int ledPin = 13;", "A box for a whole number. Put it at the top."),
        ("a function", "void blinkTwice() {\n  \n}", "Your own command."),
    ]),
    ("PINS", "accent2", [
        ("pin is an output", "pinMode(13, OUTPUT);", "In setup: this pin controls an LED or motor."),
        ("pin is a button", "pinMode(2, INPUT_PULLUP);", "In setup: read a button (pressed = LOW)."),
        ("turn on", "digitalWrite(13, HIGH);", "Turn the pin on."),
        ("turn off", "digitalWrite(13, LOW);", "Turn the pin off."),
        ("fade", "analogWrite(9, 128);", "0 to 255 — needs a ~ pin."),
        ("read a button", "if (digitalRead(2) == LOW) {\n  \n}", "Do something while pressed."),
        ("read a sensor", "int value = analogRead(A0);", "0 to 1023 from A0–A5."),
    ]),
    ("TIME", "accent3", [
        ("wait", "delay(1000);", "Wait 1000 milliseconds (1 second)."),
        ("time since start", "unsigned long now = millis();", "Milliseconds since the board started."),
    ]),
    ("CONTROL", "accent", [
        ("if", "if (value > 500) {\n  \n}", "Only when something is true."),
        ("if / else", "if (value > 500) {\n  \n} else {\n  \n}", "One thing or the other."),
        ("repeat", "for (int i = 0; i < 10; i++) {\n  \n}", "Do something 10 times."),
        ("while", "while (digitalRead(2) == HIGH) {\n  \n}", "Keep going while true."),
    ]),
    ("SERIAL", "accent2", [
        ("start serial", "Serial.begin(9600);", "In setup: talk to the computer at 9600 baud."),
        ("print", 'Serial.println("Hello!");', "Shows up in the Serial Monitor."),
        ("print a value", "Serial.println(value);", "Numbers also show up in the Plotter."),
        ("read a message", "if (Serial.available()) {\n  String text = Serial.readStringUntil('\\n');\n}",
         "Read what you type in the Serial Monitor."),
    ]),
    ("SOUND & MOTORS", "accent3", [
        ("beep", "tone(8, 440, 200);", "Play 440 Hz for 200 ms on a buzzer on pin 8."),
        ("silence", "noTone(8);", "Stop the sound."),
        ("servo", "#include <Servo.h>\nServo arm;\n// in setup: arm.attach(9);\n// then: arm.write(90);",
         "Servo motors turn to an angle."),
    ]),
]


class BlockPalette(QScrollArea):
    def __init__(self, palette, on_insert, extra_categories=(), parent=None):
        super().__init__(parent)
        self.on_insert = on_insert
        self.extra_categories = list(extra_categories)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.inner = QWidget()
        self.inner.setObjectName("BlockPanel")
        self.layout_ = QVBoxLayout(self.inner)
        self.layout_.setContentsMargins(10, 6, 10, 14)
        self.layout_.setSpacing(5)
        self.setWidget(self.inner)

        self.buttons = []
        self.palette = palette
        self.kind = "sparky"
        self.build(palette)

    def set_language(self, lang_id):
        """Arduino sketches get Arduino blocks; everything else gets Sparky blocks."""
        kind = "arduino" if lang_id == "arduino" else "sparky"
        if kind == self.kind:
            return
        self.kind = kind
        while self.layout_.count():
            item = self.layout_.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
                item.widget().deleteLater()
        self.buttons = []
        self.build(self.palette)

    def build(self, palette):
        title = QLabel("BLOCKS")
        title.setObjectName("SectionTitle")
        self.layout_.addWidget(title)

        font = QFont()
        font.setFamilies(HEADING_FONTS)
        font.setPointSize(12)
        font.setWeight(QFont.Weight.DemiBold)

        categories = ARDUINO_CATEGORIES if self.kind == "arduino" else \
            CATEGORIES + self.extra_categories
        for name, accent_key, blocks in categories:
            header = QLabel(name)
            header.setObjectName("SectionTitle")
            self.layout_.addWidget(header)
            for label, snippet, tip in blocks:
                button = QPushButton(label)
                button.setFont(font)
                button.setToolTip(f"{tip}\n\n{snippet}")
                button.setCursor(Qt.CursorShape.PointingHandCursor)
                button.clicked.connect(
                    lambda _=False, s=snippet: self.on_insert(s))
                button.accent_key = accent_key
                self.layout_.addWidget(button)
                self.buttons.append(button)
        self.layout_.addStretch(1)
        self.apply_palette(palette)

    def apply_palette(self, palette):
        self.palette = palette
        for button in self.buttons:
            accent = palette[button.accent_key]
            button.setStyleSheet(f"""
                QPushButton {{
                    background: {accent};
                    color: #ffffff;
                    border: none;
                    border-radius: 10px;
                    padding: 8px 12px;
                    text-align: left;
                }}
                QPushButton:hover {{
                    background: {palette['text']};
                    color: {palette['bg']};
                }}
            """)
