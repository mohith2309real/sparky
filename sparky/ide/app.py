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
import hashlib
import os
import re
import sys
import tempfile
import time
from pathlib import Path

from PyQt6.QtCore import QEvent, Qt, QSettings, QTimer, QUrl
from PyQt6.QtGui import (QAction, QActionGroup, QColor, QDesktopServices, QFont,
                         QGuiApplication, QIcon, QKeySequence, QShortcut, QTextCharFormat,
                         QTextCursor)
from PyQt6.QtWidgets import (QApplication, QComboBox, QFileDialog, QHBoxLayout, QInputDialog,
                             QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QPlainTextEdit,
                             QSlider, QSplitter, QStackedWidget, QTabWidget, QVBoxLayout, QWidget)

from .. import __version__
from . import code_tools, design, icons, languages, mascot, prefs, vscode, whats_new
from .ai import AIPanel
from .code_panels import FindInFilesDialog, OutlinePanel
from .debug_panel import ConsoleView, DebugPanel
from . import docs
from .arduino_panel import ArduinoPanel, SerialCard
from .blocks import BlockPalette
from .dialogs import (AboutDialog, CommunityDialog, FirstRunDialog, WhatsNewDialog,
                      open_site)
from .editor import CodeEditor
from .export import make_app
from .extension_manager import ExtensionManager
from .home import HomePage
from .learn import LearnDialog
from .learning import Progress
from .projects import ProjectStore
from .project_ui import AssetsPanel, NewProjectDialog, VersionHistoryDialog, share_image
from .panels import CommandPalette, ExtensionsPanel, FilesPanel, FindBar
from .process_runner import ProcessRunner
from .runner import RunnerThread
from .settings_dialog import SettingsDialog
from .sounds import SoundBank
from .stage import StageModel, StageView, StageWindow
from .stage_tools import ChoiceBar, CostumePicker, GifRecorder, Speaker, SpritesPanel
from .theme import DARK, LIGHT, build_qss, load_fonts
from .tour import TourOverlay, build_steps
from .widgets import (Badge, Card, IconButton, Pill, SpeedControl, Toasts, UpdateBar, REDUCE_MOTION, fade_in,
                      retint, text_button)
from ..lang import SparkyError
from ..lang.to_python import to_python
from ..arduino.translate import is_arduino_program
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
           ("outline", "outline", "Outline: jump to your commands"),
           ("debug", "bug", "Debug: variables, breakpoints, run history"),
           ("extensions", "extensions", "Extensions"), ("ai", "ai", "AI helper"),
           ("arduino", "chip", "Arduino: boards, upload, Serial Monitor"),
           ("assets", "files", "Project images and sounds")]

