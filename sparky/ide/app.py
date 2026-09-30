# The Sparky IDE main window.
#
#   activity bar | sidebar (Blocks · Files · Extensions · AI) | tabs | stage + console
#
# Sparky programs run on the stage; Python, JavaScript and other languages
# run as normal programs with their output in the console. Native Qt all the
# way — no browser engine.

import html
import sys
import tempfile
from pathlib import Path

from PyQt6.QtCore import Qt, QSettings, QTimer, QUrl
from PyQt6.QtGui import (QAction, QColor, QDesktopServices, QFont, QIcon,
                         QKeySequence, QShortcut, QTextCharFormat, QTextCursor)
from PyQt6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout,
                             QInputDialog, QLabel, QLineEdit, QMainWindow,
                             QMenu, QMessageBox, QPlainTextEdit, QPushButton,
                             QSlider, QSplitter, QStackedWidget, QTabWidget,
                             QToolButton, QVBoxLayout, QWidget)

from . import languages, vscode
from .ai import AIPanel
from .blocks import BlockPalette
from .dialogs import (AboutDialog, CommunityDialog, SettingsDialog,
                      WelcomeDialog, open_site)
from .editor import CodeEditor
from .export import make_app
from .extension_manager import ExtensionManager
from .learn import LearnDialog
from .panels import CommandPalette, ExtensionsPanel, FilesPanel, FindBar
from .process_runner import ProcessRunner
from .runner import RunnerThread
from .sounds import SoundBank
from .stage import StageModel, StageView
from .theme import LIGHT, DARK, build_qss, HEADING_FONTS
from ..lang import SparkyError
from ..lang.to_python import to_python
from ..paths import ASSETS_DIR, EXAMPLES_DIR, prepare_user_dirs

WELCOME = '''\
# Welcome to Sparky!
# Press the orange Run button and watch the stage.
# Then try changing the numbers and run it again!

speed 7
pen color "orange"
pen size 4

say "Watch this!"

repeat 12 times
  move 80
  turn left 150
end

say "Now you try!"
'''

SIDEBAR = [("blocks", "🧱", "Blocks"), ("files", "📁", "Files"),
           ("extensions", "🧩", "Extensions"), ("ai", "✨", "AI helper")]


