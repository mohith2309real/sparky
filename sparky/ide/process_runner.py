# Runs Python, JavaScript and other programs as a separate process,
# streaming their output into Sparky's console and feeding the console's
# input line to the program (so Python's input() works).

import os
import re

from PyQt6.QtCore import QObject, QProcess, QProcessEnvironment, pyqtSignal

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
TRACEBACK_LINE = re.compile(r'File "([^"]+)", line (\d+)')
NODE_LINE = re.compile(r"^(/[^:\n]+|[A-Za-z]:\\[^:\n]+):(\d+)", re.M)


class ProcessRunner(QObject):
    output = pyqtSignal(str, bool)      # text, is_error
    finished = pyqtSignal(int)          # exit code (-1 if stopped)
    error_line = pyqtSignal(str, int)   # file, line where it went wrong

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = None
        self.stopped = False
        self.stderr_text = ""

    def is_running(self):
        return self.process is not None and \
            self.process.state() != QProcess.ProcessState.NotRunning

    def start(self, command, cwd):
        self.stopped = False
        self.stderr_text = ""
        self.process = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        env.insert("PYTHONIOENCODING", "utf-8")
        env.insert("NO_COLOR", "1")          # plain text: the console can't show colors
        env.insert("PYTHON_COLORS", "0")
        env.remove("FORCE_COLOR")
        self.process.setProcessEnvironment(env)
        self.process.setWorkingDirectory(str(cwd))
        self.process.readyReadStandardOutput.connect(self._read_out)
        self.process.readyReadStandardError.connect(self._read_err)
        self.process.finished.connect(self._done)
        self.process.errorOccurred.connect(self._failed)
        self.process.start(command[0], command[1:])

    def write(self, text):
        if self.is_running():
            self.process.write((text + os.linesep).encode("utf-8"))

    def stop(self):
        if self.is_running():
            self.stopped = True
            self.process.kill()

    def _read_out(self):
        data = ANSI.sub("", bytes(self.process.readAllStandardOutput()).decode("utf-8", "replace"))
        if data:
            self.output.emit(data, False)

    def _read_err(self):
        data = ANSI.sub("", bytes(self.process.readAllStandardError()).decode("utf-8", "replace"))
        if data:
            self.stderr_text += data
            self.output.emit(data, True)

    def _failed(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.output.emit("Couldn't start that program. Check the path in "
                             "Settings → Languages.\n", True)
            self.finished.emit(-1)

    def _done(self, code, _status):
        self._read_out()
        self._read_err()
        matches = TRACEBACK_LINE.findall(self.stderr_text) or \
            NODE_LINE.findall(self.stderr_text)
        if matches and not self.stopped:
            path, line = matches[-1]
            self.error_line.emit(path, int(line))
        self.finished.emit(-1 if self.stopped else code)
