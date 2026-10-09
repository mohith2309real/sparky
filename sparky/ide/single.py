# One window (feature 222): opening a file while Sparky is already running
# hands it to the open window instead of starting a second copy.

import getpass
import json
import os

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket


def _name():
    try:
        user = getpass.getuser()
    except Exception:
        user = "user"
    return f"sparky-ide-{user}"


class Server(QObject):
    files_received = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._accept)

    def listen(self):
        if not self.server.listen(_name()):
            QLocalServer.removeServer(_name())
            self.server.listen(_name())

    def _accept(self):
        socket = self.server.nextPendingConnection()
        if socket is None:
            return
        socket.waitForReadyRead(1000)
        try:
            paths = json.loads(bytes(socket.readAll()).decode("utf-8") or "[]")
        except ValueError:
            paths = []
        socket.disconnectFromServer()
        from pathlib import Path
        self.files_received.emit([Path(p) for p in paths])


def hand_over_or_listen(files):
    """Returns a Server to keep, or None if another Sparky took the files."""
    if os.environ.get("SPARKY_NEW_WINDOW") != "1":
        socket = QLocalSocket()
        socket.connectToServer(_name())
        if socket.waitForConnected(300):
            socket.write(json.dumps([str(p) for p in files]).encode("utf-8"))
            socket.flush()
            socket.waitForBytesWritten(1000)
            socket.disconnectFromServer()
            return None
    server = Server()
    server.listen()
    return server