NEW_SKETCH = """void setup() {
  // put your setup code here, to run once:

}

void loop() {
  // put your main code here, to run repeatedly:

}
"""
PRO_ONLY = {"files", "extensions", "outline"}
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
        from .i18n import translator
        self.translator = translator()
        self.translator.set_language(self.settings.value('app_language','en',type=str))
        self.code_font = self.settings.value('code_font', '', type=str)
        self.project_store = ProjectStore()
        from .classroom import TimeTracker
        self.time_tracker = TimeTracker(self.project_store.root / '.activity.json')
        self.last_activity = self.last_time_tick = time.monotonic()
        self.assignment_dialog = None
        self.current_assignment = None
        self.learning_progress = Progress()
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
        from .classroom import blocked
        if os.environ.get("SPARKY_SAFE_MODE") != "1" and not blocked(self.settings,'extensions'):
            self.extension_manager.discover()
        self.proc = ProcessRunner(self)
        self.proc.output.connect(self.on_proc_output)
        self.proc.finished.connect(self.on_proc_done)
        self.proc.error_line.connect(self.on_proc_error_line)
        self.updates = UpdateService(self, self.settings)

        self.stage_model = StageModel()
        self.speaker = Speaker()
        self.turbo_saved = None
        self.live_mode = False
        self.live_timer = QTimer(self)
        self.live_timer.setSingleShot(True)
        self.live_timer.setInterval(800)
        self.live_timer.timeout.connect(self.live_run)
        self.trail_timer = QTimer(self)
        self.trail_timer.timeout.connect(self.fade_trail)
        self.replay_frames = []
        self.replay_timer = QTimer(self)
        self.replay_timer.timeout.connect(self.record_frame)
        self.run_started = 0.0
        self.last_stats = None
        self.build_ui()
        self.build_menus()
        self.toasts = Toasts(self)
        self.load_settings()
        self.restore_session()
        self.set_theme(self.theme_key)
        self.set_mode(self.mode)
        self.set_state("", "Ready")
        self.translator.apply(self)
        self.connect_updates()

        self.recovery_timer = QTimer(self)
        self.recovery_timer.setSingleShot(True)
        self.recovery_timer.setInterval(1000)
        self.recovery_timer.timeout.connect(self.save_drafts)
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(5000)
        self.autosave_timer.timeout.connect(self.autosave)
        self.autosave_timer.start()
        self.activity_timer = QTimer(self)
        self.activity_timer.setInterval(1000)
        self.activity_timer.timeout.connect(self.time_tick)
        self.activity_timer.start()
        QApplication.instance().installEventFilter(self)

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
        self.activity_bar = bar
        bar.setObjectName("ActivityBar")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(bar)
        layout.setContentsMargins(7, 8, 7, 8)
        layout.setSpacing(4)
        self.activity_buttons = {}
        self.activity_badges = {}

        def add(key, icon_name, tip, slot, checkable=True):
            b = IconButton(icon_name, tip, size=21, checkable=checkable)
            b.setObjectName("ActivityButton")
            b.clicked.connect(slot)
            layout.addWidget(b)
            self.activity_buttons[key] = b
            self.activity_badges[key] = Badge(b)
            return b

        add("home", "home", "Home", self.show_home)
        for key, icon_name, tip in SIDEBAR:
            add(key, icon_name, tip, lambda _=False, k=key: self.show_sidebar_named(k, toggle=True))
        layout.addStretch(1)
        add("learn", "learn", "Learn: lessons and challenges", self.show_learn, checkable=False)
        add("settings", "settings", "Settings", lambda: self.open_settings(), checkable=False)
        return bar

    def build_workspace(self):
        from .lazy_panel import LazyPanel
        self.blocks = BlockPalette(
            self.palette_colors, self.insert_block,
            extra_categories=self.extension_manager.api.block_categories)
        self.files_panel = LazyPanel(FilesPanel,self)
        self.ai_panel = LazyPanel(AIPanel,self)
        self.extensions_panel = LazyPanel(ExtensionsPanel,self)
        self.arduino_panel = LazyPanel(ArduinoPanel,self)
        self.arduino_panel.message.connect(lambda text: self.toast(text, 3000))
        self.outline_panel = LazyPanel(OutlinePanel,self)
        self.debug_panel = LazyPanel(DebugPanel,self)
        self.assets_panel = LazyPanel(AssetsPanel,self)
        self.sidebar = QStackedWidget()
        self.sidebar.setObjectName("SidePanel")
        self.sidebar.setMinimumWidth(230)
        for widget in (self.blocks, self.files_panel, self.outline_panel, self.debug_panel,
                       self.extensions_panel, self.ai_panel, self.arduino_panel, self.assets_panel):
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
        self.editor_split = QSplitter(Qt.Orientation.Horizontal)
        self.editor_split.setChildrenCollapsible(False)
        self.editor_split.addWidget(self.tabs)
        self.split_view = None
        center_layout.addWidget(self.editor_split, 1)

        right = QWidget()
        right.setObjectName("SidePanel")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 8, 8, 8)
        column = QSplitter(Qt.Orientation.Vertical)
        column.setObjectName("Workspace")
        column.setChildrenCollapsible(False)
        column.addWidget(self.build_stage_card())
        self.serial_card = SerialCard(self)
        column.addWidget(self.serial_card)
        column.addWidget(self.build_console_card())
        column.setSizes([520, 300, 300])
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
        self.recorder = GifRecorder(self.stage, self)
        self.recorder.tick.connect(self.recording_tick)
        self.recorder.saved.connect(lambda path: self.toast(f"Saved {Path(path).name} ✓", 3200))
        self.recorder.failed.connect(self.toast)
        self.recorder.progress.connect(
            lambda n, total: self.set_state("running", f"Saving the GIF… {n}/{total}")
            if n < total else self.set_state("done", "GIF saved ✓"))
        tools = QWidget()
        row = QHBoxLayout(tools)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(2)
        self.rec_label = QLabel("")
        self.rec_label.setObjectName("RecLabel")
        self.rec_label.hide()
        row.addWidget(self.rec_label)
        self.grid_button = IconButton("grid", "Show the grid and axes (G)", size=16, checkable=True)
        self.grid_button.toggled.connect(self.set_grid)
        self.arrow_button = IconButton("compass", "Show which way sprites point", size=16,
                                       checkable=True)
        self.arrow_button.toggled.connect(self.set_arrows)
        self.turbo_button = IconButton("bolt", "Turbo: draw instantly", size=16, checkable=True)
        self.turbo_button.toggled.connect(self.set_turbo)
        self.sprites_button = IconButton("list", "Sprites: where each one is", size=16,
                                         checkable=True)
        self.sprites_button.toggled.connect(self.show_sprites_panel)
        costumes = IconButton("costume", "Pick a costume", size=16)
        costumes.clicked.connect(self.pick_costume)
        snap = IconButton("camera", "Save a picture: PNG (1×, 2×, 4×) or SVG", size=16)
        snap.clicked.connect(lambda: self.snapshot_menu(snap))
        self.record_button = IconButton("record", "Record the stage as an animated GIF", size=16,
                                        checkable=True)
        self.record_button.toggled.connect(self.toggle_recording)
        copy = IconButton("copy", "Copy the stage as a picture", size=16)
        copy.clicked.connect(self.copy_stage)
        full = IconButton("fullscreen", "Fullscreen stage (F11)", size=16)
        full.clicked.connect(self.fullscreen_stage)
        clear = IconButton("eraser", "Clear the stage", size=16)
        clear.clicked.connect(self.clear_stage)
        for b in (self.grid_button, self.arrow_button, self.turbo_button, self.sprites_button,
                  costumes, snap, self.record_button, copy, full, clear):
            row.addWidget(b)
        self.stage_tools = tools
        card.add_tool(tools)
        card.body.addWidget(self.stage, 1)
        self.replay_row = QWidget()
        replay_layout = QHBoxLayout(self.replay_row)
        replay_layout.setContentsMargins(4, 4, 4, 0)
        replay_label = QLabel("Replay")
        replay_label.setObjectName("FieldLabel")
        replay_layout.addWidget(replay_label)
        self.replay_slider = QSlider(Qt.Orientation.Horizontal)
        self.replay_slider.setToolTip("Drag to watch the last run again")
        self.replay_slider.valueChanged.connect(self.replay_to)
        replay_layout.addWidget(self.replay_slider, 1)
        self.replay_time = QLabel("")
        self.replay_time.setObjectName("FileLabel")
        replay_layout.addWidget(self.replay_time)
        self.replay_row.hide()
        card.body.addWidget(self.replay_row)
        self.sprites_panel = SpritesPanel(self.stage_model)
        self.sprites_panel.hide()
        card.body.addWidget(self.sprites_panel)
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
        self.console_filter = QComboBox()
        self.console_filter.addItem("Everything", "all")
        self.console_filter.addItem("What it said", "say")
        self.console_filter.addItem("Problems", "problems")
        self.console_filter.setToolTip("Show everything, only what the program said, or only problems")
        self.console_filter.currentIndexChanged.connect(
            lambda: self.console.set_filter(self.console_filter.currentData()))
        card.add_tool(self.console_filter)
        card.add_tool(copy)
        card.add_tool(clear)
        self.fix_ai_button = text_button('Fix with AI')
        self.fix_ai_button.clicked.connect(self.fix_with_ai)
        self.fix_ai_button.hide()
        card.add_tool(self.fix_ai_button)
        self.console = ConsoleView()
        self.console.line_clicked.connect(self.console_line_clicked)
        self.console.lesson_clicked.connect(self.open_lesson)
        card.body.addWidget(self.console, 1)
        self.choice_bar = ChoiceBar()
        self.choice_bar.chosen.connect(self.send_choice)
        card.body.addWidget(self.choice_bar)
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
        self.crumbs = QLabel("")
        self.crumbs.setObjectName("FileLabel")
        self.crumbs.setToolTip("Where the cursor is: the blocks around it")
        self.status.addWidget(self.crumbs)
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
        act(file_menu, "New project…", self.new_project)
        act(file_menu, "New Arduino sketch", self.new_sketch)
        act(file_menu, "Open…", self.open_file, "Ctrl+O")
        act(file_menu, 'Open assignment…', self.open_assignment)
        act(file_menu, 'Hand in…', self.hand_in)
        act(file_menu, "Open folder…", self.open_folder_dialog, key="open_folder")
        self.recent_menu = file_menu.addMenu("Open recent")
        self.recent_menu.aboutToShow.connect(self.fill_recent_menu)
        file_menu.addSeparator()
        act(file_menu, "Save", self.save_file, "Ctrl+S")
        act(file_menu, "Save as…", self.save_as, "Ctrl+Shift+S")
        act(file_menu, "Saved versions…", self.show_versions)
        act(file_menu, "Export project bundle…", self.export_project_bundle)
        act(file_menu, "Save share card…", self.save_share_card)
        file_menu.addSeparator()
        act(file_menu, "Export as colored HTML…", self.export_html)
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
        edit.addSeparator()
        act(edit, "Rename everywhere…", self.rename_symbol, "F2")
        act(edit, "Format (fix indentation)", self.format_document, "Shift+Alt+F")
        act(edit, "Go to definition", lambda: self.editor and self.editor.go_to_definition(
            self.editor.current_word()), "F12")
        act(edit, "Select next match", lambda: self.editor.select_next_match())
        act(edit, "Duplicate line", lambda: self.editor.duplicate_line())
        act(edit, "Move line up", lambda: self.editor.move_lines(-1))
        act(edit, "Move line down", lambda: self.editor.move_lines(1))
        edit.addSeparator()
        act(edit, "Fold all", lambda: self.fold_all(True))
        act(edit, "Unfold all", lambda: self.fold_all(False))
        act(edit, "Toggle bookmark", self.toggle_bookmark, "Ctrl+Alt+K")
        act(edit, "Next bookmark", lambda: self.next_bookmark(1), "Ctrl+Alt+L")
        act(edit, "Previous bookmark", lambda: self.next_bookmark(-1), "Ctrl+Alt+J")
        act(edit, "Find in all files…", self.find_in_files, "Ctrl+Shift+F")

        view = bar.addMenu("&View")
        act(view, "Home", self.show_home)
        act(view, "Blocks", lambda: self.show_sidebar_named("blocks"))
        act(view, "Files", lambda: self.show_sidebar_named("files"), key="view_files")
        act(view, "Extensions", lambda: self.show_sidebar_named("extensions"), key="view_extensions")
        act(view, "AI helper", lambda: self.show_sidebar_named("ai"), key="view_ai")
        act(view, "Arduino", lambda: self.show_sidebar_named("arduino"))
        act(view, "Outline", lambda: self.show_sidebar_named("outline"), key="view_outline")
        act(view, "Debug", lambda: self.show_sidebar_named("debug"))
        view.addSeparator()
        act(view, "Split editor", self.toggle_split, "Ctrl+\\")
        act(view, "Minimap", lambda: self.toggle_view_option("minimap"))
        act(view, "Word wrap", lambda: self.toggle_view_option("word_wrap"), "Alt+Z")
        act(view, "Show spaces", lambda: self.toggle_view_option("show_spaces"))
        act(view, "Zen mode", self.toggle_zen, "Ctrl+Alt+Z")
        act(view, "Live mode (re-run as you type)", self.toggle_live)
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
        act(run, "Run selected lines", self.run_selection, "Ctrl+Shift+Return")
        act(run, "Toggle breakpoint", self.toggle_breakpoint, "F9")
        act(run, "Show as Python", self.show_as_python)
        run.addSeparator()
        act(run, "Arduino: Verify", lambda: self.arduino_panel.build(upload=False), "Ctrl+R")
        act(run, "Arduino: Upload", lambda: self.arduino_panel.build(upload=True), "Ctrl+U")
        act(run, "Arduino: Serial Monitor", lambda: self.show_serial("monitor"), "Ctrl+Shift+M")
        act(run, "Arduino: Serial Plotter", lambda: self.show_serial("plotter"), "Ctrl+Shift+L")
        act(run, "Show as Arduino", self.arduino_panel.show_as_arduino)
        run.addSeparator()
        act(run, "Save a snapshot of the stage…", self.save_snapshot)
        act(run, "Clear the stage", self.clear_stage)

        learn = bar.addMenu("&Learn")
        act(learn, "Lessons and challenges", self.show_learn)
        act(learn, "Explain this line", self.explain_line)
        act(learn, "Explain this line with AI", self.explain_ai_line)
        act(learn, "Piano and sound library…", self.show_music)
        self.examples_menu = learn.addMenu("Examples")
        example_menus = {}
        for path in sorted(EXAMPLES_DIR.rglob("*.spark")) if EXAMPLES_DIR.is_dir() else []:
            category = path.parent.name if path.parent != EXAMPLES_DIR else "Basics"
            if category not in example_menus:
                example_menus[category] = self.examples_menu.addMenu(category.title())
            act(example_menus[category], path.stem.replace("_", " ").replace("-", " ").title(),
                lambda p=path: self.open_example(p))
        act(learn, "Arduino examples…", self.arduino_panel.open_examples)
        act(learn, "Arduino pin maps", self.arduino_panel.open_pins)
        act(learn, "Take the tour", self.start_tour)

        help_menu = bar.addMenu("&Help")
        self.help_menu = help_menu
        act(help_menu, "Take the tour", self.start_tour)
        act(help_menu, "Replay a tour part…", self.replay_tour_part)
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
        from .classroom import blocked
        if key in ('ai','extensions') and blocked(self.settings,key):
            self.toast('This panel is hidden in Classroom mode.')
            return
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
        fade_in(self.sidebar)
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
        self.apply_classroom()
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
        editor.commands = self.extension_manager.api.commands
        editor.code_font = self.code_font
        editor.title = title
        editor.setPlainText(text)
        editor.disk_digest = hashlib.sha256(path.read_bytes()).hexdigest() if path and path.exists() else None
        editor.document().setModified(False)
        editor.set_font_size(self.font_size)
        editor.set_accessibility(self.settings.value('readable',False,type=bool),
                                 self.settings.value('thick_cursor',False,type=bool),
                                 self.settings.value('color_blind',False,type=bool))
        editor.completions_enabled = self.completions_enabled
        editor.snippets = self.snippets(editor.language.id)
        editor.document().modificationChanged.connect(
            lambda _=False, e=editor: self.update_tab_title(e))
        editor.cursorPositionChanged.connect(self.update_cursor_label)
        editor.cursorPositionChanged.connect(self.update_breadcrumbs)
        editor.textChanged.connect(self.live_timer.start)
        editor.textChanged.connect(self.schedule_drafts)
        editor.scrubbed.connect(lambda: self.live_run(force=True))
        editor.breakpoints_changed.connect(self.breakpoints_changed)
        editor.problem_changed.connect(self.problem_changed)
        editor.set_minimap(self.settings.value("minimap", False, type=bool))
        editor.set_word_wrap(self.settings.value("word_wrap", False, type=bool))
        editor.set_show_spaces(self.settings.value("show_spaces", False, type=bool))
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
        if hasattr(self, 'ai_panel'):
            self.ai_panel.switch_project()
        if hasattr(self, 'assets_panel') and self.assets_panel.isVisible():
            self.assets_panel.refresh()
        lang = editor.language
        self.lang_label.setText(lang.name)
        board = lang.runner == "arduino" or (lang.runner == "stage" and
                                             is_arduino_program(editor.toPlainText()))
        stage_lang = lang.runner == "stage" and not board
        self.stage_card.setVisible(stage_lang)
        self.run_label = "Upload" if board else "Run"
        self.blocks.set_language(lang.id)
        self.outline_panel.watch(editor)
        self.update_breadcrumbs()
        from .i18n import translate
        self.run_button.setText(translate(self.run_label,self.translator.language))
        self.arduino_panel.restore_board()
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

    def new_sketch(self):
        self.untitled += 1
        editor = self.new_tab(NEW_SKETCH, None, languages.BY_ID["arduino"],
                              f"sketch_{self.untitled}.ino")
        self.show_sidebar_named("arduino")
        return editor

    def show_serial(self, which="monitor"):
        self.show_workspace()
        self.serial_card.show_tab(which)

    def open_file(self):
        start = str(self.files_panel.folder or USER_DIR)
        paths, _ = QFileDialog.getOpenFileNames(self, "Open files", start,
                                                languages.open_dialog_filter() + ";;Sparky projects (*.sparky)")
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
        if path.suffix.lower()=='.sparkytask':
            from .classroom import read_task
            from .assignment_ui import AssignmentDialog
            try:
                task=read_task(path)
                if self.assignment_dialog and not self.assignment_dialog.close(): return
                self.current_assignment=task
                self.assignment_dialog=AssignmentDialog(self,task)
                self.assignment_dialog.show()
            except (OSError,ValueError) as error:
                self.toast('Could not open assignment: '+str(error))
            return
        if path.suffix.lower() == ".sparky":
            try:
                return self.open_project(self.project_store.import_bundle(path))
            except (OSError, ValueError) as error:
                QMessageBox.warning(self, "Couldn't open project", str(error))
                return None
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
            self.project_store.save(editor.path, editor.toPlainText())
            editor.disk_digest = hashlib.sha256(editor.path.read_bytes()).hexdigest()
        except (OSError, ValueError, UnicodeError) as err:
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

    def show_music(self):
        from .music_panel import MusicDialog
        if not hasattr(self, 'music_dialog'):
            self.music_dialog = MusicDialog(self)
        self.music_dialog.show()
        self.music_dialog.raise_()

    def next_lesson_title(self):
        return "Continue: " + self.learning_progress.next_lesson()["title"]

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
        from .classroom import verify_pin
        if self.settings.value('classroom/enabled',False,type=bool):
            pin,ok=QInputDialog.getText(self,'Classroom settings','Teacher PIN:',QLineEdit.EchoMode.Password)
            if not ok: return
            if not verify_pin(self.settings,pin):
                self.toast('That PIN did not unlock Settings.'); return
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
            ("Stage: save the drawing as SVG", "", self.save_svg),
            ("Stage: record as an animated GIF", "", lambda: self.record_button.toggle()),
            ("Stage: show which way sprites point", "",
             lambda: self.set_arrows(not self.stage.show_arrows)),
            ("Stage: sprites list", "", lambda: self.sprites_button.toggle()),
            ("Stage: turbo (draw instantly)", "", lambda: self.turbo_button.toggle()),
            ("Pick a costume…", "", self.pick_costume),
            ("New Arduino sketch", "", self.new_sketch),
            ("Rename everywhere", "F2", self.rename_symbol),
            ("Format document (fix indentation)", "Shift+Alt+F", self.format_document),
            ("Go to definition", "F12", lambda: self.editor and self.editor.go_to_definition(
                self.editor.current_word())),
            ("Find in all files", "Ctrl/Cmd+Shift+F", self.find_in_files),
            ("Split editor", "Ctrl/Cmd+\\", self.toggle_split),
            ("Toggle minimap", "", lambda: self.toggle_view_option("minimap")),
            ("Toggle word wrap", "Alt+Z", lambda: self.toggle_view_option("word_wrap")),
            ("Toggle show spaces", "", lambda: self.toggle_view_option("show_spaces")),
            ("Zen mode", "Ctrl/Cmd+Alt+Z", self.toggle_zen),
            ("Live mode: re-run as you type", "", self.toggle_live),
            ("Fold all", "", lambda: self.fold_all(True)),
            ("Unfold all", "", lambda: self.fold_all(False)),
            ("Toggle bookmark", "Ctrl/Cmd+Alt+K", self.toggle_bookmark),
            ("Next bookmark", "Ctrl/Cmd+Alt+L", lambda: self.next_bookmark(1)),
            ("Toggle breakpoint", "F9", self.toggle_breakpoint),
            ("Run selected lines", "Ctrl/Cmd+Shift+Enter", self.run_selection),
            ("Debug: variables and breakpoints", "", lambda: self.show_sidebar_named("debug")),
            ("Outline", "", lambda: self.show_sidebar_named("outline")),
            ("Export as colored HTML", "", self.export_html),
            ("Arduino: verify (compile)", "Ctrl/Cmd+R", lambda: self.arduino_panel.build(upload=False)),
            ("Arduino: upload to the board", "Ctrl/Cmd+U", lambda: self.arduino_panel.build(upload=True)),
            ("Arduino: Serial Monitor", "Ctrl/Cmd+Shift+M", lambda: self.show_serial("monitor")),
            ("Arduino: Serial Plotter", "Ctrl/Cmd+Shift+L", lambda: self.show_serial("plotter")),
            ("Arduino: libraries…", "", self.arduino_panel.open_libraries),
            ("Arduino: board packages…", "", self.arduino_panel.open_boards),
            ("Arduino: examples…", "", self.arduino_panel.open_examples),
            ("Arduino: pin maps", "", self.arduino_panel.open_pins),
            ("Arduino: pick board and port", "", lambda: self.show_sidebar_named("arduino")),
            ("Show as Arduino", "", self.arduino_panel.show_as_arduino),
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

    def update_breadcrumbs(self):
        editor = self.editor
        if editor is None or editor.language.id != "sparky":
            self.crumbs.setText("")
            return
        trail = code_tools.breadcrumbs(editor.lines(), editor.textCursor().blockNumber() + 1)
        self.crumbs.setText("  ›  ".join(trail))

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

    def set_arrows(self, on):
        self.stage.set_arrows(bool(on))
        if self.arrow_button.isChecked() != bool(on):
            self.arrow_button.blockSignals(True)
            self.arrow_button.setChecked(bool(on))
            self.arrow_button.blockSignals(False)
        self.settings.setValue("stage_arrows", bool(on))

    def set_turbo(self, on):
        if on:
            self.turbo_saved = self.speed.value()
            self.speed.setValue(10)
            self.toast("Turbo on: drawings appear instantly ⚡")
        elif self.turbo_saved is not None:
            self.speed.setValue(self.turbo_saved)
            self.turbo_saved = None

    def show_sprites_panel(self, on):
        self.sprites_panel.setVisible(bool(on))

    def pick_costume(self):
        picker = CostumePicker(self)
        picker.picked.connect(self.insert_costume)
        picker.exec()

    def insert_costume(self, name):
        editor = self.editor
        if editor is None or editor.language.runner != "stage":
            QGuiApplication.clipboard().setText(f'costume "{name}"')
            self.toast(f'Copied costume "{name}"')
            return
        cursor = editor.textCursor()
        if cursor.positionInBlock() > 0:
            cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
            cursor.insertText("\n")
        cursor.insertText(f'costume "{name}"')
        editor.setTextCursor(cursor)
        editor.setFocus()
        self.toast(f'Added costume "{name}" — press Run')

    def snapshot_menu(self, anchor):
        menu = QMenu(self)
        for scale in (1, 2, 4):
            menu.addAction(f"PNG picture, {scale}× ({480 * scale}×{360 * scale})",
                           lambda s=scale: self.save_snapshot(s))
        menu.addSeparator()
        menu.addAction("SVG drawing (sharp at any size)", self.save_svg)
        menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))

    def save_svg(self):
        folder = USER_DIR / "Snapshots"
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H.%M.%S")
        path, _ = QFileDialog.getSaveFileName(self, "Save the drawing as SVG",
                                              str(folder / f"Drawing {stamp}.svg"),
                                              "SVG drawings (*.svg)")
        if not path:
            return
        if not path.lower().endswith(".svg"):
            path += ".svg"
        try:
            self.stage.save_svg(path)
            self.toast(f"Saved {Path(path).name} ✓")
        except Exception as err:
            self.toast(f"Couldn't save the SVG: {err}")

    def toggle_recording(self, on):
        if on:
            if self.recorder.encoding:
                self.record_button.blockSignals(True)
                self.record_button.setChecked(False)
                self.record_button.blockSignals(False)
                self.toast("Still saving the last GIF — one moment.")
                return
            self.recorder.start()
            self.rec_label.show()
            self.toast("Recording the stage… press ● again to stop")
            return
        self.recorder.stop()
        self.rec_label.hide()
        folder = USER_DIR / "Snapshots"
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H.%M.%S")
        path, _ = QFileDialog.getSaveFileName(self, "Save the recording",
                                              str(folder / f"Stage {stamp}.gif"),
                                              "Animated GIF (*.gif)")
        if not path:
            self.recorder.writer = None
            self.toast("Recording thrown away.")
            return
        if not path.lower().endswith(".gif"):
            path += ".gif"
        self.recorder.save(path)
        self.toast("Saving the GIF…")

    def recording_tick(self, seconds):
        self.rec_label.setText(f"● {int(seconds) // 60}:{int(seconds) % 60:02d}")
        if not self.recorder.recording() and self.record_button.isChecked():
            self.record_button.setChecked(False)

    def celebrate(self):
        self.stage.set_mood("wow")
        self.stage.celebrate(REDUCE_MOTION["on"])

    def stage_mouse(self, point):
        if point is None:
            self.coords_label.setText("")
        else:
            self.coords_label.setText(f"x {point[0]:.0f}, y {point[1]:.0f}")

    def stage_click(self, x, y):
        if not self.is_running():
            QGuiApplication.clipboard().setText(f"{x:.0f} {y:.0f}")
            self.toast(f"Copied {x:.0f} {y:.0f} — paste it after goto")

    def save_snapshot(self, scale=2):
        folder = USER_DIR / "Snapshots"
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H.%M.%S")
        path, _ = QFileDialog.getSaveFileName(self, "Save a snapshot", str(folder / f"Stage {stamp}.png"),
                                              "PNG images (*.png)")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        if self.stage.render_image(scale=scale).save(path):
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
        self.stage_window = StageWindow(self.stage_model, self.palette_colors,
                                        self.stage.stage_color)
        self.stage_window.showFullScreen()

    def clear_stage(self):
        if self.is_running():
            self.toast("Stop the program first, then clear the stage.")
            return
        self.stage_model.reset()

    # ---------- learning and projects ----------

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.KeyPress,QEvent.Type.MouseButtonPress,QEvent.Type.Wheel):
            if isinstance(obj,QWidget) and (obj is self or self.isAncestorOf(obj)):
                self.last_activity=time.monotonic()
        return super().eventFilter(obj,event)

    def time_tick(self):
        now=time.monotonic(); elapsed=now-self.last_time_tick; self.last_time_tick=now
        active=self.isActiveWindow() and self.center_stack.currentIndex()==1 and now-self.last_activity<300
        if not self.settings.value('time_tracking',True,type=bool): active=False
        if self.time_tracker.advance(elapsed,active,self.settings.value('break_reminders',False,type=bool),
                                     self.settings.value('break_minutes',20,type=int)):
            self.toast('A little break? Stretch, rest your eyes, then come back when you’re ready.',8000)
        if int(self.time_tracker.seconds)%30==0:
            try: self.time_tracker.save()
            except OSError: pass

    def apply_classroom(self):
        from .classroom import blocked
        for key in ('ai','extensions'):
            hidden=blocked(self.settings,key)
            self.activity_buttons[key].setVisible(not hidden and (key not in PRO_ONLY or self.mode=='pro'))
            action=self.menu_actions.get('view_'+key)
            if action: action.setVisible(not hidden and self.mode=='pro')
            if hidden and self.sidebar.currentIndex()==[k for k,_,_ in SIDEBAR].index(key): self.sidebar.hide()
        if blocked(self.settings,'ai') and self.ai_panel.worker and self.ai_panel.worker.isRunning():
            self.ai_panel.worker.cancel()
        hidden = blocked(self.settings,'extensions') or os.environ.get('SPARKY_SAFE_MODE')=='1'
        previous = getattr(self,'classroom_extensions_hidden',False)
        self.classroom_extensions_hidden = hidden
        if hidden:
            from .extension_manager import ExtensionAPI
            self.extension_manager.api=ExtensionAPI()
        elif previous:
            self.extension_manager.discover()
        self.blocks.reload_categories(self.extension_manager.api.block_categories)
        self.refresh_extension_commands()

    def open_assignment(self):
        path,_=QFileDialog.getOpenFileName(self,'Open assignment',str(EXAMPLES_DIR/'Assignments'),'Sparky assignments (*.sparkytask)')
        if path: self.open_path(Path(path))

    def hand_in(self):
        from .classroom import export_handin
        name,ok=QInputDialog.getText(self,'Hand in','Your name:')
        if not ok or not name.strip(): return
        path,_=QFileDialog.getSaveFileName(self,'Save hand-in','My Sparky work.zip','Hand-ins (*.zip)')
        if path:
            try:
                export_handin(path,self.editor.toPlainText(),name,self.current_assignment,
                              self.project_store.project_for(self.editor.path),self.time_tracker.seconds)
                self.toast('Hand-in saved with your name, program and project assets.')
            except (OSError,ValueError) as error:
                self.toast('Could not save hand-in: '+str(error))

    def explain_line(self):
        editor = self.editor
        line = editor.textCursor().block().text().strip()
        word = line.split(' ', 1)[0].lower() if line else ''
        info = docs.lookup(word)
        text = info[0] + '\n\nExample:\n' + info[1] if info else (
            'This is a comment: it helps people understand the program.' if line.startswith('#') else
            'Choose a Sparky command line, then use Explain this line.')
        QMessageBox.information(self, 'Explain this line', text)

    def explain_ai_line(self):
        line = self.editor.textCursor().block().text()
        self.show_sidebar_named('ai')
        self.ai_panel.ask('Explain this line in simple words and give one small hint: '+line)

    def refresh_ai_actions(self):
        from .ai import PROVIDERS, provider_config
        cfg = provider_config(self.settings)
        needs_key = PROVIDERS.get(cfg['name'], ('', '', '', True))[3]
        ready = bool(cfg['model']) and (bool(cfg['key']) or not needs_key)
        from .classroom import blocked
        self.fix_ai_button.setVisible(bool(self.last_error) and ready and not blocked(self.settings,'ai') and not self.settings.value('offline', False, type=bool))

    def fix_with_ai(self):
        self.show_sidebar_named('ai')
        self.ai_panel.ask('Help me understand the last error and give one hint for fixing it.')

    def replay_tour_part(self):
        parts = {
            'Start and write code': ['home','new','type','run','console'],
            'Draw and use the stage': ['new','draw','stage','tools','speed'],
            'Step and debug': ['new','type','step','debug'],
            'Blocks and Arduino': ['blocks','arduino'],
            'Learn, AI and settings': ['ai','learn','commands','theme','settings'],
        }
        label, ok = QInputDialog.getItem(self, 'Replay a tour part', 'Which part?', list(parts), 0, False)
        if ok:
            self.start_tour(parts[label])

    def new_project(self):
        dialog = NewProjectDialog(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        try:
            folder = self.project_store.create(dialog.name.text(), dialog.template.currentText())
            self.open_project(folder)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, 'Could not create project', str(error))

    def open_project(self, folder):
        self.files_panel.set_folder(Path(folder))
        editor = self.open_path(Path(folder) / 'main.spark')
        self.assets_panel.refresh()
        return editor

    def project_action(self, folder, action):
        folder = Path(folder)
        if action in ('rename', 'trash') and self.is_running():
            self.toast('Stop the running program before moving a project.')
            return
        try:
            if action == 'duplicate':
                target = self.project_store.duplicate(folder)
                self.open_project(target)
            elif action == 'rename':
                name, ok = QInputDialog.getText(self, 'Rename project', 'New name:', text=folder.name)
                if not ok:
                    return
                target = self.project_store.rename(folder, name)
                self.ai_panel.save_chat()
                self.ai_panel.chat_store.rename_project(folder, target)
                if self.ai_panel.chat_project == folder:
                    self.ai_panel.ensure().chat_project = target
                for editor in self.editors():
                    if editor.path and editor.path.is_relative_to(folder):
                        editor.path = target / editor.path.relative_to(folder)
                        self.update_tab_title(editor)
                self.files_panel.set_folder(target)
            elif action == 'trash':
                from PyQt6.QtCore import QFile
                self.project_store.managed_folder(folder)
                tabs = [e for e in self.editors() if e.path and e.path.is_relative_to(folder)]
                if any(not self.confirm_discard(e) for e in tabs):
                    return
                result = QFile.moveToTrash(str(folder))
                success = result[0] if isinstance(result, tuple) else result
                if not success:
                    raise OSError('The system could not move this project to Trash. It has been kept.')
                for editor in tabs:
                    self.tabs.removeTab(self.tabs.indexOf(editor))
                    editor.deleteLater()
                if not self.tabs.count():
                    self.new_file()
            self.save_drafts()
            self.home_page.refresh()
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, 'Could not change project', str(error))

    def export_project_bundle(self):
        folder = self.project_store.project_for(self.editor.path)
        if folder is None:
            self.toast('Create or open a project first.')
            return
        # Include current unsaved edits before exporting the bundle.
        for editor in self.editors():
            if editor.path and editor.path.is_relative_to(folder) and editor.document().isModified():
                if not self.save_file(editor):
                    return
        path, _ = QFileDialog.getSaveFileName(self, 'Export project bundle', folder.name+'.sparky',
                                              'Sparky projects (*.sparky)')
        if path:
            try:
                self.project_store.bundle(folder, Path(path))
                self.toast('Project bundled with its images and sounds.')
            except (OSError, ValueError) as error:
                QMessageBox.warning(self, 'Could not export project', str(error))

    def show_versions(self):
        if self.editor.path is None:
            self.toast('Save this file first to start its version history.')
            return
        VersionHistoryDialog(self, self.editor).exec()

    def save_share_card(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Save share card', 'My Sparky creation.png', 'Pictures (*.png)')
        if path:
            if share_image(self).save(path):
                self.toast('Share card saved with your drawing and code.')
            else:
                self.toast('Could not save the share card there.')

    def schedule_drafts(self):
        if hasattr(self, 'recovery_timer'):
            self.recovery_timer.start()

    def save_drafts(self, clean=False):
        tabs = []
        for editor in self.editors():
            if clean and (editor.path is None or editor.document().isModified()):
                continue
            tabs.append({'path': str(editor.path) if editor.path else None,
                         'title': editor.display_name(), 'language': editor.language.id,
                         'text': editor.toPlainText(), 'modified': editor.document().isModified(),
                         'disk_digest': getattr(editor, 'disk_digest', None)})
        try:
            self.project_store.save_recovery(tabs, self.tabs.currentIndex(), clean)
        except OSError:
            self.status.showMessage('Could not save recovery drafts. Try Save as to a writable folder.', 5000)

    def autosave(self):
        self.save_drafts()
        if not self.settings.value('autosave', True, type=bool):
            return
        for editor in self.editors():
            if editor.path is None or not editor.document().isModified():
                continue
            try:
                digest = hashlib.sha256(editor.path.read_bytes()).hexdigest() if editor.path.exists() else None
                if digest != getattr(editor, 'disk_digest', None):
                    self.status.showMessage('This file changed outside Sparky. Your draft is safe; use Save as to keep both.', 6000)
                    continue
                self.project_store.save(editor.path, editor.toPlainText())
                editor.disk_digest = hashlib.sha256(editor.path.read_bytes()).hexdigest()
                editor.document().setModified(False)
                self.update_tab_title(editor)
            except (OSError, ValueError, UnicodeError):
                self.status.showMessage('Autosave could not save this file. Your recovery draft is kept.', 6000)

    # ---------- settings & session ----------

    def apply_stage_color(self):
        color = self.settings.value("stage_color", "", type=str)
        self.stage.stage_color = color or None
        if self.stage_window is not None:
            self.stage_window.view.stage_color = color or None
        self.stage.update()

    def load_settings(self):
        s = self.settings
        self.code_font = s.value('code_font', '', type=str)
        self.set_mascot_color(s.value('mascot_color', '#e0805f', type=str))
        key = s.value("theme", "", type=str)
        if not key:
            key = "midnight" if s.value("dark", False, type=bool) else "daylight"
        self.theme_key = design.OLD_NAMES.get(key, key)
        self.speed.setValue(s.value("speed", 5, type=int))
        self.font_size = s.value("font_size", 15, type=int)
        self.completions_enabled = s.value("autocomplete", True, type=bool)
        self.sound_bank.enabled = s.value("sounds", True, type=bool)
        self.sound_bank.volume = s.value("volume", 80, type=int) / 100
        self.sound_bank.events = {kind: s.value('sound_events/'+kind, True, type=bool) for kind in ('run', 'done', 'error')}
        self.set_reduce_motion(s.value("reduce_motion", False, type=bool))
        self.set_grid(s.value("stage_grid", False, type=bool))
        self.set_arrows(s.value("stage_arrows", False, type=bool))
        self.live_mode = s.value("live_mode", False, type=bool)
        self.apply_stage_color()
        self.apply_accessibility()
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
        for kind, enabled in self.sound_bank.events.items():
            s.setValue('sound_events/'+kind, enabled)
        s.setValue("geometry", self.saveGeometry())
        s.setValue("open_files", [str(e.path) for e in self.editors() if e.path])
        s.setValue("mode", self.mode)

    def restore_session(self):
        folder = self.settings.value("folder", "", type=str)
        if folder and Path(folder).is_dir():
            self.files_panel.set_folder(Path(folder))
        recovery = self.project_store.load_recovery()
        drafts = recovery.get("tabs", [])
        if not recovery.get("clean", True) and isinstance(drafts, list):
            for draft in drafts[:100]:
                if not isinstance(draft, dict) or not isinstance(draft.get("text"), str):
                    continue
                name = draft.get("path")
                path = Path(name) if isinstance(name, str) and Path(name).is_file() else None
                language = languages.BY_ID.get(draft.get("language", "sparky"), languages.BY_ID["sparky"])
                editor = self.new_tab(draft["text"], path, language, draft.get("title", "Recovered.spark"))
                editor.document().setModified(bool(draft.get("modified", True)) or path is None)
                editor.disk_digest = draft.get("disk_digest")
            active = recovery.get("active", 0)
            if isinstance(active, int) and 0 <= active < self.tabs.count():
                self.tabs.setCurrentIndex(active)
        else:
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
            editor.code_font = self.code_font
            editor.set_font_size(self.font_size)

    def refresh_extension_commands(self):
        for editor in self.editors():
            editor.commands = self.extension_manager.api.commands
            editor.check_code()

    def set_reduce_motion(self, on):
        REDUCE_MOTION["on"] = bool(on)

    def set_mascot_color(self, color):
        if QColor(color).isValid():
            mascot.BODY = QColor(color).name()
            if hasattr(self, 'stage'):
                self.stage.update()
            if hasattr(self, 'home'):
                self.home.refresh()

    def apply_accessibility(self):
        s = self.settings
        for editor in self.editors():
            editor.set_accessibility(s.value('readable',False,type=bool),
                                     s.value('thick_cursor',False,type=bool),
                                     s.value('color_blind',False,type=bool))
        left = s.value('left_handed',False,type=bool)
        self.split.insertWidget(1 if left else 2, self.stage_box)
        self.split.setSizes([270,530,640] if left else [270,640,530])
        self.translator.set_language(s.value('app_language','en',type=str))

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
        self.console.palette_colors=palette; self.console.gutter.update()
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

    def console_write(self, text, color=None, kind=None):
        if kind is None:
            kind = "error" if color == self.palette_colors.get("danger") else "info"
        if color is None:
            role={'say':'text','question':'sky','answer':'success','error':'danger','info':'muted'}.get(kind,'text')
            color=self.palette_colors[role]
        self.console.add(text, color, kind)

    def console_say(self, text):
        if self.settings.value('read_aloud',False,type=bool):
            self.speaker.say(text, self.sound_bank.volume)
        self.console_write(text, kind="say")

    def console_line_clicked(self, line):
        editor = self.run_editor if self.run_editor is not None and \
            self.tabs.indexOf(self.run_editor) >= 0 else self.editor
        if editor is not None:
            self.tabs.setCurrentWidget(editor)
            editor.goto_line(line)

    def open_lesson(self, title):
        self.show_learn()
        if self.learn_dialog is not None:
            self.learn_dialog.open_lesson(title)

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
        return bool(self.runner and self.runner.isRunning()) or self.proc.is_running() or \
            self.arduino_panel.busy()

    def run_program(self, step=False):
        if self.is_running():
            if self.runner and self.runner.isRunning() and self.runner._paused:
                self.runner.resume()
            return
        self.show_workspace()
        editor = self.editor
        lang = editor.language
        self.last_error = ""
        self.activity_badges['debug'].show_count('')
        self.run_count += 1
        if lang.runner == "arduino" or (lang.runner == "stage" and not step
                                        and is_arduino_program(editor.toPlainText())):
            self.arduino_panel.build(upload=True)
        elif lang.runner == "stage":
            self.run_sparky(editor, step=step)
        elif lang.runner == "browser":
            if editor.path is None and not self.save_as(editor):
                return
            self.save_file(editor)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(editor.path)))
            self.toast(f"Opened {editor.path.name} in your web browser.")
        else:
            self.run_process(editor)

    def run_sparky(self, editor, step=False, speed=None, source=None):
        self.reset_run_view()
        self.run_editor = editor
        source = editor.toPlainText() if source is None else source
        base = editor.path.parent if editor.path else USER_DIR
        self.runner = RunnerThread(source, self.stage_model,
                                   self.speed.value() if speed is None else speed, base_dir=base,
                                   commands=self.extension_manager.api.commands,
                                   breakpoints=editor.breakpoints() if not getattr(self, "running_selection", False) else ())
        self.runner.sig_say.connect(self.console_say)
        self.runner.sig_stats.connect(self.on_stats)
        self.runner.sig_hint.connect(lambda text: (self.console_write("💡 " + text, self.palette_colors["muted"]),
                                                   self.toast("Tip: add a wait inside that loop", 3500)))
        self.runner.sig_ask.connect(self.on_ask)
        self.runner.sig_choice.connect(self.on_choice)
        self.runner.sig_speak.connect(self.on_speak)
        self.runner.sig_listening.connect(
            lambda: self.set_state("running", "Listening for keys and clicks — press Stop to end"))
        self.runner.sig_sound.connect(self.sound_bank.play)
        self.runner.sig_music.connect(self.sound_bank.play_music)
        self.runner.sig_line.connect(editor.set_running_line)
        self.runner.sig_error.connect(self.on_error)
        self.runner.sig_done.connect(self.on_done)
        self.runner.sig_paused.connect(self.on_paused)
        self.runner.sig_resumed.connect(self.on_resumed)
        if step:
            self.runner.step()
        self.stage.set_mood("happy")
        editor.clear_trail()
        self.trail_timer.start(100)
        self.replay_frames = []
        self.replay_row.hide()
        self.stage.set_replay(None)
        self.replay_timer.start(66)
        self.run_started = time.monotonic()
        self.last_stats = None
        self.set_running(True, stage=True)
        self.set_state("running", "Running…")
        self.runner.start()
        self.sound_bank.event('run')
        if "when key" in source or 'key "' in source or "when clicked" in source \
                or "when stage" in source or " clicked" in source:
            self.stage.setFocus()      # keys go to the program

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
        from .i18n import translate
        self.run_button.setText(translate(getattr(self, "run_label", "Run"),self.translator.language))
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
        self.sound_bank.stop()
        self.speaker.stop()
        self.arduino_panel.stop()
        if self.runner and self.runner.isRunning():
            self.runner.stop()
        if self.proc.is_running():
            self.proc.stop()
        self.set_state("", "Stopped")

    def speed_changed(self, value):
        if self.runner and self.runner.isRunning():
            self.runner.set_speed(value)

    def on_ask(self, prompt):
        self.console_write(prompt,kind='question')
        self.ask_input.setEnabled(True)
        self.ask_input.setFocus()

    def on_choice(self, prompt, choices):
        self.console_write(prompt,kind='question')
        self.choice_bar.show_choices(choices)
        self.ask_input.setEnabled(True)
        self.ask_input.setPlaceholderText("click an answer, or type it (or its number)…")

    def send_choice(self, choice):
        if not (self.runner and self.runner.isRunning()):
            return
        self.console_write(choice,kind='answer')
        self.ask_input.clear()
        self.ask_input.setEnabled(False)
        self.ask_input.setPlaceholderText("answers go here when a program asks…")
        self.runner.answer(choice)

    def on_speak(self, text):
        volume = self.settings.value("volume", 80, type=int) / 100.0
        if not self.speaker.say(text, volume):
            self.console_write(f"🔊 {text}", self.palette_colors["muted"])
            if not getattr(self, "_speak_warned", False):
                self._speak_warned = True
                self.toast("This computer has no voice for speak, so it's shown in the console.")

    def send_answer(self):
        text = self.ask_input.text()
        if self.proc.is_running():
            self.console_insert(text + "\n", self.palette_colors["muted"])
            self.ask_input.clear()
            self.proc.write(text)
            return
        if not (self.runner and self.runner.isRunning()) or not self.ask_input.isEnabled():
            return
        self.console_write(text,kind='answer')
        self.ask_input.clear()
        self.ask_input.setEnabled(False)
        self.choice_bar.hide()
        self.ask_input.setPlaceholderText("answers go here when a program asks…")
        self.runner.answer(text)

    def on_error(self, message, line):
        self.activity_badges['debug'].show_count('!')
        self.last_error = message
        self.refresh_ai_actions()
        self.stage.set_mood("oops")
        self.choice_bar.hide()
        lesson = self.lesson_for(message)
        if lesson:
            QTimer.singleShot(0, lambda: self.console_write(
                f"📖 Learn about this: {lesson} — click here", self.palette_colors["sky"], kind="error"))
        self.console_write(message, self.palette_colors["danger"])
        if line and self.run_editor is not None:
            self.run_editor.set_error_line(line)
        self.set_state("error", f"Oops on line {line}" if line else "Oops — check the console")

    def on_done(self, ok):
        self.sound_bank.event('done' if ok else 'error')
        self.set_running(False)
        self.ask_input.setEnabled(False)
        self.choice_bar.hide()
        if ok:
            self.stage.set_mood("happy")
            try:
                self.learning_progress.record_run()
            except OSError:
                self.toast('Your program finished, but learning progress could not be saved.')
            project = self.project_store.project_for(self.run_editor.path if self.run_editor else None)
            if project is not None:
                self.stage.render_image(1).save(str(project / "thumbnail.png"))
        self.finish_run_tools(ok)
        editor = self.run_editor
        if editor is not None:
            QTimer.singleShot(600, lambda: editor.set_running_line(None))
        if ok:
            self.set_state("done", "Done ✓")

    # ---------- alpha 3: editor and debugging tools ----------

    def lesson_for(self, message):
        from .lessons_data import LESSONS
        low = message.lower()
        for words, topic in docs.ERROR_LESSONS:
            if any(w.lower() in low for w in words):
                for lesson in LESSONS:
                    if topic.lower() in lesson["title"].lower():
                        return lesson["title"]
        return None

    def on_stats(self, steps, seconds):
        self.last_stats = (steps, seconds)
        self.status.showMessage(f"Ran {steps:,} steps in {seconds:.1f} seconds.", 6000)

    def finish_run_tools(self, ok):
        self.replay_timer.stop()
        self.record_frame()
        QTimer.singleShot(1400, self.trail_timer.stop)
        if len(self.replay_frames) > 3 and not self.replay_row.isVisible():
            self.replay_slider.blockSignals(True)
            self.replay_slider.setRange(0, len(self.replay_frames) - 1)
            self.replay_slider.setValue(len(self.replay_frames) - 1)
            self.replay_slider.blockSignals(False)
            self.replay_time.setText(f"{(len(self.replay_frames) - 1) * 0.066:.1f} s")
            self.replay_row.show()
        editor = self.run_editor
        steps, seconds = self.last_stats or (0, time.monotonic() - self.run_started)
        self.debug_panel.add_run({
            "file": editor.display_name() if editor is not None else "program",
            "when": time.time(), "seconds": seconds, "steps": steps,
            "ok": ok and not self.last_error, "output": self.console.toPlainText()})
        self.debug_panel.refresh()

    def fade_trail(self):
        editor = self.run_editor
        if editor is not None and editor.trail:
            editor.refresh_highlights()

    def record_frame(self):
        if len(self.replay_frames) < 3000:
            self.replay_frames.append(self.stage_model.replay_frame())

    def replay_to(self, index):
        if not self.replay_frames:
            return
        last = index >= len(self.replay_frames) - 1
        self.stage.set_replay(None if last else self.replay_frames[index])
        self.replay_time.setText(f"{index * 0.066:.1f} s")

    def breakpoints_changed(self):
        editor = self.sender()
        if self.runner and self.runner.isRunning() and editor is self.run_editor:
            self.runner.set_breakpoints(editor.breakpoints())
        self.debug_panel.refresh_breakpoints()

    def problem_changed(self, problem):
        if problem is not None and self.sender() is self.editor:
            self.status.showMessage(problem.pretty().split("\n")[0], 5000)

    def toggle_breakpoint(self):
        if self.editor is not None:
            self.editor.toggle_breakpoint()

    def rename_symbol(self):
        editor = self.editor
        if editor is None:
            return
        old = editor.current_word()
        if not old:
            self.toast("Put the cursor on a name first.")
            return
        new, ok = QInputDialog.getText(self, "Rename", f"Rename “{old}” everywhere to:", text=old)
        if ok and new.strip() and new.strip() != old:
            count = editor.rename_symbol(old, new.strip())
            self.toast(f"Renamed {count} time{'s' if count != 1 else ''} ✓" if count
                       else f"Didn't find “{old}” in the code.")

    def format_document(self):
        if self.editor is not None:
            self.toast("Tidied up the indentation ✓" if self.editor.format_document()
                       else "The indentation already looks good.")

    def set_view_option(self, key, on):
        self.settings.setValue(key, bool(on))
        for editor in self.editors():
            {"minimap": editor.set_minimap, "word_wrap": editor.set_word_wrap,
             "show_spaces": editor.set_show_spaces}[key](bool(on))
        if self.split_view is not None:
            {"minimap": self.split_view.set_minimap, "word_wrap": self.split_view.set_word_wrap,
             "show_spaces": self.split_view.set_show_spaces}[key](bool(on))

    def toggle_view_option(self, key):
        self.set_view_option(key, not self.settings.value(key, False, type=bool))

    def toggle_split(self):
        if self.split_view is not None:
            self.split_view.setParent(None)
            self.split_view.deleteLater()
            self.split_view = None
            return
        editor = self.editor
        if editor is None:
            return
        view = CodeEditor(self.palette_colors, editor.language, editor.path,
                          document=editor.document())
        view.set_font_size(self.font_size)
        view.title = editor.title
        self.split_view = view
        self.editor_split.addWidget(view)
        self.editor_split.setSizes([1, 1])
        self.toast("Split: a second view of the same file")

    def toggle_zen(self):
        zen = not getattr(self, "zen", False)
        self.zen = zen
        for widget in (self.activity_bar, self.status, self.console_card):
            widget.setVisible(not zen)
        if zen:
            self.sidebar.hide()
            self.toast("Zen mode: just the code and the stage. Press Ctrl+Alt+Z to come back.", 3500)
        else:
            self.sidebar.show()

    def toggle_live(self):
        self.live_mode = not self.live_mode
        self.settings.setValue("live_mode", self.live_mode)
        self.toast("Live mode on: drawings re-run as you type ✨" if self.live_mode else "Live mode off")
        if self.live_mode:
            self.live_run(force=True)

    def live_run(self, force=False):
        editor = self.editor
        if not (self.live_mode or force) or editor is None or editor.language.id != "sparky":
            return
        if not self.live_mode and not force:
            return
        source = editor.toPlainText()
        if editor.problem or is_arduino_program(source):
            return
        if re.search(r"^\s*(ask|when|forever|repeat until|repeat while)\b", source, re.M | re.I):
            return            # programs that wait for you (or never end) don't re-run by themselves
        if self.runner and self.runner.isRunning():
            self.runner.stop()
            if not self.runner.wait(500):
                self.live_timer.start()
                return
        if self.proc.is_running() or self.arduino_panel.busy():
            return
        self.run_sparky(editor, speed=10)

    def run_selection(self):
        if self.is_running():
            self.toast("Stop the current program before running selected lines.")
            return
        editor = self.editor
        if editor is None or editor.language.runner != "stage":
            self.toast("Run selection works on Sparky programs.")
            return
        cursor = editor.textCursor()
        if not cursor.hasSelection():
            self.toast("Select some lines first, then Run selection.")
            return
        doc = editor.document()
        first = doc.findBlock(cursor.selectionStart())
        last = doc.findBlock(cursor.selectionEnd() - 1)
        lines = []
        block = first
        while block.isValid():
            lines.append(block.text())
            if block == last:
                break
            block = block.next()
        import textwrap
        source = "\n" * first.blockNumber() + textwrap.dedent("\n".join(lines))
        self.running_selection = True
        try:
            self.run_sparky_source(editor, source)
        finally:
            self.running_selection = False

    def run_sparky_source(self, editor, source):
        self.run_sparky(editor, source=source)
        self.toast("Running the selected lines")

    def toggle_bookmark(self):
        if self.editor is not None:
            self.editor.toggle_bookmark()

    def next_bookmark(self, step=1):
        if self.editor is not None and not self.editor.next_bookmark(step):
            self.toast("No bookmarks yet — press Ctrl+Alt+K on a line.")

    def export_html(self):
        editor = self.editor
        if editor is None:
            return
        name = (editor.path.stem if editor.path else Path(editor.display_name()).stem) + ".html"
        path, _ = QFileDialog.getSaveFileName(self, "Export as colored HTML",
                                              str(USER_DIR / name), "Web pages (*.html)")
        if not path:
            return
        Path(path).write_text(editor.export_html(), encoding="utf-8")
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        self.toast(f"Saved {Path(path).name} — print it from your browser ✓")

    def find_in_files(self):
        folder = self.files_panel.folder or (self.editor.path.parent if self.editor is not None
                                             and self.editor.path else USER_DIR)
        word = self.editor.textCursor().selectedText() if self.editor is not None else ""
        FindInFilesDialog(self, folder, word).exec()

    def fold_all(self, fold=True):
        editor = self.editor
        if editor is None:
            return
        if fold:
            for line in sorted(editor.foldable(), reverse=True):
                if line not in editor.folded:
                    editor.toggle_fold(line)
        else:
            editor.unfold_all()

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
        self.activity_badges['settings'].show_count('1')
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

    def start_tour(self, keys=None):
        if self.tour is not None:
            return
        steps = build_steps(self)
        if keys is not None:
            steps = [step for step in steps if step.key in keys or step.key == "done"]
        self.tour = TourOverlay(self, steps)
        self.tour.finished.connect(self.tour_finished)

    def tour_finished(self, completed):
        self.tour = None
        self.settings.setValue("tour_done", True)
        if completed:
            self.toast("Tour complete! 🎉", 3000)

    # ---------- closing ----------

    def closeEvent(self, event):
        news = self.home_page.feed_worker
        if news and news.isRunning():
            news.requestInterruption()
            if not news.wait(100):
                self.toast('Finishing the news request before closing…')
                event.ignore()
                return
        worker = self.ai_panel.worker
        if worker and worker.isRunning():
            worker.cancel()
            if not worker.wait(1000):
                self.toast('Stopping the AI reply before closing…')
                event.ignore()
                return
        if self.runner and self.runner.isRunning():
            self.runner.stop()
            self.runner.wait(1000)
        if self.proc.is_running():
            self.proc.stop()
        if self.assignment_dialog and not self.assignment_dialog.close():
            event.ignore(); return
        for editor in self.editors():
            if not self.confirm_discard(editor):
                event.ignore()
                return
        self.save_settings()
        self.activity_timer.stop()
        try: self.time_tracker.save()
        except OSError: pass
        if self.learn_dialog and not self.learn_dialog.close():
            event.ignore()
            return
        self.save_drafts(clean=True)
        self.recovery_timer.stop()
        self.autosave_timer.stop()
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
