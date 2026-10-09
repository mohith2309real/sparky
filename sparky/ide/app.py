# The Sparky IDE main window (Spark 3).
#
#   top bar:   Sparky · file name · Run / Pause / Step / Stop · speed · commands · theme · help
#   body:      activity bar | Home  — or —  sidebar | editor tabs | stage card + console card
#   bottom:    status bar with the run state, stage x/y, language, cursor, updates, credit
#
# Sparky programs run on the stage; Python, JavaScript and other languages
# run as normal programs with their output in the console. Native Qt all the
# way — no browser engine.

import datetime
import html
import os
import sys
import tempfile
from pathlib import Path

from PyQt6.QtCore import QEvent, Qt, QSettings, QTimer, QUrl
from PyQt6.QtGui import (QAction, QActionGroup, QColor, QDesktopServices, QFont,
                         QGuiApplication, QIcon, QKeySequence, QShortcut, QTextCharFormat,
                         QTextCursor)
from PyQt6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QInputDialog, QLabel,
                             QLineEdit, QMainWindow, QMenu, QMessageBox, QPlainTextEdit,
                             QSplitter, QStackedWidget, QTabWidget, QVBoxLayout, QWidget)

from .. import __version__
from . import design, icons, languages, mascot, prefs, vscode, whats_new
from .ai import AIPanel
from .blocks import BlockPalette
from .dialogs import (AboutDialog, CommunityDialog, FirstRunDialog, WhatsNewDialog,
                      open_site)
from .editor import CodeEditor
from .export import make_app
from .extension_manager import ExtensionManager
from .home import HomePage
from .learn import LearnDialog
from .panels import CommandPalette, ExtensionsPanel, FilesPanel, FindBar
from .process_runner import ProcessRunner
from .runner import RunnerThread
from .settings_dialog import SettingsDialog
from .sounds import SoundBank
from .stage import StageModel, StageView, StageWindow
from .theme import DARK, LIGHT, build_qss, load_fonts
from .tour import TourOverlay, build_steps
from .widgets import (Card, IconButton, Pill, SpeedControl, Toasts, UpdateBar, REDUCE_MOTION,
                      retint, text_button)
from ..lang import SparkyError
from ..lang.to_python import to_python
from ..paths import ASSETS_DIR, EXAMPLES_DIR, USER_DIR, prepare_user_dirs
from ..update.service import UpdateService

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

SIDEBAR = [("blocks", "blocks", "Blocks"), ("files", "files", "Files"),
           ("extensions", "extensions", "Extensions"), ("ai", "ai", "AI helper")]
PRO_ONLY = {"files", "extensions"}
MAX_RECENT = 12


def is_dark(palette):
    return QColor(palette["editor_bg"]).lightness() < 128


def _icon_file(name, color, stroke=2.2):
    path = Path(tempfile.gettempdir()) / f"sparky-{name}-{color.lstrip('#')}.svg"
    if not path.exists():
        path.write_text(icons.svg(name, color, stroke))
    return path.as_posix()


