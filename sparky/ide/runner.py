# Running programs inside the IDE.
#
# The interpreter runs on a worker thread so the window never freezes,
# even during "forever" loops. It talks back through Qt signals (console,
# errors, line highlights) and writes drawings straight into the StageModel.
# "ask" blocks the worker on a queue until the kid types an answer.

import queue
import time

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication

from ..lang import SparkyError, parse, Interpreter, Runtime
from ..lang.runtime import FileMemory


class GuiRuntime(Runtime):
    def __init__(self, thread, model):
        super().__init__()
        self.thread = thread
        self.model = model
        self.answers = queue.Queue()
        self.memory = FileMemory()

    def say(self, text):
        self.thread.sig_say.emit(text)

    def ask(self, prompt):
        self.thread.sig_ask.emit(prompt)
        answer = self.answers.get()   # blocks until the input line replies
        return answer                  # None means "we were stopped"

    def ask_choice(self, prompt, choices):
        self.thread.sig_choice.emit(prompt, list(choices))
        return self.answers.get()

    def bubble(self, text):
        self.model.set_bubble("sparky", "say", text)

    def sprite_bubble(self, text, kind, sprite):
        self.model.set_bubble(sprite, kind, text)

    def line(self, x1, y1, x2, y2, color, width):
        self.model.add_line(x1, y1, x2, y2, {"color": color, "width": width})

    def pen_line(self, x1, y1, x2, y2, pen):
        self.model.add_line(x1, y1, x2, y2, pen)

    def shape(self, points, closed, pen, fill):
        self.model.add_shape(points, closed, pen, fill)

    def sprite_changed(self, sprite):
        self.model.set_sprite(sprite.snapshot())

    def stamp_sprite(self, snapshot):
        self.model.add_stamp(snapshot)

    def write_styled(self, x, y, text, color, scale, style):
        self.model.add_text(x, y, text, color, scale, style)

    def write_text(self, x, y, text, color, scale):
        self.model.add_text(x, y, text, color, scale)

    def clear(self):
        self.model.clear_drawings()

    def background(self, color):
        self.model.set_background(color)

    def backdrop(self, name):
        self.model.set_backdrop(name)

    def beep(self):
        QApplication.beep()

    def play_sound(self, name, note, duration):
        self.thread.sig_sound.emit(name, float(note), float(duration))

    def play_music(self, instrument, notes, duration):
        self.thread.sig_music.emit(instrument, list(notes), float(duration))

    def speak(self, text):
        self.thread.sig_speak.emit(text)

    # keys, clicks and the mouse come from the stage window
    def events(self):
        return self.model.drain_events()

    def wants_events(self):
        return True

    def key_down(self, name):
        if name == "any":
            return bool(self.model.keys_down)
        return name in self.model.keys_down

    def mouse(self):
        return self.model.mouse

    def save_value(self, name, value):
        self.memory.save(name, value)

    def load_value(self, name):
        return self.memory.load(name)


