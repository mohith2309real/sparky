# Small dialogs: About (credits), Community (sharing + gallery), the
# first-run welcome, What's new, and the Extensions list.
# Settings lives in settings_dialog.py.

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QListWidget, QScrollArea,
                             QVBoxLayout, QWidget)

from .. import __version__
from . import mascot, whats_new
from .widgets import text_button
from ..paths import EXTENSIONS_DIR, GALLERY_DIR as GALLERY

SITE_URL = "https://mohith2309.web.app"


def open_site():
    QDesktopServices.openUrl(QUrl(SITE_URL))


def _face(size, mood="happy"):
    label = QLabel()
    label.setPixmap(mascot.pixmap(size, mood))
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label


def _label(text, name=None, center=False):
    label = QLabel(text)
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setOpenExternalLinks(True)
    if name:
        label.setObjectName(name)
    if center:
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Sparky")
        self.setFixedWidth(400)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(28, 26, 28, 22)
        layout.addWidget(_face(96, "happy"))
        layout.addWidget(_label("Sparky", "HeroTitle", center=True))
        layout.addWidget(_label(f"Version {__version__}", "Muted", center=True))
        layout.addWidget(_label(
            "A coding app for kids (and grown-ups): a friendly language, a stage that "
            "draws, and a real native IDE — no browser engine anywhere.<br><br>"
            "<b>Created by Mohith.</b> Built with Python and Qt.", center=True))
        site = text_button("Visit Mohith's website", icon="globe", object_name="Primary")
        site.clicked.connect(open_site)
        layout.addWidget(site)
        close = text_button("Close")
        close.clicked.connect(self.accept)
        layout.addWidget(close)


class FirstRunDialog(QDialog):
    """The first launch: say hello, pick Kid or Pro mode, offer the tour."""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.setWindowTitle("Welcome to Sparky")
        self.setFixedWidth(520)
        self.mode = main_window.mode
        self.take_tour = True
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 26, 30, 24)
        layout.setSpacing(12)
        layout.addWidget(_face(110, "wow"))
        layout.addWidget(_label("Welcome to Sparky!", "HeroTitle", center=True))
        layout.addWidget(_label("Who's coding today? You can change this anytime in Settings.",
                                "Muted", center=True))
        row = QHBoxLayout()
        row.setSpacing(12)
        kid = text_button("I'm a kid", icon="sprite", object_name="Primary")
        kid.setToolTip("Kid mode: a simple screen with the important things")
        kid.clicked.connect(lambda: self.pick("kid"))
        grown = text_button("I'm a grown-up", icon="code")
        grown.setToolTip("Pro mode: every panel and tool")
        grown.clicked.connect(lambda: self.pick("pro"))
        row.addWidget(kid, 1)
        row.addWidget(grown, 1)
        layout.addLayout(row)
        skip = text_button("Skip the tour", object_name="GhostButton")
        skip.clicked.connect(self.skip_tour)
        layout.addWidget(skip, 0, Qt.AlignmentFlag.AlignCenter)

    def pick(self, mode):
        self.mode = mode
        self.accept()

    def skip_tour(self):
        self.take_tour = False
        self.accept()


class WhatsNewDialog(QDialog):
    """Release notes: the built-in history, or one update's notes from its manifest."""

    def __init__(self, main_window, update=None):
        super().__init__(main_window)
        self.setWindowTitle("What's new in Sparky")
        self.resize(560, 560)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 18)
        layout.setSpacing(10)
        top = QHBoxLayout()
        top.addWidget(_face(64, "wow"))
        title = _label("What's new", "HeroTitle")
        top.addWidget(title, 1)
        layout.addLayout(top)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        col = QVBoxLayout(body)
        col.setSpacing(14)
        if update is not None and update.notes:
            col.addWidget(_label(f"Sparky {whats_new.pretty_version(update.version)}", "SubHeading"))
            notes = update.notes.replace("\n", "<br>")
            col.addWidget(_label(notes))
        for release in whats_new.RELEASES:
            col.addWidget(_label(f"Sparky {whats_new.pretty_version(release['version'])} "
                                 f"<span style='font-weight:400'>· {release['date']}</span>",
                                 "SubHeading"))
            col.addWidget(_label(f"<b>{release['title']}</b>"))
            col.addWidget(_label("".join(f"• {item}<br>" for item in release["items"])))
        col.addStretch(1)
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)
        close = text_button("Nice!", object_name="Primary")
        close.clicked.connect(self.accept)
        layout.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)


class CommunityDialog(QDialog):
    """Sharing programs the honest way: .spark files and exported apps.
    The gallery folder is the local 'community board' — drop in programs
    from friends and they show up here."""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("Sparky Community")
        self.resize(540, 480)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 18)
        layout.setSpacing(10)
        layout.addWidget(_label("Share your creations", "Heading"))
        layout.addWidget(_label(
            "Every Sparky program is a little <b>.spark</b> file — send it to a friend and "
            "they can open it here. Or use <b>Make an App</b> to turn it into a "
            "double-clickable app.<br><br>The <b>gallery</b> folder is your community board: "
            "drop in programs from friends and family, and they show up below.", "Muted"))

        self.gallery_list = QListWidget()
        layout.addWidget(self.gallery_list, 1)

        row = QHBoxLayout()
        open_button = text_button("Open in editor", object_name="Primary")
        open_button.clicked.connect(self.open_selected)
        folder_button = text_button("Gallery folder", icon="files")
        folder_button.clicked.connect(self.open_folder)
        site_button = text_button("Mohith's website", icon="globe")
        site_button.clicked.connect(open_site)
        for b in (open_button, folder_button, site_button):
            row.addWidget(b)
        layout.addLayout(row)
        self.refresh()

    def refresh(self):
        GALLERY.mkdir(parents=True, exist_ok=True)
        self.gallery_list.clear()
        programs = sorted(GALLERY.glob("*.spark"))
        if not programs:
            self.gallery_list.addItem("(empty — drop .spark files into the gallery folder)")
            self.gallery_list.setEnabled(False)
        else:
            self.gallery_list.setEnabled(True)
            for path in programs:
                self.gallery_list.addItem(path.name)

    def open_selected(self):
        item = self.gallery_list.currentItem()
        if item is None or not self.gallery_list.isEnabled():
            return
        path = GALLERY / item.text()
        if path.exists():
            self.main_window.open_path(path)
            self.main_window.raise_()
            self.accept()

    def open_folder(self):
        GALLERY.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(GALLERY)))


class ExtensionsDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        manager = main_window.extension_manager
        self.setWindowTitle("Extensions")
        self.resize(500, 420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 18)
        layout.setSpacing(10)
        layout.addWidget(_label("Extensions", "Heading"))
        layout.addWidget(_label(
            "Any <b>.py</b> file in the <b>extensions</b> folder with a <b>register(api)</b> "
            "function can add new block categories. Copy <b>shape_pack.py</b> to make your own "
            "— changes load next time Sparky starts.", "Muted"))
        self.listing = QListWidget()
        if not manager.extensions:
            self.listing.addItem("(no extensions installed)")
            self.listing.setEnabled(False)
        for ext in manager.extensions:
            if ext.error:
                self.listing.addItem(f"⚠️ {ext.name} — couldn't load: {ext.error}")
            else:
                self.listing.addItem(f"{ext.name} by {ext.author} — {ext.blocks_added} block(s)")
        layout.addWidget(self.listing, 1)
        folder = text_button("Open extensions folder", icon="files")
        folder.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(EXTENSIONS_DIR))))
        layout.addWidget(folder)
        close = text_button("Close")
        close.clicked.connect(self.accept)
        layout.addWidget(close)
