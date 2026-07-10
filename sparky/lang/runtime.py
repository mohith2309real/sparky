# Runtimes: how Sparky programs talk to the outside world.
# The interpreter calls these methods; a runtime decides what they mean.
# The console runtime prints things; the IDE runtime draws on the stage.

import sys
import time


class Runtime:
    """Base runtime — graphics calls are quietly ignored (headless)."""

    def say(self, text):
        pass

    def ask(self, prompt):
        return ""

    def bubble(self, text):
        pass

    def line(self, x1, y1, x2, y2, color, width):
        pass

    def sprite(self, x, y, heading, visible, scale):
        pass

    def stamp(self, x, y, heading, scale):
        pass

    def write_text(self, x, y, text, color, scale):
        pass

    def clear(self):
        pass

    def background(self, color):
        pass

    def beep(self):
        pass

    def play_sound(self, name, note, duration):
        pass


class ConsoleRuntime(Runtime):
    """Runs Sparky programs in the terminal: say prints, ask reads input."""

    def say(self, text):
        print(text)

    def ask(self, prompt):
        try:
            return input(prompt + " ")
        except EOFError:
            return None

    def beep(self):
        sys.stdout.write("\a")
        sys.stdout.flush()


def run_console(source, runtime=None, max_steps=None):
    """Parse and run a program in the terminal. Returns the interpreter."""
    from .parser import parse
    from .interpreter import Interpreter

    runtime = runtime or ConsoleRuntime()
    interpreter = Interpreter(parse(source), runtime)
    steps = 0
    for tick in interpreter.run():
        if tick[0] == "wait":
            time.sleep(tick[1])
        steps += 1
        if max_steps is not None and steps >= max_steps:
            break
    return interpreter