def extra_qss(p):
    """Stylesheet parts that need small icon files (tab close, check marks)."""
    return (
        f"QTabBar::close-button {{ image: url({_icon_file('close', p['muted'])}); "
        f"subcontrol-position: right; margin: 3px; border-radius: 5px; }}"
        f"QTabBar::close-button:hover {{ background: {p['surface2']}; }}"
        f"QCheckBox::indicator:checked {{ image: url({_icon_file('check', p['accent_text'], 3)}); }}"
    )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = prefs.open_settings()
        self.theme_key = "daylight"
        self.palette_colors = LIGHT
        self.dark = False
        self.mode = self.settings.value("mode", "kid", type=str)
        self.font_size = 15
        self.completions_enabled = True
        self.runner = None              # Sparky programs (stage)
        self.run_editor = None
        self.run_path = None
        self.last_error = ""
        self.learn_dialog = None
        self.stage_window = None
        self.tour = None
        self.snippet_cache = {}
        self.untitled = 0
        self.run_count = 0
        self.step_count = 0
        self.block_count = 0

        self.setWindowTitle("Sparky")
        self.resize(1440, 900)
        self.setMinimumSize(980, 620)
        self.setAcceptDrops(True)
        icon_path = ASSETS_DIR / "logo_256.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        prepare_user_dirs()
        self.sound_bank = SoundBank()
        self.extension_manager = ExtensionManager()
        if os.environ.get("SPARKY_SAFE_MODE") != "1":
            self.extension_manager.discover()
        self.proc = ProcessRunner(self)
        self.proc.output.connect(self.on_proc_output)
        self.proc.finished.connect(self.on_proc_done)
        self.proc.error_line.connect(self.on_proc_error_line)
        self.updates = UpdateService(self, self.settings)

        self.stage_model = StageModel()
        self.build_ui()
        self.build_menus()
        self.toasts = Toasts(self)
        self.load_settings()
        self.restore_session()
        self.set_theme(self.theme_key)
        self.set_mode(self.mode)
        self.set_state("", "Ready")
        self.connect_updates()

        if self.settings.value("start_home", True, type=bool):
            self.show_home()
        else:
            self.show_workspace()
        QTimer.singleShot(300, self.after_start)

    # ---------- building the window ----------

    def build_ui(self):
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.setCentralWidget(root)
        root_layout.addWidget(self.build_top_bar())
        self.update_bar = UpdateBar()
        self.update_bar.restart.connect(self.restart_to_update)
        self.update_bar.notes.connect(self.show_whats_new_for_update)
        self.update_bar.later.connect(self.update_bar.hide)
        root_layout.addWidget(self.update_bar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self.build_activity_bar())

        self.center_stack = QStackedWidget()
        self.home_page = HomePage(self)
        self.center_stack.addWidget(self.home_page)
        self.center_stack.addWidget(self.build_workspace())
        body.addWidget(self.center_stack, 1)
        root_layout.addLayout(body, 1)
        self.build_status_bar()
        self.build_shortcuts()

    def build_top_bar(self):
        bar = QWidget()
        bar.setObjectName("TopBar")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 7, 12, 7)
        layout.setSpacing(6)

        self.logo = QLabel()
        self.logo.setPixmap(mascot.pixmap(28, "happy"))
        layout.addWidget(self.logo)
        word = QLabel("Sparky")
        word.setObjectName("Wordmark")
        layout.addWidget(word)
        layout.addSpacing(14)
        self.file_label = QLabel("")
        self.file_label.setObjectName("FileName")
        layout.addWidget(self.file_label)
        layout.addStretch(1)

        self.run_button = text_button("Run", icon="play", object_name="RunButton",
                                      tip="Run this file (Ctrl/Cmd+Enter)")
        self.run_button.clicked.connect(self.run_program)
        layout.addWidget(self.run_button)
        self.pause_button = IconButton("pause", "Pause / resume (F6)", size=16)
        self.pause_button.clicked.connect(self.toggle_pause)
        self.pause_button.setEnabled(False)
        layout.addWidget(self.pause_button)
        self.step_button = text_button("Step", icon="step", object_name="StepButton",
                                       tip="Run one line at a time (F10)")
        self.step_button.clicked.connect(self.step_program)
        layout.addWidget(self.step_button)
        self.stop_button = text_button("Stop", icon="stop", object_name="StopButton",
                                       tip="Stop the program (Shift+F5)")
        self.stop_button.clicked.connect(self.stop_program)
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button)
        layout.addSpacing(10)
        self.speed = SpeedControl()
        self.speed.valueChanged.connect(self.speed_changed)
        self.speed_slider = self.speed
        layout.addWidget(self.speed)
        layout.addStretch(1)

        self.command_button = text_button("Search commands…", icon="search",
                                          object_name="GhostButton",
                                          tip="Every command and setting (Ctrl/Cmd+Shift+P)")
        self.command_button.clicked.connect(self.show_palette)
        layout.addWidget(self.command_button)
        self.theme_button = IconButton("moon", "Switch light / dark")
        self.theme_button.clicked.connect(self.toggle_theme)
        layout.addWidget(self.theme_button)
        self.help_button = IconButton("help", "Help, the tour and updates")
        self.help_button.clicked.connect(self.show_help_menu)
        layout.addWidget(self.help_button)
        return bar

    def build_activity_bar(self):
        bar = QWidget()
        bar.setObjectName("ActivityBar")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(bar)
        layout.setContentsMargins(7, 8, 7, 8)
        layout.setSpacing(4)
        self.activity_buttons = {}

        def add(key, icon_name, tip, slot, checkable=True):
            b = IconButton(icon_name, tip, size=21, checkable=checkable)
            b.setObjectName("ActivityButton")
            b.clicked.connect(slot)
            layout.addWidget(b)
            self.activity_buttons[key] = b
            return b

        add("home", "home", "Home", self.show_home)
        for key, icon_name, tip in SIDEBAR:
            add(key, icon_name, tip, lambda _=False, k=key: self.show_sidebar_named(k, toggle=True))
        layout.addStretch(1)
        add("learn", "learn", "Learn: lessons and challenges", self.show_learn, checkable=False)
        add("settings", "settings", "Settings", lambda: self.open_settings(), checkable=False)
        return bar

    def build_workspace(self):
        self.blocks = BlockPalette(
            self.palette_colors, self.insert_block,
            extra_categories=self.extension_manager.api.block_categories)
        self.files_panel = FilesPanel(self)
        self.ai_panel = AIPanel(self)
        self.extensions_panel = ExtensionsPanel(self)
        self.sidebar = QStackedWidget()
        self.sidebar.setObjectName("SidePanel")
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

        right = QWidget()
        right.setObjectName("SidePanel")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 8, 8, 8)
        column = QSplitter(Qt.Orientation.Vertical)
        column.setObjectName("Workspace")
        column.setChildrenCollapsible(False)
        column.addWidget(self.build_stage_card())
        column.addWidget(self.build_console_card())
        column.setSizes([520, 300])
        right_layout.addWidget(column)
        self.stage_box = right

        self.split = QSplitter(Qt.Orientation.Horizontal)
        self.split.addWidget(self.sidebar)
        self.split.addWidget(center)
        self.split.addWidget(right)
        self.split.setSizes([270, 640, 530])
        self.split.setCollapsible(1, False)
        return self.split

    def build_stage_card(self):
        card = Card("Stage")
        self.stage_card = card
        self.stage = StageView(self.stage_model, self.palette_colors)
        self.stage.mouse_moved.connect(self.stage_mouse)
        self.stage.stage_clicked.connect(self.stage_click)
        tools = QWidget()
        row = QHBoxLayout(tools)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(2)
        self.grid_button = IconButton("grid", "Show the grid (G)", size=16, checkable=True)
        self.grid_button.toggled.connect(self.set_grid)
        snap = IconButton("camera", "Save a snapshot (PNG)", size=16)
        snap.clicked.connect(self.save_snapshot)
        copy = IconButton("copy", "Copy the stage as a picture", size=16)
        copy.clicked.connect(self.copy_stage)
        full = IconButton("fullscreen", "Fullscreen stage (F11)", size=16)
        full.clicked.connect(self.fullscreen_stage)
        clear = IconButton("eraser", "Clear the stage", size=16)
        clear.clicked.connect(self.clear_stage)
        for b in (self.grid_button, snap, copy, full, clear):
            row.addWidget(b)
        self.stage_tools = tools
        card.add_tool(tools)
        card.body.addWidget(self.stage, 1)
        card.body.setContentsMargins(8, 0, 8, 8)
        return card

    def build_console_card(self):
        card = Card("Console")
        self.console_card = card
        copy = IconButton("copy", "Copy everything in the console", size=16)
        copy.clicked.connect(lambda: (QGuiApplication.clipboard().setText(self.console.toPlainText()),
                                      self.toast("Console copied ✓")))
        clear = IconButton("trash", "Clear the console", size=16)
        clear.clicked.connect(lambda: self.console.clear())
        card.add_tool(copy)
        card.add_tool(clear)
        self.console = QPlainTextEdit()
        self.console.setObjectName("Console")
        self.console.setReadOnly(True)
        self.console.setAccessibleName("Console")
        card.body.addWidget(self.console, 1)
        ask_row = QWidget()
        ask_layout = QHBoxLayout(ask_row)
        ask_layout.setContentsMargins(8, 6, 8, 8)
        self.ask_input = QLineEdit()
        self.ask_input.setObjectName("AskInput")
        self.ask_input.setPlaceholderText("answers go here when a program asks…")
        self.ask_input.setAccessibleName("Answer box")
        self.ask_input.setEnabled(False)
        self.ask_input.returnPressed.connect(self.send_answer)
        ask_layout.addWidget(self.ask_input)
        card.body.addWidget(ask_row)
        return card

    def build_status_bar(self):
        self.status = self.statusBar()
        self.state_pill = Pill("Ready")
        self.status.addWidget(self.state_pill)
        self.coords_label = QLabel("")
        self.coords_label.setObjectName("FileLabel")
        self.status.addPermanentWidget(self.coords_label)
        self.lang_label = QLabel("Sparky")
        self.lang_label.setObjectName("FileLabel")
        self.status.addPermanentWidget(self.lang_label)
        self.cursor_label = QLabel("Ln 1, Col 1")
        self.cursor_label.setObjectName("FileLabel")
        self.status.addPermanentWidget(self.cursor_label)
        self.update_label = text_button("", object_name="LinkButton")
        self.update_label.clicked.connect(lambda: self.open_settings("Updates"))
        self.update_label.hide()
        self.status.addPermanentWidget(self.update_label)
        credit = text_button("⚡ by Mohith", object_name="GhostButton", tip="Visit Mohith's website")
        credit.clicked.connect(open_site)
        self.status.addPermanentWidget(credit)

    def build_shortcuts(self):
        shortcuts = [
            ("Ctrl+Return", self.run_program), ("Meta+Return", self.run_program),
            ("F5", self.run_program), ("Shift+F5", self.stop_program),
            ("F6", self.toggle_pause), ("F10", self.step_program),
            ("Ctrl+W", lambda: self.close_tab(self.tabs.currentIndex())),
            ("Ctrl+F", lambda: self.find_bar.open(False)),
            ("Ctrl+Alt+F", lambda: self.find_bar.open(True)),
            ("Ctrl+G", self.go_to_line), ("Ctrl+/", lambda: self.editor.toggle_comment()),
            ("Ctrl+Shift+P", self.show_palette), ("F1", self.show_palette),
            ("Ctrl+K", self.show_palette),
            ("Ctrl+P", self.quick_open), ("Ctrl+B", self.toggle_sidebar),
            ("Ctrl+=", lambda: self.set_font_size_all(self.font_size + 1)),
            ("Ctrl+-", lambda: self.set_font_size_all(self.font_size - 1)),
            ("Ctrl+0", lambda: self.set_font_size_all(15)),
            ("Ctrl+Tab", lambda: self.cycle_tab(1)), ("Ctrl+Shift+Tab", lambda: self.cycle_tab(-1)),
            ("F11", self.fullscreen_stage), ("Ctrl+Shift+H", self.show_home),
        ]
        for keys, slot in shortcuts:
            QShortcut(QKeySequence(keys), self, slot)

    def build_menus(self):
        bar = self.menuBar()
        self.menu_actions = {}

        def act(menu, label, slot, keys=None, key=None, checkable=False):
            action = QAction(label, self)
            if keys:
                action.setShortcut(QKeySequence(keys))
                action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
            action.setCheckable(checkable)
            action.triggered.connect(lambda checked=False, s=slot: s())
            menu.addAction(action)
            if key:
                self.menu_actions[key] = action
            return action

        file_menu = bar.addMenu("&File")
        act(file_menu, "New program", self.new_file, "Ctrl+N")
        act(file_menu, "Open…", self.open_file, "Ctrl+O")
        act(file_menu, "Open folder…", self.open_folder_dialog, key="open_folder")
        self.recent_menu = file_menu.addMenu("Open recent")
        self.recent_menu.aboutToShow.connect(self.fill_recent_menu)
        file_menu.addSeparator()
        act(file_menu, "Save", self.save_file, "Ctrl+S")
        act(file_menu, "Save as…", self.save_as, "Ctrl+Shift+S")
        file_menu.addSeparator()
        act(file_menu, "Make an App…", lambda: make_app(self))
        act(file_menu, "Community and gallery…", lambda: CommunityDialog(self).exec())
        file_menu.addSeparator()
        act(file_menu, "Close tab", lambda: self.close_tab(self.tabs.currentIndex()))
        quit_action = act(file_menu, "Quit Sparky", self.close, "Ctrl+Q")
        quit_action.setMenuRole(QAction.MenuRole.QuitRole)

        edit = bar.addMenu("&Edit")
        act(edit, "Undo", lambda: self.editor.undo())
        act(edit, "Redo", lambda: self.editor.redo())
        edit.addSeparator()
        act(edit, "Cut", lambda: self.editor.cut())
        act(edit, "Copy", lambda: self.editor.copy())
        act(edit, "Paste", lambda: self.editor.paste())
        act(edit, "Select all", lambda: self.editor.selectAll())
        edit.addSeparator()
        act(edit, "Find", lambda: self.find_bar.open(False))
        act(edit, "Find and replace", lambda: self.find_bar.open(True))
        act(edit, "Go to line…", self.go_to_line)
        act(edit, "Toggle comment", lambda: self.editor.toggle_comment())

        view = bar.addMenu("&View")
        act(view, "Home", self.show_home)
        act(view, "Blocks", lambda: self.show_sidebar_named("blocks"))
        act(view, "Files", lambda: self.show_sidebar_named("files"), key="view_files")
        act(view, "Extensions", lambda: self.show_sidebar_named("extensions"), key="view_extensions")
        act(view, "AI helper", lambda: self.show_sidebar_named("ai"))
        act(view, "Toggle sidebar", self.toggle_sidebar)
        view.addSeparator()
        themes = view.addMenu("Theme")
        group = QActionGroup(self)
        self.theme_actions = {}
        for key, palette in design.THEMES.items():
            a = act(themes, palette["name"], lambda k=key: self.set_theme(k), checkable=True)
            group.addAction(a)
            self.theme_actions[key] = a
        themes.addSeparator()
        act(themes, "VS Code themes…", self.pick_theme)
        modes = view.addMenu("Mode")
        mode_group = QActionGroup(self)
        self.mode_actions = {}
        for key, label in (("kid", "Kid mode"), ("pro", "Pro mode")):
            a = act(modes, label, lambda k=key: self.set_mode(k), checkable=True)
            mode_group.addAction(a)
            self.mode_actions[key] = a
        view.addSeparator()
        act(view, "Zoom in", lambda: self.set_font_size_all(self.font_size + 1))
        act(view, "Zoom out", lambda: self.set_font_size_all(self.font_size - 1))
        act(view, "Actual size", lambda: self.set_font_size_all(15))
        act(view, "Show the stage grid", lambda: self.set_grid(not self.stage.show_grid))
        act(view, "Fullscreen stage", self.fullscreen_stage)

        run = bar.addMenu("&Run")
        act(run, "Run", self.run_program)
        act(run, "Pause / resume", self.toggle_pause)
        act(run, "Step", self.step_program)
        act(run, "Stop", self.stop_program)
        run.addSeparator()
        act(run, "Show as Python", self.show_as_python)
        act(run, "Save a snapshot of the stage…", self.save_snapshot)
        act(run, "Clear the stage", self.clear_stage)

        learn = bar.addMenu("&Learn")
        act(learn, "Lessons and challenges", self.show_learn)
        self.examples_menu = learn.addMenu("Examples")
        for path in sorted(EXAMPLES_DIR.glob("*.spark")) if EXAMPLES_DIR.is_dir() else []:
            act(self.examples_menu, path.stem.replace("_", " ").title(),
                lambda p=path: self.open_example(p))
        act(learn, "Take the tour", self.start_tour)

        help_menu = bar.addMenu("&Help")
        self.help_menu = help_menu
        act(help_menu, "Take the tour", self.start_tour)
        act(help_menu, "What's new", self.show_whats_new)
        act(help_menu, "Language guide", self.open_guide)
        act(help_menu, "Check for updates…", lambda: self.check_updates(manual=True))
        help_menu.addSeparator()
        act(help_menu, "Sparky website", lambda: QDesktopServices.openUrl(QUrl("https://sparky-code.web.app")))
        act(help_menu, "Mohith's website", open_site)
        act(help_menu, "Open logs folder", self.open_logs)
        about = act(help_menu, "About Sparky", lambda: AboutDialog(self).exec())
        about.setMenuRole(QAction.MenuRole.AboutRole)
        settings = act(help_menu, "Settings…", lambda: self.open_settings(), "Ctrl+,")
        settings.setMenuRole(QAction.MenuRole.PreferencesRole)

    # ---------- home and sidebar ----------

    def show_home(self):
        self.home_page.refresh()
        self.center_stack.setCurrentIndex(0)
        self.activity_buttons["home"].setChecked(True)
        for key, _icon, _tip in SIDEBAR:
            self.activity_buttons[key].setChecked(False)
        self.setWindowTitle("Sparky")
        self.file_label.setText("Home")

    def show_workspace(self):
        if self.center_stack.currentIndex() != 1:
            self.center_stack.setCurrentIndex(1)
            self.activity_buttons["home"].setChecked(False)
            if self.sidebar.isVisible():
                self.activity_buttons[SIDEBAR[self.sidebar.currentIndex()][0]].setChecked(True)
            self.update_file_label()

    def show_sidebar_named(self, key, toggle=False):
        index = [k for k, _i, _t in SIDEBAR].index(key)
        was_home = self.center_stack.currentIndex() == 0
        self.show_workspace()
        if toggle and self.sidebar.isVisible() and self.sidebar.currentIndex() == index \
                and not was_home:
            self.sidebar.hide()
            self.activity_buttons[key].setChecked(False)
            return
        self.sidebar.setCurrentIndex(index)
        self.sidebar.show()
        for k, _i, _t in SIDEBAR:
            self.activity_buttons[k].setChecked(k == key)
        self.activity_buttons["home"].setChecked(False)
        if key == "ai":
            sizes = self.split.sizes()
            if sizes[0] < 320:
                self.split.setSizes([340, max(420, sizes[1] - (340 - sizes[0])), sizes[2]])

    def show_sidebar(self, index):
        self.show_sidebar_named(SIDEBAR[index][0])

    def toggle_sidebar(self):
        self.show_sidebar_named(SIDEBAR[self.sidebar.currentIndex()][0], toggle=True)

    def set_mode(self, mode):
        self.mode = "pro" if mode == "pro" else "kid"
        self.settings.setValue("mode", self.mode)
        pro = self.mode == "pro"
        for key in PRO_ONLY:
            self.activity_buttons[key].setVisible(pro)
        for key in ("view_files", "view_extensions", "open_folder"):
            if key in self.menu_actions:
                self.menu_actions[key].setVisible(pro)
        self.lang_label.setVisible(pro)
        self.command_button.setText("Search commands…" if pro else "")
        if self.mode_actions:
            self.mode_actions[self.mode].setChecked(True)
        current = SIDEBAR[self.sidebar.currentIndex()][0]
        if not pro and current in PRO_ONLY:
            self.sidebar.setCurrentIndex(0)

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
        self.show_workspace()
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
        if editor is None or self.center_stack.currentIndex() == 0:
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
        stage_lang = lang.runner == "stage"
        self.stage_card.setVisible(stage_lang)
        self.speed.setEnabled(stage_lang)
        self.step_button.setEnabled(stage_lang and not self.proc.is_running())
        runnable = lang.runner is not None or \
            (editor.path and editor.path.suffix.lower() in languages.custom_commands(self.settings))
        self.run_button.setToolTip("Run this file (Ctrl/Cmd+Enter)" if runnable else
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
        self.show_workspace()
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
        start = str(self.files_panel.folder or USER_DIR)
        paths, _ = QFileDialog.getOpenFileNames(self, "Open files", start,
                                                languages.open_dialog_filter())
        for path in paths:
            self.open_path(Path(path))

    def open_folder_dialog(self):
        self.show_sidebar_named("files")
        self.files_panel.choose_folder()

    def recent_files(self):
        return self.settings.value("recent_files", [], type=list) or []

    def remember_recent(self, path):
        path = str(Path(path).resolve())
        items = [p for p in self.recent_files() if p != path]
        items.insert(0, path)
        self.settings.setValue("recent_files", items[:MAX_RECENT])

    def fill_recent_menu(self):
        self.recent_menu.clear()
        items = [p for p in self.recent_files() if Path(p).is_file()]
        if not items:
            self.recent_menu.addAction("Nothing yet").setEnabled(False)
        for p in items:
            action = self.recent_menu.addAction(Path(p).name)
            action.setToolTip(p)
            action.triggered.connect(lambda _=False, path=p: self.open_path(Path(path)))

    def open_path(self, path):
        path = Path(path).resolve()
        for editor in self.editors():
            if editor.path and editor.path.resolve() == path:
                self.tabs.setCurrentWidget(editor)
                self.show_workspace()
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
        current = self.tabs.currentWidget()
        if current is not None and current.path is None and \
                not current.document().isModified() and not current.toPlainText().strip():
            self.tabs.removeTab(self.tabs.indexOf(current))
        editor = self.new_tab(data.decode("utf-8", "replace"), path)
        self.remember_recent(path)
        self.status.showMessage(f"Opened {path.name}", 3000)
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
        self.remember_recent(editor.path)
        self.toast(f"Saved {editor.path.name} ✓")
        return True

    def save_as(self, editor=None):
        editor = editor or self.editor
        folder = self.files_panel.folder or USER_DIR
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
                self.show_sidebar_named("files")
            elif path.is_file():
                self.open_path(path)

    # ---------- menus, palette, dialogs ----------

    def show_learn(self):
        if self.learn_dialog is None:
            self.learn_dialog = LearnDialog(self)
        self.learn_dialog.show()
        self.learn_dialog.raise_()

    def next_lesson_title(self):
        return "Lessons from your first program to games."

    def open_guide(self):
        from ..paths import RESOURCES
        guide = RESOURCES / "GUIDE.md"
        if guide.exists():
            self.open_text(guide.read_text(encoding="utf-8"), "GUIDE.md", "markdown")

    def show_help_menu(self):
        menu = QMenu(self)
        p = self.palette_colors
        for label, icon_name, slot in [
            ("Take the tour", "tour", self.start_tour),
            ("What's new", "star", self.show_whats_new),
            ("Language guide", "learn", self.open_guide),
            ("Check for updates…", "refresh", lambda: self.check_updates(manual=True)),
            ("Settings", "settings", lambda: self.open_settings()),
            ("About Sparky", "info", lambda: AboutDialog(self).exec()),
        ]:
            action = menu.addAction(icons.icon(icon_name, p["muted"], 16), label)
            action.triggered.connect(lambda _=False, s=slot: s())
        menu.exec(self.help_button.mapToGlobal(self.help_button.rect().bottomLeft()))

    def open_settings(self, tab="General"):
        SettingsDialog(self, tab).exec()

    def show_whats_new(self):
        WhatsNewDialog(self).exec()

    def show_whats_new_for_update(self):
        update = self.updates.staged or self.updates.update
        WhatsNewDialog(self, update=update).exec()

    def open_logs(self):
        from .crash import logs_dir
        folder = logs_dir()
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def commands(self):
        items = [
            ("Run", "Ctrl/Cmd+Return", self.run_program),
            ("Pause / resume", "F6", self.toggle_pause),
            ("Step: run one line", "F10", self.step_program),
            ("Stop", "Shift+F5", self.stop_program),
            ("Home", "", self.show_home),
            ("New program", "Ctrl/Cmd+N", self.new_file),
            ("Open file…", "Ctrl/Cmd+O", self.open_file),
            ("Open folder…", "", self.open_folder_dialog),
            ("Go to file…", "Ctrl/Cmd+P", self.quick_open),
            ("Save", "Ctrl/Cmd+S", self.save_file),
            ("Save as…", "Ctrl/Cmd+Shift+S", self.save_as),
            ("Close tab", "Ctrl/Cmd+W", lambda: self.close_tab(self.tabs.currentIndex())),
            ("Find", "Ctrl/Cmd+F", lambda: self.find_bar.open(False)),
            ("Find and replace", "Ctrl/Cmd+Alt+F", lambda: self.find_bar.open(True)),
            ("Go to line…", "Ctrl/Cmd+G", self.go_to_line),
            ("Toggle comment", "Ctrl/Cmd+/", lambda: self.editor.toggle_comment()),
            ("Show as Python", "", self.show_as_python),
            ("Stage: show / hide grid", "", lambda: self.set_grid(not self.stage.show_grid)),
            ("Stage: save a snapshot", "", self.save_snapshot),
            ("Stage: copy as a picture", "", self.copy_stage),
            ("Stage: fullscreen", "F11", self.fullscreen_stage),
            ("Stage: clear", "", self.clear_stage),
            ("Toggle light / dark", "", self.toggle_theme),
            ("Color theme…", "", self.pick_theme),
            ("Kid mode", "", lambda: self.set_mode("kid")),
            ("Pro mode", "", lambda: self.set_mode("pro")),
            ("Show blocks", "", lambda: self.show_sidebar_named("blocks")),
            ("Show files", "", lambda: self.show_sidebar_named("files")),
            ("Extensions: find themes and snippets", "", lambda: self.show_sidebar_named("extensions")),
            ("AI helper", "", lambda: self.show_sidebar_named("ai")),
            ("AI: explain my code", "", lambda: (self.show_sidebar_named("ai"),
                                                 self.ai_panel.ask("Explain what my code does, step by step."))),
            ("Toggle sidebar", "Ctrl/Cmd+B", self.toggle_sidebar),
            ("Learn: lessons", "", self.show_learn),
            ("Take the tour", "", self.start_tour),
            ("What's new", "", self.show_whats_new),
            ("Check for updates", "", lambda: self.check_updates(manual=True)),
            ("Make an App…", "", lambda: make_app(self)),
            ("Settings", "Ctrl/Cmd+,", lambda: self.open_settings()),
            ("Settings: updates", "", lambda: self.open_settings("Updates")),
            ("Settings: AI", "", lambda: self.open_settings("AI")),
            ("Settings: languages", "", lambda: self.open_settings("Languages")),
            ("Settings: accessibility", "", lambda: self.open_settings("Accessibility")),
            ("Diagnostics and logs", "", lambda: self.open_settings("About")),
            ("Open logs folder", "", self.open_logs),
            ("Zoom in", "Ctrl/Cmd+=", lambda: self.set_font_size_all(self.font_size + 1)),
            ("Zoom out", "Ctrl/Cmd+-", lambda: self.set_font_size_all(self.font_size - 1)),
            ("About Sparky", "", lambda: AboutDialog(self).exec()),
        ]
        for key, palette in design.THEMES.items():
            items.append((f"Theme: {palette['name']}", "", lambda k=key: self.set_theme(k)))
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
                          lambda e=editor: (self.tabs.setCurrentWidget(e), self.show_workspace())))
            if editor.path:
                seen.add(editor.path.resolve())
        for p in self.recent_files():
            path = Path(p)
            if path.is_file() and path.resolve() not in seen:
                seen.add(path.resolve())
                items.append((path.name, "recent", lambda q=path: self.open_path(q)))
        folder = self.files_panel.folder
        for path in self.files_panel.all_files():
            if path.resolve() in seen:
                continue
            label = str(path.relative_to(folder)) if folder else path.name
            items.append((label, "", lambda q=path: self.open_path(q)))
        hint = "Type a file name…"
        CommandPalette(self, items, hint).exec()

    def pick_theme(self):
        items = [(palette["name"], "built in", lambda k=key: self.set_theme(k))
                 for key, palette in design.THEMES.items()]
        for key, label, _dark in vscode.all_themes():
            items.append((f"{label}", "VS Code theme", lambda k=key: self.set_theme(k)))
        items.append(("Find more themes on Open VSX…", "", lambda: self.show_sidebar_named("extensions")))
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
            self.toast("Show as Python works on Sparky programs.")
            return
        try:
            code = to_python(editor.toPlainText())
        except SparkyError as err:
            self.console_write(err.pretty(), self.palette_colors["danger"])
            if err.line:
                editor.set_error_line(err.line)
            return
        name = (editor.path.stem if editor.path else Path(editor.display_name()).stem) + ".py"
        self.new_tab(code, None, languages.BY_ID["python"], name)
        self.status.showMessage("Here's your program in Python. Press Run to try it — "
                                "drawings need a Python with turtle graphics.", 6000)

    def insert_block(self, snippet):
        self.show_workspace()
        self.editor.insert_snippet(snippet)
        self.block_count += 1

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

    def toast(self, text, ms=2200):
        self.toasts.show(text, ms)

    # ---------- stage tools ----------

    def set_grid(self, on):
        self.stage.set_grid(bool(on))
        if self.grid_button.isChecked() != bool(on):
            self.grid_button.blockSignals(True)
            self.grid_button.setChecked(bool(on))
            self.grid_button.blockSignals(False)
        self.settings.setValue("stage_grid", bool(on))

    def stage_mouse(self, point):
        if point is None:
            self.coords_label.setText("")
        else:
            self.coords_label.setText(f"x {point[0]:.0f}, y {point[1]:.0f}")

    def stage_click(self, x, y):
        if not self.is_running():
            QGuiApplication.clipboard().setText(f"{x:.0f} {y:.0f}")
            self.toast(f"Copied {x:.0f} {y:.0f} — paste it after goto")

    def save_snapshot(self):
        folder = USER_DIR / "Snapshots"
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H.%M.%S")
        path, _ = QFileDialog.getSaveFileName(self, "Save a snapshot", str(folder / f"Stage {stamp}.png"),
                                              "PNG images (*.png)")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        if self.stage.render_image(scale=2).save(path):
            self.toast(f"Saved {Path(path).name} ✓")
        else:
            self.toast("Couldn't save the snapshot.")

    def copy_stage(self):
        QGuiApplication.clipboard().setImage(self.stage.render_image(scale=2))
        self.toast("Stage copied as a picture ✓")

    def fullscreen_stage(self):
        if self.stage_window is not None and self.stage_window.isVisible():
            self.stage_window.close()
            return
        self.stage_window = StageWindow(self.stage_model, self.palette_colors)
        self.stage_window.showFullScreen()

    def clear_stage(self):
        if self.is_running():
            self.toast("Stop the program first, then clear the stage.")
            return
        self.stage_model.reset()

    # ---------- settings & session ----------

    def load_settings(self):
        s = self.settings
        key = s.value("theme", "", type=str)
        if not key:
            key = "midnight" if s.value("dark", False, type=bool) else "daylight"
        self.theme_key = design.OLD_NAMES.get(key, key)
        self.speed.setValue(s.value("speed", 5, type=int))
        self.font_size = s.value("font_size", 15, type=int)
        self.completions_enabled = s.value("autocomplete", True, type=bool)
        self.sound_bank.enabled = s.value("sounds", True, type=bool)
        self.sound_bank.volume = s.value("volume", 80, type=int) / 100
        self.set_reduce_motion(s.value("reduce_motion", False, type=bool))
        self.set_grid(s.value("stage_grid", False, type=bool))
        geometry = s.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

    def save_settings(self):
        s = self.settings
        s.setValue("theme", self.theme_key)
        s.setValue("dark", self.dark)
        s.setValue("speed", self.speed.value())
        s.setValue("font_size", self.font_size)
        s.setValue("autocomplete", self.completions_enabled)
        s.setValue("sounds", self.sound_bank.enabled)
        s.setValue("volume", int(self.sound_bank.volume * 100))
        s.setValue("geometry", self.saveGeometry())
        s.setValue("open_files", [str(e.path) for e in self.editors() if e.path])
        s.setValue("mode", self.mode)

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

    def set_reduce_motion(self, on):
        REDUCE_MOTION["on"] = bool(on)

    # ---------- theming ----------

    def set_theme(self, key):
        palette = None
        key = design.OLD_NAMES.get(key, key)
        if key and key.startswith("vscode:"):
            palette = vscode.theme_palette(key, LIGHT, DARK)
            if palette is not None:
                palette = design.complete(palette)
        if palette is None:
            key = key if key in design.THEMES else "daylight"
            palette = design.theme(key)
        self.theme_key = key
        self.palette_colors = palette
        self.dark = is_dark(palette)
        QApplication.instance().setStyleSheet(build_qss(palette) + extra_qss(palette))
        for editor in self.editors():
            editor.apply_palette(palette)
        self.stage.apply_palette(palette)
        if self.stage_window is not None:
            self.stage_window.view.apply_palette(dict(palette, surface="#000000"))
        self.blocks.apply_palette(palette)
        self.ai_panel.apply_palette()
        retint(palette)
        self.theme_button.set_icon_name("sun" if self.dark else "moon", palette)
        if key in getattr(self, "theme_actions", {}):
            self.theme_actions[key].setChecked(True)
        self.settings.setValue("theme", key)

    def apply_theme(self):
        self.set_theme(self.theme_key)

    def toggle_theme(self):
        self.set_theme("daylight" if self.dark else "midnight")

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

    def set_state(self, state, text):
        self.state_pill.set_state(state, text)

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

    def run_program(self, step=False):
        if self.is_running():
            if self.runner and self.runner.isRunning() and self.runner._paused:
                self.runner.resume()
            return
        self.show_workspace()
        editor = self.editor
        lang = editor.language
        self.last_error = ""
        self.run_count += 1
        if lang.runner == "stage":
            self.run_sparky(editor, step=step)
        elif lang.runner == "browser":
            if editor.path is None and not self.save_as(editor):
                return
            self.save_file(editor)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(editor.path)))
            self.toast(f"Opened {editor.path.name} in your web browser.")
        else:
            self.run_process(editor)

    def run_sparky(self, editor, step=False):
        self.reset_run_view()
        self.run_editor = editor
        self.runner = RunnerThread(editor.toPlainText(), self.stage_model, self.speed.value())
        self.runner.sig_say.connect(self.console_write)
        self.runner.sig_ask.connect(self.on_ask)
        self.runner.sig_sound.connect(self.sound_bank.play)
        self.runner.sig_line.connect(editor.set_running_line)
        self.runner.sig_error.connect(self.on_error)
        self.runner.sig_done.connect(self.on_done)
        self.runner.sig_paused.connect(self.on_paused)
        self.runner.sig_resumed.connect(self.on_resumed)
        if step:
            self.runner.step()
        self.set_running(True, stage=True)
        self.set_state("running", "Running…")
        self.runner.start()

    def toggle_pause(self):
        if not (self.runner and self.runner.isRunning()):
            return
        if self.runner._paused:
            self.runner.resume()
        else:
            self.runner.pause()

    def step_program(self):
        self.step_count += 1
        if self.runner and self.runner.isRunning():
            self.runner.step()
            return
        if self.proc.is_running():
            return
        if self.editor.language.runner == "stage":
            self.run_program(step=True)

    def on_paused(self, line):
        self.set_state("paused", f"Paused at line {line}" if line else "Paused")
        self.run_button.setText("Continue")
        self.run_button.setEnabled(True)
        self.pause_button.set_icon_name("play", self.palette_colors)
        self.pause_button.setToolTip("Resume (F6)")

    def on_resumed(self):
        self.set_state("running", "Running…")
        self.run_button.setText("Run")
        self.run_button.setEnabled(False)
        self.pause_button.set_icon_name("pause", self.palette_colors)
        self.pause_button.setToolTip("Pause (F6)")

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
            self.console_write(problem, self.palette_colors["danger"])
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
        self.set_state("running", "Running…")
        self.proc.start(command, path.parent)

    def set_running(self, running, stage=False):
        self.run_button.setText("Run")
        self.run_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.pause_button.setEnabled(running and stage)
        if not running:
            self.pause_button.set_icon_name("pause", self.palette_colors)

    def on_proc_output(self, text, is_error):
        self.console_insert(text, self.palette_colors["danger"] if is_error else None)

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
        self.ask_input.setPlaceholderText("answers go here when a program asks…")
        if code == -1:
            self.console_write("■ Stopped.", self.palette_colors["muted"])
            self.set_state("", "Stopped")
        elif code == 0:
            self.set_state("done", "Done ✓")
        else:
            if not self.last_error:
                self.last_error = "\n".join(self.proc.stderr_text.strip().splitlines()[-6:])
            self.console_write(f"■ The program stopped with exit code {code}.",
                               self.palette_colors["muted"])
            self.set_state("error", "There's a problem — check the console")

    def stop_program(self):
        if self.runner and self.runner.isRunning():
            self.runner.stop()
        if self.proc.is_running():
            self.proc.stop()
        self.set_state("", "Stopped")

    def speed_changed(self, value):
        if self.runner and self.runner.isRunning():
            self.runner.set_speed(value)

    def on_ask(self, prompt):
        self.console_write("❓ " + prompt, self.palette_colors["sky"])
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
        self.console_write(message, self.palette_colors["danger"])
        if line and self.run_editor is not None:
            self.run_editor.set_error_line(line)
        self.set_state("error", f"Oops on line {line}" if line else "Oops — check the console")

    def on_done(self, ok):
        self.set_running(False)
        self.ask_input.setEnabled(False)
        editor = self.run_editor
        if editor is not None:
            QTimer.singleShot(600, lambda: editor.set_running_line(None))
        if ok:
            self.set_state("done", "Done ✓")

    # ---------- updates ----------

    def connect_updates(self):
        u = self.updates
        u.available.connect(self.update_available)
        u.progress.connect(self.update_progress)
        u.ready.connect(self.update_ready)
        u.failed.connect(self.update_failed)
        u.up_to_date.connect(self.update_none)

    def check_updates(self, manual=True):
        self._manual_check = manual
        if manual:
            self.toast("Checking for updates…")
        self.updates.check(manual=manual)

    def update_available(self, update):
        if update.kind == "manual":
            self.update_label.setText(f"Sparky {update.version} is out")
            self.update_label.show()
            if getattr(self, "_manual_check", False):
                self.toast(f"Sparky {update.version} is on sparky-code.web.app")
            return
        self.update_label.setText(f"Downloading {update.version}…")
        self.update_label.show()

    def update_progress(self, done, total):
        if total:
            self.update_label.setText(f"Downloading update… {done * 100 // total}%")

    def update_ready(self, update):
        self.update_label.setText(f"{update.version} ready — restart")
        self.update_label.show()
        self.update_bar.ready(update.version)

    def update_failed(self, message, manual):
        if manual:
            self.toast(message, 5000)
        self.update_label.hide() if not self.updates.staged else None

    def update_none(self, version):
        if getattr(self, "_manual_check", False):
            self.toast(f"You have the newest Sparky ({version}) ✓")
        self._manual_check = False

    def restart_to_update(self):
        for editor in self.editors():
            if not self.confirm_discard(editor):
                return
        self.save_settings()
        self.updates.restart(QApplication.instance())

    # ---------- first start, tour, what's new ----------

    def after_start(self):
        try:
            import sparky_boot
            QTimer.singleShot(3000, sparky_boot.mark_good)
            if sparky_boot.notice:
                QMessageBox.information(self, "Sparky went back a version", sparky_boot.notice)
        except ImportError:
            pass
        just = self.settings.value("updates/just_updated", "", type=str)
        if just:
            self.settings.remove("updates/just_updated")
            if just == __version__:
                self.toast(f"Updated to Sparky {__version__} ✓", 4000)
                QTimer.singleShot(600, self.show_whats_new)
        if not self.settings.value("first_run_done", False, type=bool):
            dialog = FirstRunDialog(self)
            dialog.exec()
            self.settings.setValue("first_run_done", True)
            self.set_mode(dialog.mode)
            if dialog.take_tour:
                self.start_tour()
        if os.environ.get("SPARKY_SAFE_MODE") == "1":
            self.toast("Safe mode: no extensions and no updates this time.", 5000)
        else:
            self.updates.start()

    def start_tour(self):
        if self.tour is not None:
            return
        self.tour = TourOverlay(self, build_steps(self))
        self.tour.finished.connect(self.tour_finished)

    def tour_finished(self, completed):
        self.tour = None
        self.settings.setValue("tour_done", True)
        if completed:
            self.toast("Tour complete! 🎉", 3000)

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
        if self.stage_window is not None:
            self.stage_window.close()
        event.accept()


