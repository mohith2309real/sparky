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


class GuiRuntime(Runtime):
    def __init__(self, thread, model):
        self.thread = thread
        self.model = model
        self.answers = queue.Queue()

    def say(self, text):
        self.thread.sig_say.emit(text)

    def ask(self, prompt):
        self.thread.sig_ask.emit(prompt)
        answer = self.answers.get()   # blocks until the input line replies
        return answer                  # None means "we were stopped"

    def bubble(self, text):
        self.model.set_bubble(text)

    def line(self, x1, y1, x2, y2, color, width):
        self.model.add_segment(x1, y1, x2, y2, color, width)

    def sprite(self, x, y, heading, visible, scale):
        self.model.set_sprite(x, y, heading, visible, scale)

    def stamp(self, x, y, heading, scale):
        self.model.add_stamp(x, y, heading, scale)

    def write_text(self, x, y, text, color, scale):
        self.model.add_text(x, y, text, color, scale)

    def clear(self):
        self.model.clear_drawings()

    def background(self, color):
        self.model.set_background(color)

    def beep(self):
        QApplication.beep()

    def play_sound(self, name, note, duration):
        self.thread.sig_sound.emit(name, float(note), float(duration))


class RunnerThread(QThread):
    sig_say = pyqtSignal(str)
    sig_ask = pyqtSignal(str)
    sig_sound = pyqtSignal(str, float, float)  # name ("" = note), note, secs
    sig_line = pyqtSignal(int)          # line currently running
    sig_error = pyqtSignal(str, int)    # friendly message, line (0 = unknown)
    sig_done = pyqtSignal(bool)         # True if it finished without errors

    def __init__(self, source, model, start_speed, parent=None):
        super().__init__(parent)
        self.source = source
        self.model = model
        self.start_speed = start_speed
        self.runtime = GuiRuntime(self, model)
        self.interpreter = None
        self._stop = False

    def stop(self):
        self._stop = True
        self.runtime.answers.put(None)  # unblock a pending ask

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
            program = parse(self.source)
            self.interpreter = Interpreter(program, self.runtime)
            self.interpreter.speed = self.start_speed
        except SparkyError as err:
            self.sig_error.emit(err.pretty(), err.line or 0)
            self.sig_done.emit(False)
            return

        last_line = 0
        last_line_emit = 0.0
        steps = 0
        try:
            for tick in self.interpreter.run():
                if self._stop:
                    break
                line = tick[-1]
                now = time.monotonic()
                # highlight the running line, but don't flood the UI
                if line != last_line and now - last_line_emit > 0.03:
                    last_line = line
                    last_line_emit = now
                    self.sig_line.emit(line)

                kind = tick[0]
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
            self.sig_error.emit(err.pretty(), err.line or 0)
            self.sig_done.emit(False)
            return
        except Exception as err:  # never show kids a traceback
            self.sig_error.emit(
                f"Oops! Something surprised me deep inside: {err}", 0)
            self.sig_done.emit(False)
            return
        self.sig_done.emit(True)

    def answer(self, text):
        self.runtime.answers.put(text)