def is_dark(palette):
    color = QColor(palette["editor_bg"])
    return color.lightness() < 128


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("Sparky", "Sparky")
        self.theme_key = "light"
        self.palette_colors = LIGHT
        self.dark = False
        self.font_size = 15
        self.completions_enabled = True
        self.runner = None              # Sparky programs (stage)
        self.run_editor = None
        self.run_path = None
        self.last_error = ""
        self.learn_dialog = None
        self.snippet_cache = {}
        self.untitled = 0

        self.setWindowTitle("Sparky")
        self.resize(1400, 880)
        self.setAcceptDrops(True)
        icon_path = ASSETS_DIR / "logo_256.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        prepare_user_dirs()
        self.sound_bank = SoundBank()
        self.extension_manager = ExtensionManager()
        self.extension_manager.discover()
        self.proc = ProcessRunner(self)
        self.proc.output.connect(self.on_proc_output)
        self.proc.finished.connect(self.on_proc_done)
        self.proc.error_line.connect(self.on_proc_error_line)

        self.stage_model = StageModel()
        self.build_ui()
        self.load_settings()
        self.restore_session()
        self.set_theme(self.theme_key)
        self.status.showMessage("Ready to spark! Press Run.")

        if self.settings.value("show_welcome", True, type=bool):
            QTimer.singleShot(250, self.show_welcome)

    # ---------- building the window ----------

    def build_ui(self):
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.setCentralWidget(root)
        root_layout.addWidget(self.build_header())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self.build_activity_bar())

        self.blocks = BlockPalette(
            self.palette_colors, lambda snippet: self.editor.insert_snippet(snippet),
            extra_categories=self.extension_manager.api.block_categories)
        self.files_panel = FilesPanel(self)
        self.ai_panel = AIPanel(self)
        self.extensions_panel = ExtensionsPanel(self)
        self.sidebar = QStackedWidget()
        self.sidebar.setMinimumWidth(230)
        for widget in (self.blocks, self.files_panel, self.extensions_panel, self.ai_panel):
            self.sidebar.addWidget(widget)

        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        self.find_bar = FindBar(self)
        center_layout.addWidget(self.find_bar)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("EditorTabs")
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.tab_changed)
        center_layout.addWidget(self.tabs, 1)

        right = QSplitter(Qt.Orientation.Vertical)
        self.stage = StageView(self.stage_model, self.palette_colors)
        self.stage_box = QWidget()
        stage_layout = QVBoxLayout(self.stage_box)
        stage_layout.setContentsMargins(0, 0, 0, 0)
        stage_layout.setSpacing(0)
        stage_title = QLabel("STAGE")
        stage_title.setObjectName("StageTitle")
        stage_layout.addWidget(stage_title)
        stage_layout.addWidget(self.stage, 1)
        right.addWidget(self.stage_box)
        right.addWidget(self.build_console())
        right.setSizes([520, 280])

        self.split = QSplitter(Qt.Orientation.Horizontal)
        self.split.addWidget(self.sidebar)
        self.split.addWidget(center)
        self.split.addWidget(right)
        self.split.setSizes([260, 600, 520])
        self.split.setCollapsible(1, False)
        body.addWidget(self.split, 1)
        root_layout.addLayout(body, 1)

        self.status = self.statusBar()
        self.lang_label = QLabel("Sparky")
        self.lang_label.setObjectName("FileLabel")
        self.status.addPermanentWidget(self.lang_label)
        self.cursor_label = QLabel("Ln 1, Col 1")
        self.cursor_label.setObjectName("FileLabel")
        self.status.addPermanentWidget(self.cursor_label)
        credit = QPushButton("⚡ by Mohith")
        credit.setObjectName("GhostButton")
        credit.setCursor(Qt.CursorShape.PointingHandCursor)
        credit.setToolTip("Visit Mohith's website")
        credit.clicked.connect(open_site)
        self.status.addPermanentWidget(credit)

        shortcuts = [
            ("Ctrl+Return", self.run_program), ("Meta+Return", self.run_program),
            ("Ctrl+N", self.new_file), ("Ctrl+O", self.open_file), ("Ctrl+S", self.save_file),
            ("Ctrl+Shift+S", self.save_as), ("Ctrl+W", lambda: self.close_tab(self.tabs.currentIndex())),
            ("Ctrl+F", lambda: self.find_bar.open(False)),
            ("Ctrl+Alt+F", lambda: self.find_bar.open(True)),
            ("Ctrl+G", self.go_to_line), ("Ctrl+/", lambda: self.editor.toggle_comment()),
            ("Ctrl+Shift+P", self.show_palette), ("F1", self.show_palette),
            ("Ctrl+P", self.quick_open), ("Ctrl+B", self.toggle_sidebar),
            ("Ctrl+=", lambda: self.set_font_size_all(self.font_size + 1)),
            ("Ctrl+-", lambda: self.set_font_size_all(self.font_size - 1)),
            ("Ctrl+0", lambda: self.set_font_size_all(15)),
            ("Ctrl+Tab", lambda: self.cycle_tab(1)), ("Ctrl+Shift+Tab", lambda: self.cycle_tab(-1)),
        ]
        for keys, slot in shortcuts:
            QShortcut(QKeySequence(keys), self, slot)

    def build_activity_bar(self):
        bar = QWidget()
        bar.setObjectName("ActivityBar")
        layout = QVBoxLayout(bar)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(4)
        self.activity_buttons = {}
        for index, (key, icon, tip) in enumerate(SIDEBAR):
            b = QToolButton()
            b.setText(icon)
            b.setToolTip(tip)
            b.setCheckable(True)
            b.setObjectName("ActivityButton")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, i=index: self.show_sidebar(i))
            layout.addWidget(b)
            self.activity_buttons[index] = b
        layout.addStretch(1)
        palette_btn = QToolButton()
        palette_btn.setText("⌘")
        palette_btn.setToolTip("All commands (Ctrl/Cmd+Shift+P)")
        palette_btn.setObjectName("ActivityButton")
        palette_btn.clicked.connect(self.show_palette)
        layout.addWidget(palette_btn)
        settings_btn = QToolButton()
        settings_btn.setText("⚙")
        settings_btn.setToolTip("Settings")
        settings_btn.setObjectName("ActivityButton")
        settings_btn.clicked.connect(lambda: self.open_settings())
        layout.addWidget(settings_btn)
        self.activity_buttons[0].setChecked(True)
        return bar

    def build_header(self):
        bar = QWidget()
        bar.setObjectName("HeaderBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 9, 14, 9)
        layout.setSpacing(8)

        title = QLabel("⚡ Sparky")
        title.setObjectName("AppTitle")
        layout.addWidget(title)
        self.file_label = QLabel("")
        self.file_label.setObjectName("FileLabel")
        layout.addWidget(self.file_label)
        layout.addStretch(1)

        def ghost(text, slot, tip=""):
            b = QPushButton(text)
            b.setObjectName("GhostButton")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            if tip:
                b.setToolTip(tip)
            layout.addWidget(b)
            return b

        ghost("New", self.new_file, "New file (Ctrl/Cmd+N)")
        ghost("Open", self.open_file, "Open a file (Ctrl/Cmd+O)")
        ghost("Save", self.save_file, "Save (Ctrl/Cmd+S)")
        self.examples_button = ghost("Examples ▾", self.show_examples)
        ghost("Learn", self.show_learn, "Lessons, challenges, and the language guide")
        self.more_button = ghost("More ▾", self.show_more_menu)
        self.theme_button = ghost("\U0001f319", self.toggle_theme, "Switch light/dark")

        speed_label = QLabel("Speed")
        speed_label.setObjectName("FileLabel")
        layout.addWidget(speed_label)
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 10)
        self.speed_slider.setValue(5)
        self.speed_slider.setFixedWidth(100)
        self.speed_slider.setToolTip("How fast Sparky programs run (1 slow – 10 instant)")
        self.speed_slider.valueChanged.connect(self.speed_changed)
        layout.addWidget(self.speed_slider)

        self.run_button = QPushButton("▶  Run")
        self.run_button.setObjectName("RunButton")
        self.run_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.run_button.setToolTip("Run this file (Ctrl/Cmd+Return)")
        self.run_button.clicked.connect(self.run_program)
        layout.addWidget(self.run_button)
        self.stop_button = QPushButton("■  Stop")
        self.stop_button.setObjectName("StopButton")
        self.stop_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_button.clicked.connect(self.stop_program)
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button)
        return bar

    def build_console(self):
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        title = QLabel("CONSOLE")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)
        self.console = QPlainTextEdit()
        self.console.setObjectName("Console")
        self.console.setReadOnly(True)
        layout.addWidget(self.console, 1)
        ask_row = QWidget()
        ask_layout = QHBoxLayout(ask_row)
        ask_layout.setContentsMargins(8, 6, 8, 8)
        self.ask_input = QLineEdit()
        self.ask_input.setObjectName("AskInput")
        self.ask_input.setPlaceholderText("answers show up here...")
        self.ask_input.setEnabled(False)
        self.ask_input.returnPressed.connect(self.send_answer)
        ask_layout.addWidget(self.ask_input)
        layout.addWidget(ask_row)
        return box

    # ---------- sidebar ----------

    def show_sidebar(self, index):
        if self.sidebar.isVisible() and self.sidebar.currentIndex() == index:
            self.sidebar.hide()
            self.activity_buttons[index].setChecked(False)
            return
        self.sidebar.setCurrentIndex(index)
        self.sidebar.show()
        for i, b in self.activity_buttons.items():
            b.setChecked(i == index)
        if SIDEBAR[index][0] == "ai":
            sizes = self.split.sizes()
            if sizes[0] < 320:
                self.split.setSizes([340, max(420, sizes[1] - (340 - sizes[0])), sizes[2]])

    def toggle_sidebar(self):
        self.show_sidebar(self.sidebar.currentIndex())

    # ---------- tabs ----------

    @property
    def editor(self):
        editor = self.tabs.currentWidget()
        if editor is None:
            editor = self.new_tab(WELCOME)
        return editor

    def editors(self):
        return [self.tabs.widget(i) for i in range(self.tabs.count())]

    def snippets(self, language_id):
        if language_id not in self.snippet_cache:
            self.snippet_cache[language_id] = vscode.snippets_for(language_id)
        return self.snippet_cache[language_id]

    def new_tab(self, text="", path=None, language=None, title=None):
        editor = CodeEditor(self.palette_colors, language, path)
        editor.title = title
        editor.setPlainText(text)
        editor.document().setModified(False)
        editor.set_font_size(self.font_size)
        editor.completions_enabled = self.completions_enabled
        editor.snippets = self.snippets(editor.language.id)
        editor.document().modificationChanged.connect(
            lambda _=False, e=editor: self.update_tab_title(e))
        editor.cursorPositionChanged.connect(self.update_cursor_label)
        index = self.tabs.addTab(editor, editor.display_name())
        self.tabs.setTabToolTip(index, str(path) if path else editor.display_name())
        self.tabs.setCurrentIndex(index)
        editor.setFocus()
        return editor

    def update_tab_title(self, editor):
        index = self.tabs.indexOf(editor)
        if index < 0:
            return
        dot = " •" if editor.document().isModified() else ""
        self.tabs.setTabText(index, editor.display_name() + dot)
        if editor is self.tabs.currentWidget():
            self.update_file_label()

    def update_file_label(self):
        editor = self.tabs.currentWidget()
        if editor is None:
            return
        dot = " •" if editor.document().isModified() else ""
        self.file_label.setText(editor.display_name() + dot)
        self.setWindowTitle(f"{editor.display_name()}{dot} — Sparky")

    def tab_changed(self, _index):
        editor = self.tabs.currentWidget()
        if editor is None:
            return
        self.update_file_label()
        self.update_cursor_label()
        lang = editor.language
        self.lang_label.setText(lang.name)
        self.stage_box.setVisible(lang.runner == "stage")
        self.speed_slider.setEnabled(lang.runner == "stage")
        runnable = lang.runner is not None or \
            (editor.path and editor.path.suffix.lower() in languages.custom_commands(self.settings))
        self.run_button.setToolTip("Run this file (Ctrl/Cmd+Return)" if runnable else
                                   f"Sparky can't run {lang.name} files — add a run "
                                   "command in Settings → Languages")

    def cycle_tab(self, step):
        if self.tabs.count():
            self.tabs.setCurrentIndex((self.tabs.currentIndex() + step) % self.tabs.count())

    def close_tab(self, index):
        editor = self.tabs.widget(index)
        if editor is None:
            return
        if not self.confirm_discard(editor):
            return
        self.tabs.removeTab(index)
        editor.deleteLater()
        if self.tabs.count() == 0:
            self.new_file()

    # ---------- files ----------

    def confirm_discard(self, editor=None):
        editor = editor or self.tabs.currentWidget()
        if editor is None or not editor.document().isModified() or \
                not editor.toPlainText().strip():
            return True
        self.tabs.setCurrentWidget(editor)
        answer = QMessageBox.question(
            self, "Save your changes?",
            f"{editor.display_name()} has changes that aren't saved yet.\n"
            "Save before closing it?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Save:
            return self.save_file(editor)
        return answer == QMessageBox.StandardButton.Discard

    def new_file(self):
        self.untitled += 1
        return self.new_tab("", title=f"untitled-{self.untitled}.spark")

    def open_file(self):
        start = str(self.files_panel.folder or Path.home())
        paths, _ = QFileDialog.getOpenFileNames(self, "Open files", start,
                                                languages.open_dialog_filter())
        for path in paths:
            self.open_path(Path(path))

    def open_path(self, path):
        path = Path(path).resolve()
        for editor in self.editors():
            if editor.path and editor.path.resolve() == path:
                self.tabs.setCurrentWidget(editor)
                return editor
        try:
            data = path.read_bytes()
        except OSError as err:
            QMessageBox.warning(self, "Couldn't open", f"I couldn't open that file:\n{err}")
            return None
        if b"\0" in data[:8000] or len(data) > 8 * 1024 * 1024:
            QMessageBox.information(self, "Can't open that here",
                                    f"{path.name} isn't a text file Sparky can edit.")
            return None
        # replace an empty, untouched starter tab
        current = self.tabs.currentWidget()
        if current is not None and current.path is None and \
                not current.document().isModified() and not current.toPlainText().strip():
            self.tabs.removeTab(self.tabs.indexOf(current))
        editor = self.new_tab(data.decode("utf-8", "replace"), path)
        self.status.showMessage(f"Opened {path.name}")
        return editor

    def open_text(self, text, title, language="sparky"):
        return self.new_tab(text, None, languages.BY_ID[language],
                            title if "." in title else f"{title}.spark")

    def save_file(self, editor=None):
        editor = editor or self.editor
        if editor.path is None:
            return self.save_as(editor)
        try:
            editor.path.write_text(editor.toPlainText(), encoding="utf-8")
        except OSError as err:
            QMessageBox.warning(self, "Couldn't save", f"I couldn't save the file:\n{err}")
            return False
        editor.document().setModified(False)
        self.update_tab_title(editor)
        self.status.showMessage(f"Saved {editor.path.name} ✓")
        return True

    def save_as(self, editor=None):
        editor = editor or self.editor
        folder = self.files_panel.folder or Path.home()
        suggested = folder / (editor.path.name if editor.path else editor.display_name())
        path, _ = QFileDialog.getSaveFileName(self, "Save as", str(suggested),
                                              languages.open_dialog_filter())
        if not path:
            return False
        path = Path(path)
        if not path.suffix and editor.language.extensions:
            path = path.with_suffix(editor.language.extensions[0])
        editor.path = path
        new_lang = languages.language_for(path)
        if new_lang.id != editor.language.id and new_lang.id != "text":
            editor.set_language(new_lang)
            editor.snippets = self.snippets(new_lang.id)
        index = self.tabs.indexOf(editor)
        self.tabs.setTabToolTip(index, str(path))
        ok = self.save_file(editor)
        self.tab_changed(self.tabs.currentIndex())
        return ok

    def show_examples(self):
        menu = QMenu(self)
        examples = sorted(EXAMPLES_DIR.glob("*.spark")) if EXAMPLES_DIR.is_dir() else []
        if not examples:
            menu.addAction("No examples found").setEnabled(False)
        for path in examples:
            action = QAction(path.stem.replace("_", " ").title(), menu)
            action.triggered.connect(lambda _=False, p=path: self.open_example(p))
            menu.addAction(action)
        menu.exec(self.examples_button.mapToGlobal(self.examples_button.rect().bottomLeft()))

    def open_example(self, path):
        # examples open as copies, so saving never changes the originals
        self.open_text(path.read_text(encoding="utf-8"), path.name)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.is_dir():
                self.files_panel.set_folder(path)
                self.show_sidebar(1)
            elif path.is_file():
                self.open_path(path)

    # ---------- menus, palette, dialogs ----------

    def show_learn(self):
        if self.learn_dialog is None:
            self.learn_dialog = LearnDialog(self)
        self.learn_dialog.show()
        self.learn_dialog.raise_()

    def show_more_menu(self):
        menu = QMenu(self)
        actions = [
            ("🐍  Show as Python", self.show_as_python),
            ("📦  Make an App…", lambda: make_app(self)),
            ("🧩  Extensions", lambda: self.show_sidebar(2)),
            ("✨  AI helper", lambda: self.show_sidebar(3)),
            ("🌍  Community…", lambda: CommunityDialog(self).exec()),
            ("⌘  All commands…", self.show_palette),
            ("⚙️  Settings…", lambda: self.open_settings()),
            ("⚡  About Sparky…", lambda: AboutDialog(self).exec()),
        ]
        for label, slot in actions:
            action = QAction(label, menu)
            action.triggered.connect(lambda _=False, s=slot: s())
            menu.addAction(action)
        menu.exec(self.more_button.mapToGlobal(self.more_button.rect().bottomLeft()))

    def open_settings(self, tab="General"):
        SettingsDialog(self, tab).exec()

    def show_welcome(self):
        WelcomeDialog(self).exec()
        self.settings.setValue("show_welcome", False)

    def commands(self):
        items = [
            ("Run", "Ctrl/Cmd+Return", self.run_program),
            ("Stop", "", self.stop_program),
            ("New file", "Ctrl/Cmd+N", self.new_file),
            ("Open file…", "Ctrl/Cmd+O", self.open_file),
            ("Open folder…", "", self.files_panel.choose_folder),
            ("Go to file…", "Ctrl/Cmd+P", self.quick_open),
            ("Save", "Ctrl/Cmd+S", self.save_file),
            ("Save as…", "Ctrl/Cmd+Shift+S", self.save_as),
            ("Close tab", "Ctrl/Cmd+W", lambda: self.close_tab(self.tabs.currentIndex())),
            ("Find", "Ctrl/Cmd+F", lambda: self.find_bar.open(False)),
            ("Find and replace", "Ctrl/Cmd+Alt+F", lambda: self.find_bar.open(True)),
            ("Go to line…", "Ctrl/Cmd+G", self.go_to_line),
            ("Toggle comment", "Ctrl/Cmd+/", lambda: self.editor.toggle_comment()),
            ("Show as Python", "", self.show_as_python),
            ("Toggle light / dark", "", self.toggle_theme),
            ("Color theme…", "", self.pick_theme),
            ("Show blocks", "", lambda: self.show_sidebar(0)),
            ("Show files", "", lambda: self.show_sidebar(1)),
            ("Extensions: find themes and snippets", "", lambda: self.show_sidebar(2)),
            ("AI helper", "", lambda: self.show_sidebar(3)),
            ("AI: explain my code", "", lambda: (self.show_sidebar(3),
                                                 self.ai_panel.ask("Explain what my code does, step by step."))),
            ("Toggle sidebar", "Ctrl/Cmd+B", self.toggle_sidebar),
            ("Learn: lessons", "", self.show_learn),
            ("Make an App…", "", lambda: make_app(self)),
            ("Settings", "", lambda: self.open_settings()),
            ("Settings: AI", "", lambda: self.open_settings("AI")),
            ("Settings: languages", "", lambda: self.open_settings("Languages")),
            ("Zoom in", "Ctrl/Cmd+=", lambda: self.set_font_size_all(self.font_size + 1)),
            ("Zoom out", "Ctrl/Cmd+-", lambda: self.set_font_size_all(self.font_size - 1)),
            ("About Sparky", "", lambda: AboutDialog(self).exec()),
        ]
        for path in sorted(EXAMPLES_DIR.glob("*.spark")) if EXAMPLES_DIR.is_dir() else []:
            items.append((f"Example: {path.stem.replace('_', ' ').title()}", "",
                          lambda p=path: self.open_example(p)))
        return items

    def show_palette(self):
        CommandPalette(self, self.commands(), "Type a command…").exec()

    def quick_open(self):
        items = []
        seen = set()
        for editor in self.editors():
            items.append((f"● {editor.display_name()}", "open tab",
                          lambda e=editor: self.tabs.setCurrentWidget(e)))
            if editor.path:
                seen.add(editor.path.resolve())
        folder = self.files_panel.folder
        for path in self.files_panel.all_files():
            if path.resolve() in seen:
                continue
            label = str(path.relative_to(folder)) if folder else path.name
            items.append((label, "", lambda p=path: self.open_path(p)))
        hint = "Type a file name…" if folder else "Type a file name… (open a folder to see its files)"
        CommandPalette(self, items, hint).exec()

    def pick_theme(self):
        items = [("Light", "", lambda: self.set_theme("light")),
                 ("Dark", "", lambda: self.set_theme("dark"))]
        for key, label, _dark in vscode.all_themes():
            items.append((f"{label}", "VS Code theme", lambda k=key: self.set_theme(k)))
        items.append(("Find more themes on Open VSX…", "", lambda: self.show_sidebar(2)))
        CommandPalette(self, items, "Pick a color theme…").exec()

    def go_to_line(self):
        editor = self.editor
        line, ok = QInputDialog.getInt(self, "Go to line", f"Line (1–{editor.blockCount()}):",
                                       editor.textCursor().blockNumber() + 1, 1,
                                       editor.blockCount())
        if ok:
            editor.goto_line(line)

    def show_as_python(self):
        editor = self.editor
        if editor.language.id != "sparky":
            self.status.showMessage("Show as Python works on Sparky programs.")
            return
        try:
            code = to_python(editor.toPlainText())
        except SparkyError as err:
            self.console_write(err.pretty(), self.palette_colors["accent"])
            if err.line:
                editor.set_error_line(err.line)
            return
        name = (editor.path.stem if editor.path else Path(editor.display_name()).stem) + ".py"
        self.new_tab(code, None, languages.BY_ID["python"], name)
        self.status.showMessage("Here's your program in Python. Press Run to try it — "
                                "drawings need a Python with turtle graphics.")

    def insert_ai_code(self, lang, code):
        aliases = {"py": "python", "python3": "python", "js": "javascript",
                   "spark": "sparky", "": ""}
        lang = aliases.get(lang, lang)
        editor = self.editor
        if lang in languages.BY_ID and lang != editor.language.id:
            ext = languages.BY_ID[lang].extensions[0]
            self.new_tab(code, None, languages.BY_ID[lang], f"from-ai{ext}")
            return
        editor.insert_snippet(code)

    def vscode_changed(self):
        self.snippet_cache = {}
        for editor in self.editors():
            editor.snippets = self.snippets(editor.language.id)

    def update_cursor_label(self):
        editor = self.tabs.currentWidget()
        if editor is None:
            return
        cursor = editor.textCursor()
        self.cursor_label.setText(f"Ln {cursor.blockNumber() + 1}, Col {cursor.positionInBlock() + 1}")

    # ---------- settings & session ----------

    def load_settings(self):
        s = self.settings
        key = s.value("theme", "", type=str)
        if not key:
            key = "dark" if s.value("dark", False, type=bool) else "light"
        self.theme_key = key
        self.speed_slider.setValue(s.value("speed", 5, type=int))
        self.font_size = s.value("font_size", 15, type=int)
        self.completions_enabled = s.value("autocomplete", True, type=bool)
        self.sound_bank.enabled = s.value("sounds", True, type=bool)
        self.sound_bank.volume = s.value("volume", 80, type=int) / 100
        geometry = s.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

    def save_settings(self):
        s = self.settings
        s.setValue("theme", self.theme_key)
        s.setValue("dark", self.dark)
        s.setValue("speed", self.speed_slider.value())
        s.setValue("font_size", self.font_size)
        s.setValue("autocomplete", self.completions_enabled)
        s.setValue("sounds", self.sound_bank.enabled)
        s.setValue("volume", int(self.sound_bank.volume * 100))
        s.setValue("geometry", self.saveGeometry())
        s.setValue("open_files", [str(e.path) for e in self.editors() if e.path])

    def restore_session(self):
        folder = self.settings.value("folder", "", type=str)
        if folder and Path(folder).is_dir():
            self.files_panel.set_folder(Path(folder))
        files = self.settings.value("open_files", [], type=list) or []
        for name in files:
            if Path(name).is_file():
                self.open_path(Path(name))
        if self.tabs.count() == 0:
            self.new_tab(WELCOME, title="welcome.spark")
        self.tab_changed(self.tabs.currentIndex())

    def set_font_size_all(self, size):
        self.font_size = max(10, min(28, size))
        for editor in self.editors():
            editor.set_font_size(self.font_size)

    # ---------- theming ----------

    def set_theme(self, key):
        palette = None
        if key and key.startswith("vscode:"):
            palette = vscode.theme_palette(key, LIGHT, DARK)
        if palette is None:
            key = "dark" if key == "dark" else "light"
            palette = DARK if key == "dark" else LIGHT
        self.theme_key = key
        self.palette_colors = palette
        self.dark = is_dark(palette)
        icon = Path(tempfile.gettempdir()) / f"sparky-close-{palette['muted'].lstrip('#')}.svg"
        if not icon.exists():
            icon.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">'
                            f'<path d="M4 4l8 8M12 4l-8 8" stroke="{palette["muted"]}" '
                            'stroke-width="1.6" stroke-linecap="round"/></svg>')
        QApplication.instance().setStyleSheet(
            build_qss(palette) + "QTabBar::close-button { image: url(%s); "
            "subcontrol-position: right; margin: 2px; border-radius: 4px; }"
            "QTabBar::close-button:hover { background: %s; }"
            % (icon.as_posix(), palette["panel2"]))
        for editor in self.editors():
            editor.apply_palette(palette)
        self.stage.apply_palette(palette)
        self.blocks.apply_palette(palette)
        self.ai_panel.apply_palette()
        self.theme_button.setText("☀️" if self.dark else "\U0001f319")

    def apply_theme(self):
        self.set_theme(self.theme_key)

    def toggle_theme(self):
        self.set_theme("light" if self.dark else "dark")

    # ---------- console ----------

    def console_write(self, text, color=None):
        style = f' style="color:{color}"' if color else ""
        self.console.appendHtml(f"<span{style}>{html.escape(text)}</span>")
        bar = self.console.verticalScrollBar()
        bar.setValue(bar.maximum())

    def console_insert(self, text, color=None):
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        if color:
            fmt.setForeground(QColor(color))
        cursor.insertText(text, fmt)
        bar = self.console.verticalScrollBar()
        bar.setValue(bar.maximum())

    # ---------- running ----------

    def reset_run_view(self):
        self.stage_model.reset()
        self.console.clear()
        for editor in self.editors():
            editor.set_running_line(None)
            if editor.error_line:
                editor.error_line = None
                editor.refresh_highlights()
        self.ask_input.setEnabled(False)

    def is_running(self):
        return bool(self.runner and self.runner.isRunning()) or self.proc.is_running()

    def run_program(self):
        if self.is_running():
            return
        editor = self.editor
        lang = editor.language
        self.last_error = ""
        if lang.runner == "stage":
            self.run_sparky(editor)
        elif lang.runner == "browser":
            if editor.path is None and not self.save_as(editor):
                return
            self.save_file(editor)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(editor.path)))
            self.status.showMessage(f"Opened {editor.path.name} in your web browser.")
        else:
            self.run_process(editor)

    def run_sparky(self, editor):
        self.reset_run_view()
        self.run_editor = editor
        self.runner = RunnerThread(editor.toPlainText(), self.stage_model,
                                   self.speed_slider.value())
        self.runner.sig_say.connect(self.console_write)
        self.runner.sig_ask.connect(self.on_ask)
        self.runner.sig_sound.connect(self.sound_bank.play)
        self.runner.sig_line.connect(editor.set_running_line)
        self.runner.sig_error.connect(self.on_error)
        self.runner.sig_done.connect(self.on_done)
        self.set_running(True)
        self.status.showMessage("Running...")
        self.runner.start()

    def run_process(self, editor):
        path = editor.path
        if path is not None:
            if editor.document().isModified():
                self.save_file(editor)
        else:
            scratch = Path(tempfile.gettempdir()) / "sparky-scratch"
            scratch.mkdir(exist_ok=True)
            ext = editor.language.extensions[0] if editor.language.extensions else ".txt"
            path = scratch / (Path(editor.display_name()).stem + ext)
            path.write_text(editor.toPlainText(), encoding="utf-8")
        command, problem = languages.run_command(editor.language, path, self.settings)
        self.reset_run_view()
        if problem:
            self.console_write(problem, self.palette_colors["accent"])
            return
        self.run_editor = editor
        self.run_path = path
        shown = " ".join(Path(c).name if i == 0 else (Path(c).name if c == str(path) else c)
                         for i, c in enumerate(command))
        self.console_write(f"▶ {shown}", self.palette_colors["muted"])
        self.console_insert("\n")
        self.ask_input.setEnabled(True)
        self.ask_input.setPlaceholderText("type here to answer input() — press Enter")
        self.set_running(True)
        self.status.showMessage("Running...")
        self.proc.start(command, path.parent)

    def set_running(self, running):
        self.run_button.setEnabled(not running)
        self.stop_button.setEnabled(running)

    def on_proc_output(self, text, is_error):
        self.console_insert(text, self.palette_colors["accent"] if is_error else None)

    def on_proc_error_line(self, file, line):
        tail = self.proc.stderr_text.strip().splitlines()
        self.last_error = "\n".join(tail[-6:])
        try:
            same = self.run_path and Path(file).resolve() == self.run_path.resolve()
        except OSError:
            same = False
        if same and self.run_editor is not None:
            self.run_editor.set_error_line(line)

    def on_proc_done(self, code):
        self.set_running(False)
        self.ask_input.setEnabled(False)
        self.ask_input.setPlaceholderText("answers show up here...")
        if code == -1:
            self.console_write("■ Stopped.", self.palette_colors["muted"])
            self.status.showMessage("Stopped.")
        elif code == 0:
            self.status.showMessage("Done ✓")
        else:
            if not self.last_error:
                self.last_error = "\n".join(self.proc.stderr_text.strip().splitlines()[-6:])
            self.console_write(f"■ The program stopped with exit code {code}.",
                               self.palette_colors["muted"])
            self.status.showMessage("There's a problem — check the console.")

    def stop_program(self):
        if self.runner and self.runner.isRunning():
            self.runner.stop()
        if self.proc.is_running():
            self.proc.stop()
        self.status.showMessage("Stopped.")

    def speed_changed(self, value):
        if self.runner and self.runner.isRunning():
            self.runner.set_speed(value)

    def on_ask(self, prompt):
        self.console_write("❓ " + prompt, self.palette_colors["accent2"])
        self.ask_input.setEnabled(True)
        self.ask_input.setFocus()

    def send_answer(self):
        text = self.ask_input.text()
        if self.proc.is_running():
            self.console_insert(text + "\n", self.palette_colors["muted"])
            self.ask_input.clear()
            self.proc.write(text)
            return
        if not (self.runner and self.runner.isRunning()) or not self.ask_input.isEnabled():
            return
        self.console_write("✏️ " + text, self.palette_colors["muted"])
        self.ask_input.clear()
        self.ask_input.setEnabled(False)
        self.runner.answer(text)

    def on_error(self, message, line):
        self.last_error = message
        self.console_write(message, self.palette_colors["accent"])
        if line and self.run_editor is not None:
            self.run_editor.set_error_line(line)
        self.status.showMessage("There's a little problem — check the console.")

    def on_done(self, ok):
        self.set_running(False)
        self.ask_input.setEnabled(False)
        editor = self.run_editor
        if editor is not None:
            QTimer.singleShot(600, lambda: editor.set_running_line(None))
        if ok:
            self.status.showMessage("Done ✓")

    # ---------- closing ----------

    def closeEvent(self, event):
        if self.runner and self.runner.isRunning():
            self.runner.stop()
            self.runner.wait(1000)
        if self.proc.is_running():
            self.proc.stop()
        for editor in self.editors():
            if not self.confirm_discard(editor):
                event.ignore()
                return
        self.save_settings()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Sparky")
    icon_path = ASSETS_DIR / "logo_256.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    font = QFont()
    font.setFamilies(HEADING_FONTS)
    font.setPointSize(13)
    app.setFont(font)

    window = MainWindow()
    window.show()
    for arg in sys.argv[1:]:
        if Path(arg).is_file():
            window.open_path(Path(arg))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