class RunnerThread(QThread):
    sig_say = pyqtSignal(str)
    sig_ask = pyqtSignal(str)
    sig_choice = pyqtSignal(str, list)  # question, choices (shown as buttons)
    sig_speak = pyqtSignal(str)
    sig_listening = pyqtSignal()        # the main program ended; `when` blocks keep listening
    sig_stats = pyqtSignal(int, float)  # steps run, seconds taken (just before done)
    sig_hint = pyqtSignal(str)          # a friendly tip, like "this loop never waits"
    sig_sound = pyqtSignal(str, float, float)  # name ("" = note), note, secs
    sig_music = pyqtSignal(str, list, float)
    sig_line = pyqtSignal(int)          # line currently running
    sig_error = pyqtSignal(str, int)    # friendly message, line (0 = unknown)
    sig_done = pyqtSignal(bool)         # True if it finished without errors
    sig_paused = pyqtSignal(int)        # paused (by Pause or Step) at this line
    sig_resumed = pyqtSignal()

    def __init__(self, source, model, start_speed, parent=None, base_dir=None, breakpoints=(), commands=None):
        super().__init__(parent)
        self.source = source
        self.base_dir = base_dir
        self.commands = dict(commands or {})
        self.breakpoints = frozenset(breakpoints)
        self.model = model
        self.start_speed = start_speed
        self.runtime = GuiRuntime(self, model)
        self.setStackSize(64 * 1024 * 1024)  # room for deep recursion
        self.interpreter = None
        self._stop = False
        self._paused = False
        self._stepping = False       # run to the next line, then pause again
        self._pause_line = 0

    def stop(self):
        self._stop = True
        self._paused = False
        self.runtime.answers.put(None)  # unblock a pending ask

    def pause(self):
        self._paused = True

    def resume(self):
        self._stepping = False
        self._paused = False
        self.sig_resumed.emit()

    def step(self):
        """Run until the next line starts, then pause there."""
        self._stepping = True
        self._paused = True

    def is_paused(self):
        return self._paused and not self._stepping

    def wait_if_paused(self, line):
        if not self._paused:
            return
        if self._stepping:
            if line == self._pause_line:
                return
            self._stepping = False
        self._pause_line = line
        self.sig_line.emit(line)
        self.sig_paused.emit(line)
        while self._paused and not self._stepping and not self._stop:
            time.sleep(0.02)

    def set_breakpoints(self, lines):
        self.breakpoints = frozenset(lines)
        if self.interpreter is not None:
            self.interpreter.break_lines = self.breakpoints

    def set_speed(self, value):
        if self.interpreter is not None:
            self.interpreter.speed = value

    def visual_delay(self):
        speed = self.interpreter.speed
        if speed >= 10:
            return 0.0
        return ((10 - speed) ** 1.5) * 0.0045

    def nap(self, seconds):
        """Sleep in slices so Stop stays snappy."""
        end = time.monotonic() + seconds
        while not self._stop:
            remaining = end - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(0.05, remaining))

    def run(self):
        try:
            program = parse(self.source, self.commands)
            self.interpreter = Interpreter(program, self.runtime, base_dir=self.base_dir,
                                           source=self.source, commands=self.commands)
            self.interpreter.break_lines = self.breakpoints
            self.interpreter.speed = self.start_speed
        except SparkyError as err:
            self.sig_error.emit(err.pretty(), err.line or 0)
            self.sig_done.emit(False)
            return

        last_line = 0
        last_line_emit = 0.0
        steps = 0
        listening = False
        started = time.monotonic()
        quiet = 0              # ticks since the program last drew or waited
        ticks = 0
        hinted = False
        self.model.keys_down.clear()
        self.model.listening = True
        try:
            for tick in self.interpreter.run():
                if self._stop:
                    break
                ticks += 1
                line = tick[-1]
                if line is None:
                    # the scheduler waiting for keys, clicks or other scripts
                    if not listening and self.interpreter.handlers and not any(
                            t.handler is None and not t.done for t in self.interpreter.threads):
                        listening = True
                        self.sig_listening.emit()
                    self.nap(tick[1])
                    continue
                if tick[0] == "break":
                    if not (self._stepping and line == self._pause_line):
                        self._stepping = False
                        self._paused = True
                    self.wait_if_paused(line)
                    if self._stop:
                        break
                    continue
                if self._paused:
                    self.wait_if_paused(line)
                    if self._stop:
                        break
                now = time.monotonic()
                # highlight the running line, but don't flood the UI
                if line != last_line and now - last_line_emit > 0.03:
                    last_line = line
                    last_line_emit = now
                    self.sig_line.emit(line)

                kind = tick[0]
                if kind in ("wait", "visual"):
                    quiet = 0
                else:
                    quiet += 1
                    if quiet > 400000 and not hinted and time.monotonic() - started > 2:
                        hinted = True
                        self.sig_hint.emit(
                            f"Line {line}: this loop never waits, so nothing can move on the "
                            "stage while it runs. Add wait 0.1 or next frame inside it.")
                if kind == "wait":
                    self.nap(tick[1])
                elif kind == "visual":
                    delay = self.visual_delay()
                    if delay:
                        self.nap(delay)
                else:
                    steps += 1
                    if steps % 500 == 0:
                        time.sleep(0.001)  # let the UI breathe in hot loops
        except SparkyError as err:
            self.model.listening = False
            self.sig_error.emit(err.pretty(), err.line or 0)
            self.sig_done.emit(False)
            return
        except Exception as err:  # never show kids a traceback
            self.model.listening = False
            self.sig_error.emit(
                f"Oops! Something surprised me deep inside: {err}", 0)
            self.sig_done.emit(False)
            return
        self.model.listening = False
        self.sig_stats.emit(ticks, time.monotonic() - started)
        self.sig_done.emit(True)

    def answer(self, text):
        self.runtime.answers.put(text)
