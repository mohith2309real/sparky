# Runtimes: how Sparky programs talk to the outside world.
# The interpreter calls these methods; a runtime decides what they mean.
# The console runtime prints things; the IDE runtime draws on the stage.

import json
import os
import sys
import time
from pathlib import Path


class Runtime:
    """Base runtime — graphics calls are quietly ignored (headless)."""

    def __init__(self):
        self._memory = {}

    def say(self, text):
        pass

    def ask(self, prompt):
        return ""

    def ask_choice(self, prompt, choices):
        """Ask with buttons. Here: the question plus the choices, as text."""
        return self.ask(f"{prompt} ({' / '.join(choices)})")

    def bubble(self, text):
        pass

    def sprite_bubble(self, text, kind, sprite):
        """A speech ("say") or thought ("think") bubble on any sprite; "" clears it."""
        if sprite == "sparky":
            self.bubble(text)

    def line(self, x1, y1, x2, y2, color, width):
        pass

    def pen_line(self, x1, y1, x2, y2, pen):
        """A line with the full pen: color, width, style (solid/dashed/dotted), opacity.
        Runtimes that only draw plain lines get line()."""
        self.line(x1, y1, x2, y2, pen["color"], pen["width"])

    def shape(self, points, closed, pen, fill):
        """A filled or outlined shape: points are stage (x, y) pairs."""
        if not pen or pen.get("width", 0) <= 0:
            return
        pairs = list(zip(points, points[1:] + (points[:1] if closed else [])))
        for (x1, y1), (x2, y2) in pairs:
            self.pen_line(x1, y1, x2, y2, pen)

    def sprite(self, x, y, heading, visible, scale):
        pass

    def sprite_changed(self, sprite):
        """Any sprite moved or changed. Runtimes that only know Sparky himself
        just get the old sprite() call for him."""
        if sprite.name == "sparky":
            self.sprite(sprite.x, sprite.y, sprite.heading, sprite.visible, sprite.scale)

    def stamp(self, x, y, heading, scale):
        pass

    def stamp_sprite(self, snapshot):
        """Stamp any sprite, costume and all (snapshot = Sprite.snapshot())."""
        self.stamp(snapshot["x"], snapshot["y"], snapshot["heading"], snapshot["scale"])

    def write_text(self, x, y, text, color, scale):
        pass

    def write_styled(self, x, y, text, color, scale, style):
        """write with a style: {"size": 30, "bold": True, "italic": True}."""
        self.write_text(x, y, text, color, scale)

    def clear(self):
        pass

    def background(self, color):
        pass

    def backdrop(self, name):
        pass

    def beep(self):
        pass

    def play_sound(self, name, note, duration):
        pass

    def speak(self, text):
        pass

    # ---------- events and sensing ----------

    def events(self):
        """Keys pressed and things clicked since the last call:
        ("key", name) · ("click", sprite name) · ("stage_click", x, y)."""
        return []

    def wants_events(self):
        """True while a program with `when` blocks should keep listening."""
        return False

    def key_down(self, name):
        return False

    def mouse(self):
        return 0.0, 0.0, False

    # ---------- memory between runs ----------

    def save_value(self, name, value):
        self._memory[name] = value

    def load_value(self, name):
        return self._memory.get(name)

    def __getattr__(self, name):
        # runtimes written before Sparky 3 don't call Runtime.__init__
        if name == "_memory":
            self._memory = {}
            return self._memory
        raise AttributeError(name)


def memory_file():
    """Where `save ... as` keeps values between runs (shared by the app and the terminal)."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "Sparky"
    elif sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "Sparky"
    else:
        base = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "sparky"
    return base / "memory.json"


class FileMemory:
    """save/load backed by memory.json."""

    def __init__(self, path=None):
        self.path = Path(path) if path else memory_file()

    def read(self):
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def save(self, name, value):
        data = self.read()
        data[name] = value
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            pass

    def load(self, name):
        return self.read().get(name)


class ConsoleRuntime(Runtime):
    """Runs Sparky programs in the terminal: say prints, ask reads input."""

    def __init__(self):
        super().__init__()
        self.memory = FileMemory()

    def say(self, text):
        print(text)

    def ask(self, prompt):
        try:
            return input(prompt + " ")
        except EOFError:
            return None

    def ask_choice(self, prompt, choices):
        print(prompt)
        for i, choice in enumerate(choices, 1):
            print(f"  {i}. {choice}")
        return self.ask("Your choice:")

    def sprite_bubble(self, text, kind, sprite):
        if kind == "think" and text:
            print(f"({text})")

    def speak(self, text):
        print(f"🔊 {text}")

    def beep(self):
        sys.stdout.write("\a")
        sys.stdout.flush()

    def save_value(self, name, value):
        self.memory.save(name, value)

    def load_value(self, name):
        return self.memory.load(name)


def run_console(source, runtime=None, max_steps=None, base_dir=None):
    """Parse and run a program in the terminal. Returns the interpreter."""
    from .parser import parse
    from .interpreter import Interpreter

    runtime = runtime or ConsoleRuntime()
    interpreter = Interpreter(parse(source), runtime, base_dir=base_dir, source=source)
    steps = 0
    for tick in interpreter.run():
        if tick[0] == "wait":
            time.sleep(tick[1])
        steps += 1
        if max_steps is not None and steps >= max_steps:
            break
    return interpreter
