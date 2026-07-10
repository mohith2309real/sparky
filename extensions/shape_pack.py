# Shape Pack — a sample Sparky extension.
# Copy this file to make your own: change NAME, AUTHOR, and the blocks!

NAME = "Shape Pack"
AUTHOR = "Mohith"


def register(api):
    api.add_blocks("SHAPES", "accent2", [
        ("triangle",
         "repeat 3 times\n  move 80\n  turn 120\nend",
         "Three sides, three turns of 120."),
        ("hexagon",
         "repeat 6 times\n  move 60\n  turn 60\nend",
         "Six sides, six turns of 60."),
        ("star",
         "repeat 5 times\n  move 120\n  turn 144\nend",
         "The famous five-pointed star."),
        ("circle-ish",
         "repeat 36 times\n  move 8\n  turn 10\nend",
         "36 tiny steps make an almost-circle."),
        ("any polygon",
         "teach polygon sides\n  repeat sides times\n    move 60\n"
         "    turn 360 / sides\n  end\nend\n\ndo polygon 8",
         "One command, every shape."),
    ])