class SparkyApp(QApplication):
    """Opens files handed over by macOS (Finder, the Dock) in the window."""

    def __init__(self, argv):
        super().__init__(argv)
        self.window = None
        self.pending = []

    def event(self, event):
        if event.type() == QEvent.Type.FileOpen:
            path = Path(event.file())
            if self.window is not None:
                self.window.open_path(path)
            else:
                self.pending.append(path)
            return True
        return super().event(event)


def main():
    early = prefs.open_settings()
    scale = early.value("ui_scale", 100, type=int)
    if scale and scale != 100 and "QT_SCALE_FACTOR" not in os.environ:
        os.environ["QT_SCALE_FACTOR"] = f"{scale / 100:.2f}"
    app = SparkyApp(sys.argv)
    app.setApplicationName("Sparky")
    app.setApplicationDisplayName("Sparky")
    app.setApplicationVersion(__version__)
    from .crash import install_crash_handler
    install_crash_handler(app)
    from .single import hand_over_or_listen
    files = [Path(a) for a in sys.argv[1:] if Path(a).is_file()]
    server = hand_over_or_listen(files)
    if server is None:
        return
    load_fonts(ASSETS_DIR)
    icon_path = ASSETS_DIR / "logo_256.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    font = QFont()
    font.setFamilies(design.UI_FONTS)
    font.setPointSize(13)
    app.setFont(font)

    window = MainWindow()
    app.window = window
    server.files_received.connect(lambda paths: [window.open_path(p) for p in paths] or
                                  (window.show(), window.raise_(), window.activateWindow()))
    window.show()
    for path in files + app.pending:
        window.open_path(path)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
