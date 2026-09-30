# Small dialogs: About (credits), Community (sharing + gallery),
# and Settings.

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QPixmap
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                             QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                             QListWidget, QPlainTextEdit, QPushButton, QSlider,
                             QSpinBox, QTabWidget, QVBoxLayout, QWidget)

from .. import __version__
from ..paths import (ASSETS_DIR as ASSETS, EXTENSIONS_DIR,
                     GALLERY_DIR as GALLERY)

SITE_URL = "https://mohith2309.github.io"


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
            self.main_window.open_path(path)
            self.main_window.raise_()

    def open_folder(self):
        GALLERY.mkdir(exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(GALLERY)))


class SettingsDialog(QDialog):
    def __init__(self, main_window, tab="General"):
        super().__init__(main_window)
        from . import ai, languages, vscode
        self.ai, self.languages = ai, languages
        self.main = main_window
        self.setWindowTitle("Settings")
        self.resize(560, 560)
        settings = main_window.settings

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        # --- General ---
        general = QWidget()
        form = QFormLayout(general)
        form.setSpacing(12)
        self.theme = QComboBox()
        self.theme.addItem("Light", "light")
        self.theme.addItem("Dark", "dark")
        for key, label, _dark in vscode.all_themes():
            self.theme.addItem(f"{label}  (VS Code)", key)
        index = self.theme.findData(main_window.theme_key)
        self.theme.setCurrentIndex(max(0, index))
        form.addRow("Theme", self.theme)
        self.speed = QSlider(Qt.Orientation.Horizontal)
        self.speed.setRange(1, 10)
        self.speed.setValue(main_window.speed_slider.value())
        form.addRow("Default speed", self.speed)
        self.font_size = QSpinBox()
        self.font_size.setRange(10, 28)
        self.font_size.setValue(main_window.font_size)
        form.addRow("Code text size", self.font_size)
        self.autocomplete = QCheckBox("Suggest words while typing")
        self.autocomplete.setChecked(main_window.completions_enabled)
        form.addRow("", self.autocomplete)
        self.sounds = QCheckBox("Play sounds")
        self.sounds.setChecked(main_window.sound_bank.enabled)
        form.addRow("", self.sounds)
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(int(main_window.sound_bank.volume * 100))
        form.addRow("Volume", self.volume)
        self.welcome = QCheckBox("Show welcome on startup")
        self.welcome.setChecked(settings.value("show_welcome", True, type=bool))
        form.addRow("", self.welcome)
        self.tabs.addTab(general, "General")

        # --- Languages ---
        langs = QWidget()
        lform = QFormLayout(langs)
        lform.setSpacing(10)
        self.python = QComboBox()
        self.python.setEditable(True)
        self.python.addItem("Automatic", "")
        for cmd in languages.python_candidates():
            self.python.addItem(" ".join(cmd), cmd[0] if len(cmd) == 1 else "")
        current = settings.value("python_path", "", type=str)
        if current:
            self.python.setEditText(current)
        prow = QHBoxLayout()
        prow.addWidget(self.python, 1)
        check = QPushButton("Find")
        check.setToolTip("List the Pythons on this computer and check for turtle graphics")
        check.clicked.connect(self.check_pythons)
        prow.addWidget(check)
        lform.addRow("Python", prow)
        self.python_note = QLabel("Python programs (and Sparky programs turned into "
                                  "Python) run with this.")
        self.python_note.setWordWrap(True)
        self.python_note.setObjectName("FileLabel")
        lform.addRow("", self.python_note)
        self.node = QComboBox()
        self.node.setEditable(True)
        self.node.addItem("Automatic", "")
        for cmd in languages.node_candidates():
            self.node.addItem(cmd[0], cmd[0])
        if settings.value("node_path", "", type=str):
            self.node.setEditText(settings.value("node_path", "", type=str))
        lform.addRow("Node.js", self.node)
        self.commands = QPlainTextEdit(settings.value("run_commands", languages.DEFAULT_CUSTOM,
                                                      type=str))
        self.commands.setFixedHeight(120)
        lform.addRow("Run commands", self.commands)
        cnote = QLabel("One per line: .ext = command. {file} is the file to run.")
        cnote.setObjectName("FileLabel")
        lform.addRow("", cnote)
        self.tabs.addTab(langs, "Languages")

        # --- AI ---
        aitab = QWidget()
        aform = QFormLayout(aitab)
        aform.setSpacing(10)
        self.provider = QComboBox()
        self.provider.addItems(list(ai.PROVIDERS))
        self.provider.setCurrentText(settings.value("ai_provider", "Anthropic (Claude)", type=str))
        self.provider.currentTextChanged.connect(self.provider_changed)
        aform.addRow("Provider", self.provider)
        self.base_url = QLineEdit(settings.value("ai_base_url", "", type=str))
        aform.addRow("Base URL", self.base_url)
        self.key = QLineEdit(settings.value("ai_key", "", type=str))
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("Paste your API key")
        aform.addRow("API key", self.key)
        mrow = QHBoxLayout()
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.setEditText(settings.value("ai_model", "", type=str))
        mrow.addWidget(self.model, 1)
        load = QPushButton("Load models")
        load.clicked.connect(self.load_models)
        mrow.addWidget(load)
        aform.addRow("Model", mrow)
        self.tutor = QCheckBox("Tutor mode: hints and explanations before full answers")
        self.tutor.setChecked(settings.value("ai_tutor", True, type=bool))
        aform.addRow("", self.tutor)
        self.instructions = QPlainTextEdit(settings.value("ai_instructions", "", type=str))
        self.instructions.setPlaceholderText("Your own instructions for the AI, like: "
                                             "Explain things like I'm 10. Use lots of emojis.")
        self.instructions.setFixedHeight(90)
        aform.addRow("Instructions", self.instructions)
        self.ai_note = QLabel("")
        self.ai_note.setWordWrap(True)
        self.ai_note.setObjectName("FileLabel")
        aform.addRow("", self.ai_note)
        self.tabs.addTab(aitab, "AI")
        self.provider_changed(self.provider.currentText(), first=True)

        names = [self.tabs.tabText(i) for i in range(self.tabs.count())]
        if tab in names:
            self.tabs.setCurrentIndex(names.index(tab))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.apply_and_close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.models_worker = None

    def provider_changed(self, name, first=False):
        kind, base, model, needs_key = self.ai.PROVIDERS[name]
        if not first:
            self.base_url.setText("")
            self.model.clear()
            self.model.setEditText(model)
        self.base_url.setPlaceholderText(base or "https://your-provider.example/v1")
        self.key.setEnabled(needs_key or kind == "anthropic")
        if not self.model.currentText() and model:
            self.model.setEditText(model)
        tips = {
            "anthropic": f"Uses Anthropic's official SDK. Default model: "
                         f"{self.ai.ANTHROPIC_DEFAULT_MODEL}. Get a key at console.anthropic.com.",
            "openai": "Works with any OpenAI-compatible API. Press Load models to pick one."}
        local = "" if needs_key else " Runs on your own computer — no key needed."
        self.ai_note.setText(tips[kind] + local +
                             " Your key is saved only on this computer, in Sparky's settings.")

    def load_models(self):
        cfg = {"name": self.provider.currentText(),
               "kind": self.ai.PROVIDERS[self.provider.currentText()][0],
               "base_url": self.base_url.text().strip() or
               self.ai.PROVIDERS[self.provider.currentText()][1],
               "key": self.key.text().strip(), "model": ""}
        self.ai_note.setText("Loading models…")
        self.models_worker = self.ai.ModelsWorker(cfg, self)
        self.models_worker.loaded.connect(self.models_loaded)
        self.models_worker.failed.connect(lambda m: self.ai_note.setText("⚠️ " + m))
        self.models_worker.start()

    def models_loaded(self, names):
        current = self.model.currentText()
        self.model.clear()
        self.model.addItems(names)
        self.model.setEditText(current if current in names or not names else names[0])
        self.ai_note.setText(f"Found {len(names)} model(s).")

    def check_pythons(self):
        rows = []
        for cmd in self.languages.python_candidates():
            turtle = "✓ turtle graphics" if self.languages.has_turtle(cmd) else "no turtle graphics"
            rows.append(f"{' '.join(cmd)} — {turtle}")
        self.python_note.setText("\n".join(rows) if rows else
                                 "No Python found. Install it from python.org.")

    def apply_and_close(self):
        w = self.main
        s = w.settings
        w.speed_slider.setValue(self.speed.value())
        w.set_font_size_all(self.font_size.value())
        w.completions_enabled = self.autocomplete.isChecked()
        for editor in w.editors():
            editor.completions_enabled = w.completions_enabled
        w.sound_bank.enabled = self.sounds.isChecked()
        w.sound_bank.volume = self.volume.value() / 100
        s.setValue("show_welcome", self.welcome.isChecked())
        python = self.python.currentText().strip()
        s.setValue("python_path", "" if python == "Automatic" or " " in python else python)
        node = self.node.currentText().strip()
        s.setValue("node_path", "" if node == "Automatic" else node)
        s.setValue("run_commands", self.commands.toPlainText())
        s.setValue("ai_provider", self.provider.currentText())
        s.setValue("ai_base_url", self.base_url.text().strip())
        s.setValue("ai_key", self.key.text().strip())
        s.setValue("ai_model", self.model.currentText().strip())
        s.setValue("ai_tutor", self.tutor.isChecked())
        s.setValue("ai_instructions", self.instructions.toPlainText())
        w.set_theme(self.theme.currentData())
        w.save_settings()
        w.ai_panel.refresh_header()
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
