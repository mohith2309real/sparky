# Small dialogs: About (credits), Community (sharing + gallery),
# and Settings.

from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QPixmap
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                             QFormLayout, QHBoxLayout, QLabel, QListWidget,
                             QPushButton, QSlider, QSpinBox, QVBoxLayout)

from .. import __version__
from .extension_manager import EXTENSIONS_DIR

SITE_URL = "https://mohith2309.github.io"
ASSETS = Path(__file__).resolve().parent.parent.parent / "assets"
GALLERY = Path(__file__).resolve().parent.parent.parent / "gallery"


def open_site():
    QDesktopServices.openUrl(QUrl(SITE_URL))


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Sparky")
        self.setFixedWidth(380)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(24, 24, 24, 20)

        logo_path = ASSETS / "logo_128.png"
        if logo_path.exists():
            logo = QLabel()
            logo.setPixmap(QPixmap(str(logo_path)))
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(logo)

        title = QLabel("⚡ Sparky")
        title.setObjectName("AppTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        body = QLabel(
            f"Version {__version__}<br><br>"
            "A coding platform for kids (and grown-ups!):<br>"
            "a friendly language + a fast native IDE.<br>"
            "No browser engine anywhere — real native code.<br><br>"
            "<b>Created by Mohith</b><br>"
            "Built with Python and Qt.")
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(body)

        site = QPushButton("🌐  Visit Mohith's website")
        site.setCursor(Qt.CursorShape.PointingHandCursor)
        site.clicked.connect(open_site)
        layout.addWidget(site)

        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        layout.addWidget(close)


class CommunityDialog(QDialog):
    """Sharing programs the honest way: .spark files and exported apps.
    The gallery folder is the local 'community board' — drop in programs
    from friends and they show up here."""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("Sparky Community")
        self.resize(520, 460)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(10)

        intro = QLabel(
            "<h3>Share your creations! 🌍</h3>"
            "<p>Every Sparky program is a little <b>.spark</b> file — "
            "send it to a friend and they can open it here. Or use "
            "<b>Make an App</b> to turn it into a double-clickable app.</p>"
            "<p>The <b>gallery</b> folder is your community board: drop in "
            "programs from friends and family, and they show up below.</p>")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.gallery_list = QListWidget()
        layout.addWidget(self.gallery_list, 1)

        row = QHBoxLayout()
        open_button = QPushButton("Open in editor")
        open_button.clicked.connect(self.open_selected)
        folder_button = QPushButton("📂 Gallery folder")
        folder_button.clicked.connect(self.open_folder)
        site_button = QPushButton("🌐 Mohith's website")
        site_button.clicked.connect(open_site)
        for b in (open_button, folder_button, site_button):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            row.addWidget(b)
        layout.addLayout(row)

        self.refresh()

    def refresh(self):
        GALLERY.mkdir(exist_ok=True)
        self.gallery_list.clear()
        programs = sorted(GALLERY.glob("*.spark"))
        if not programs:
            self.gallery_list.addItem(
                "(empty — drop .spark files into the gallery folder)")
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
            if self.main_window.confirm_discard():
                self.main_window.load_path(path)
                self.main_window.raise_()

    def open_folder(self):
        GALLERY.mkdir(exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(GALLERY)))


class SettingsDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("Settings")
        self.setFixedWidth(380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 14)
        form = QFormLayout()
        form.setSpacing(12)

        self.theme = QComboBox()
        self.theme.addItems(["Light", "Dark"])
        self.theme.setCurrentIndex(1 if main_window.dark else 0)
        form.addRow("Theme", self.theme)

        self.speed = QSlider(Qt.Orientation.Horizontal)
        self.speed.setRange(1, 10)
        self.speed.setValue(main_window.speed_slider.value())
        form.addRow("Default speed", self.speed)

        self.font_size = QSpinBox()
        self.font_size.setRange(10, 28)
        self.font_size.setValue(main_window.editor.font().pointSize())
        form.addRow("Code text size", self.font_size)

        self.autocomplete = QCheckBox("Suggest words while typing")
        self.autocomplete.setChecked(main_window.editor.completions_enabled)
        form.addRow("", self.autocomplete)

        self.sounds = QCheckBox("Play sounds")
        self.sounds.setChecked(main_window.sound_bank.enabled)
        form.addRow("", self.sounds)

        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(int(main_window.sound_bank.volume * 100))
        form.addRow("Volume", self.volume)

        self.welcome = QCheckBox("Show welcome on startup")
        self.welcome.setChecked(main_window.settings.value(
            "show_welcome", True, type=bool))
        form.addRow("", self.welcome)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.apply_and_close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def apply_and_close(self):
        w = self.main_window
        w.dark = self.theme.currentIndex() == 1
        w.apply_theme()
        w.speed_slider.setValue(self.speed.value())
        w.editor.set_font_size(self.font_size.value())
        w.editor.completions_enabled = self.autocomplete.isChecked()
        w.sound_bank.enabled = self.sounds.isChecked()
        w.sound_bank.volume = self.volume.value() / 100
        w.settings.setValue("show_welcome", self.welcome.isChecked())
        w.save_settings()
        self.accept()


class WelcomeDialog(QDialog):
    """First-launch hello: what to click, in three lines."""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("Welcome!")
        self.setFixedWidth(420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 18)
        layout.setSpacing(12)

        logo_path = ASSETS / "logo_128.png"
        if logo_path.exists():
            logo = QLabel()
            logo.setPixmap(QPixmap(str(logo_path)))
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(logo)

        body = QLabel(
            "<h2 align='center'>Welcome to Sparky! ⚡</h2>"
            "<p><b>▶ Run</b> — there's already a program waiting. "
            "Press Run and watch the stage!</p>"
            "<p><b>🧱 Blocks</b> — click any colored block on the left "
            "and real code appears. Change the numbers!</p>"
            "<p><b>🎓 Learn</b> — ten little lessons, from \"hello\" "
            "to drawing fractal trees.</p>")
        body.setWordWrap(True)
        body.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(body)

        start = QPushButton("🎓  Start Lesson 1")
        start.setObjectName("RunButton")
        start.setCursor(Qt.CursorShape.PointingHandCursor)
        start.clicked.connect(self.start_lesson)
        layout.addWidget(start)

        explore = QPushButton("I'll explore on my own")
        explore.clicked.connect(self.accept)
        layout.addWidget(explore)

    def start_lesson(self):
        self.accept()
        self.main_window.show_learn()


class ExtensionsDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        manager = main_window.extension_manager
        self.setWindowTitle("Extensions")
        self.resize(500, 420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(10)

        intro = QLabel(
            "<h3>Extensions 🧩</h3>"
            "<p>Any <b>.py</b> file in the <b>extensions</b> folder with a "
            "<b>register(api)</b> function can add new block categories. "
            "Copy <b>shape_pack.py</b> to make your own — changes load "
            "next time Sparky starts.</p>")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.listing = QListWidget()
        if not manager.extensions:
            self.listing.addItem("(no extensions installed)")
            self.listing.setEnabled(False)
        for ext in manager.extensions:
            if ext.error:
                self.listing.addItem(
                    f"⚠️ {ext.name} — couldn't load: {ext.error}")
            else:
                self.listing.addItem(
                    f"🧩 {ext.name} by {ext.author} — "
                    f"{ext.blocks_added} block(s)")
        layout.addWidget(self.listing, 1)

        folder = QPushButton("📂 Open extensions folder")
        folder.setCursor(Qt.CursorShape.PointingHandCursor)
        folder.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(EXTENSIONS_DIR))))
        layout.addWidget(folder)

        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        layout.addWidget(close)
