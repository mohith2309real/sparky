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
        ("ask", 'ask "What\'s your name?" into name',
         "Ask a question and keep the answer in a variable."),
        ("write", 'write "hi"', "Write text on the stage with the pen color."),
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
        ("point", "point 0", "Face a direction: 0 up, 90 right, 180 down."),
        ("home", "home", "Back to the center, facing up."),
        ("hide / show", "hide", "Make Sparky invisible (show brings it back)."),
        ("size", "size 150", "Make Sparky bigger or smaller (100 = normal)."),
        ("stamp", "stamp", "Leave a copy of Sparky on the stage."),
    ]),
    ("PEN", "accent3", [
        ("pen down", "pen down", "Start drawing while moving."),
        ("pen up", "pen up", "Stop drawing while moving."),
        ("pen color", 'pen color "blue"',
         'Colors: red orange yellow green blue purple pink black... or "#ff8800".'),
        ("pen size", "pen size 5", "How thick the pen line is."),
        ("background", 'background "ink"', "Paint the whole stage."),
        ("clear", "clear", "Erase every drawing on the stage."),
    ]),
    ("CONTROL", "accent", [
        ("repeat", "repeat 10 times\n  move 20\n  turn 36\nend",
         "Do something again and again."),
        ("repeat until", 'repeat until score = 10\n  change score by 1\nend',
         "Keep going until something becomes true."),
        ("count with for", "for i from 1 to 10\n  say i\nend",
         "Count from one number to another."),
        ("forever", "forever\n  turn 5\nend",
         "Loop until you press Stop (or use stop loop)."),
        ("if", 'if score > 5 then\n  say "wow!"\nend',
         "Only do it when something is true."),
        ("if / else", 'if score > 5 then\n  say "wow!"\nelse\n  say "keep going!"\nend',
         "Do one thing or the other."),
        ("wait", "wait 1", "Pause for that many seconds."),
        ("stop loop", "stop loop", "Jump out of the loop you're in."),
        ("stop program", "stop program", "End the whole program."),
        ("speed", "speed 8", "How fast Sparky moves: 1 slow, 10 instant."),
    ]),
    ("LISTS", "accent3", [
        ("make a list", 'set pets to ["cat", "dog"]', "A list holds many things in order."),
        ("add to list", 'add "fish" to pets', "Put something at the end of a list."),
        ("remove from list", 'remove "cat" from pets', "Take something out of a list."),
        ("item of list", "say item 1 of pets", "Items count from 1."),
        ("for each", "for each pet in pets\n  say pet\nend", "Do something with every item."),
        ("length", "say length(pets)", "How many items (or letters)."),
    ]),
    ("VARIABLES", "accent2", [
        ("set", "set score to 0", "Make a variable (a box that holds a value)."),
        ("change", "change score by 1", "Add to a variable (or subtract)."),
        ("random", "set lucky to random 1 to 10",
         "A surprise number between two numbers."),
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
        self.build(palette)

    def build(self, palette):
        title = QLabel("BLOCKS")
        title.setObjectName("SectionTitle")
        self.layout_.addWidget(title)

        font = QFont()
        font.setFamilies(HEADING_FONTS)
        font.setPointSize(12)
        font.setWeight(QFont.Weight.DemiBold)

        for name, accent_key, blocks in CATEGORIES + self.extra_categories:
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
