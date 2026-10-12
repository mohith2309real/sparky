# Settings (Spark 3): sections in a sidebar instead of tabs.

import platform
import sys

from PyQt6.QtCore import QT_VERSION_STR, QSize, Qt, QUrl
from PyQt6.QtGui import QColor, QDesktopServices, QFont, QGuiApplication
from PyQt6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QColorDialog, QDialog, QFileDialog, QFontComboBox, QFormLayout,
                             QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                             QPlainTextEdit, QPushButton, QRadioButton, QScrollArea, QSlider, QTextBrowser,
                             QSpinBox, QStackedWidget, QVBoxLayout, QWidget)

from .. import __version__
from . import design, icons, vscode
from .widgets import text_button

SECTIONS = [("General", "settings"), ("Editor", "code"), ("Stage & sounds", "sound"),
            ("Languages", "python"), ("AI", "ai"), ("Updates", "update"),
            ("Accessibility", "keyboard"), ("Classroom", "learn"), ("Privacy", "shield"), ("About", "info")]
SCALES = [90, 100, 110, 125, 150]


def note(text):
    label = QLabel(text)
    label.setObjectName("Muted")
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setOpenExternalLinks(True)
    return label


def diagnostics(main):
    from ..paths import USER_DIR
    from ..update import where
    boot = sys.modules.get("sparky_boot")
    lines = [
        f"Sparky {__version__}" + (f" (update pack; app built with {boot.BASE_VERSION})"
                                   if boot and boot.running_pack else ""),
        f"Python {platform.python_version()} · Qt {QT_VERSION_STR} · {platform.platform()}",
        f"Build: {where.platform_id() or 'running from source'}"
        + (f" · runtime {boot.RUNTIME}" if boot else ""),
        f"Update channel: {main.updates.channel()}",
        f"Your files: {USER_DIR}",
        f"App data: {where.data_dir()}",
        f"Safe mode: {'on' if getattr(boot, 'safe_mode', False) else 'off'}",
        f"Theme: {main.palette_colors.get('name', main.theme_key)}",
    ]
    return "\n".join(lines)


class SettingsDialog(QDialog):
    def __init__(self, main_window, tab="General"):
        super().__init__(main_window)
        from . import ai, languages
        self.ai, self.languages = ai, languages
        self.main = main_window
        self.settings = main_window.settings
        self.setWindowTitle("Settings")
        self.resize(820, 600)
        self.models_worker = None

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        side = QWidget()
        side.setObjectName("SidePanel")
        side.setFixedWidth(208)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(12, 18, 12, 12)
        title = QLabel("Settings")
        title.setObjectName("Heading")
        sl.addWidget(title)
        sl.addSpacing(8)
        self.nav = QListWidget()
        self.nav.setObjectName("SettingsNav")
        self.nav.setAccessibleName('Settings sections')
        self.nav.setIconSize(QSize(18, 18))
        sl.addWidget(self.nav, 1)
        root.addWidget(side)

        right = QVBoxLayout()
        right.setContentsMargins(26, 22, 22, 16)
        self.pages = QStackedWidget()
        right.addWidget(self.pages, 1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = text_button("Cancel")
        cancel.clicked.connect(self.reject)
        done = text_button("Save", object_name="Primary")
        done.clicked.connect(self.apply_and_close)
        buttons.addWidget(cancel)
        buttons.addWidget(done)
        right.addLayout(buttons)
        root.addLayout(right, 1)

        builders = {"General": self.page_general, "Editor": self.page_editor,
                    "Stage & sounds": self.page_stage, "Languages": self.page_languages,
                    "AI": self.page_ai, "Updates": self.page_updates,
                    "Accessibility": self.page_access, "Privacy": self.page_privacy,
                    "Classroom": self.page_classroom,
                    "About": self.page_about}
        p = main_window.palette_colors
        for name, icon_name in SECTIONS:
            item = QListWidgetItem(icons.icon(icon_name, p["muted"], 18, active=p["accent"]), name)
            self.nav.addItem(item)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            page = QWidget()
            layout = QVBoxLayout(page)
            layout.setContentsMargins(0, 0, 8, 0)
            layout.setSpacing(12)
            heading = QLabel(name)
            heading.setObjectName("Heading")
            layout.addWidget(heading)
            builders[name](layout)
            layout.addStretch(1)
            scroll.setWidget(page)
            self.pages.addWidget(scroll)
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        names = [n for n, _ in SECTIONS]
        if tab == "Languages" or tab in names:
            self.nav.setCurrentRow(names.index(tab))
        else:
            self.nav.setCurrentRow(0)
        self.provider_changed(self.provider.currentText(), first=True)

    # ---------- pages ----------

    def form(self, layout):
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addLayout(form)
        return form

    def page_general(self, layout):
        m, s = self.main, self.settings
        form = self.form(layout)
        self.theme = QComboBox()
        for key, palette in design.THEMES.items():
            self.theme.addItem(palette["name"], key)
        for key, label, _dark in vscode.all_themes():
            self.theme.addItem(f"{label}  (VS Code)", key)
        current = design.OLD_NAMES.get(m.theme_key, m.theme_key)
        self.theme.setCurrentIndex(max(0, self.theme.findData(current)))
        form.addRow("Theme", self.theme)
        preview = text_button('Preview theme')
        preview.clicked.connect(self.preview_theme)
        form.addRow('', preview)
        self.mascot_color = self.settings.value('mascot_color', '#e0805f', type=str)
        mascot_button = text_button('Pick Sparky’s color')
        mascot_button.clicked.connect(self.pick_mascot_color)
        form.addRow('Sparky', mascot_button)

        mode_row = QHBoxLayout()
        self.mode_group = QButtonGroup(self)
        self.kid = QRadioButton("Kid mode — simple and friendly")
        self.pro = QRadioButton("Pro mode — every panel and tool")
        self.mode_group.addButton(self.kid)
        self.mode_group.addButton(self.pro)
        (self.kid if m.mode == "kid" else self.pro).setChecked(True)
        mode_box = QVBoxLayout()
        mode_box.addWidget(self.kid)
        mode_box.addWidget(self.pro)
        mode_row.addLayout(mode_box)
        form.addRow("Mode", mode_row)

        self.scale = QComboBox()
        for value in SCALES:
            self.scale.addItem(f"{value}%", value)
        self.scale.setCurrentIndex(max(0, self.scale.findData(s.value("ui_scale", 100, type=int))))
        form.addRow("Size of everything", self.scale)
        form.addRow("", note("The size change applies the next time Sparky starts."))
        self.start_home = QCheckBox("Start on the Home screen")
        self.start_home.setChecked(s.value("start_home", True, type=bool))
        form.addRow("", self.start_home)
        tour = text_button("Take the tour now", icon="tour")
        tour.clicked.connect(lambda: (self.accept(), m.start_tour()))
        form.addRow("Tour", tour)
        row=QHBoxLayout()
        export=text_button('Export settings'); export.clicked.connect(self.export_preferences)
        restore=text_button('Import settings'); restore.clicked.connect(self.import_preferences)
        row.addWidget(export); row.addWidget(restore); form.addRow('Preferences',row)

    def page_editor(self, layout):
        m = self.main
        form = self.form(layout)
        self.code_font = QFontComboBox()
        self.code_font.setFontFilters(QFontComboBox.FontFilter.MonospacedFonts)
        self.code_font.setCurrentFont(QFont(m.code_font or 'JetBrains Mono'))
        form.addRow('Code font', self.code_font)
        self.font_size = QSpinBox()
        self.font_size.setRange(10, 28)
        self.font_size.setValue(m.font_size)
        form.addRow("Code text size", self.font_size)
        self.autocomplete = QCheckBox("Suggest words while typing")
        self.autocomplete.setChecked(m.completions_enabled)
        form.addRow("", self.autocomplete)
        self.autosave = QCheckBox("Autosave files every five seconds (unsaved tabs have recovery drafts)")
        self.autosave.setChecked(self.settings.value("autosave", True, type=bool))
        form.addRow("", self.autosave)
        layout.addWidget(note("More editor tools (auto <b>end</b>, live error underlines, "
                              "number scrubbing…) arrive in the next 3.0 alphas."))

    def preview_theme(self):
        from .editor import CodeEditor
        from . import languages
        from .theme import LIGHT, DARK, build_qss
        key=self.theme.currentData()
        palette=vscode.theme_palette(key,LIGHT,DARK) if key.startswith('vscode:') else design.theme(key)
        if palette is None:
            self.main.toast('This theme could not be previewed.')
            return
        palette=design.complete(palette)
        dialog=QDialog(self); dialog.setWindowTitle('Theme preview'); dialog.resize(700,430)
        dialog.setStyleSheet(build_qss(palette)); layout=QVBoxLayout(dialog)
        title=QLabel(palette.get('name',self.theme.currentText())); title.setObjectName('Heading'); layout.addWidget(title)
        editor=CodeEditor(palette,languages.BY_ID['sparky']); editor.setReadOnly(True)
        editor.setPlainText('# A little code, a whole new world\nsay "Hello, Sparky!"\nrepeat 4 times\n  move 80\n  turn 90\nend\n')
        layout.addWidget(editor,1)
        close=text_button('Close'); close.clicked.connect(dialog.accept); layout.addWidget(close)
        dialog.exec()

    def pick_mascot_color(self):
        color=QColorDialog.getColor(QColor(self.mascot_color),self,'Sparky’s color')
        if color.isValid(): self.mascot_color=color.name()

    def export_preferences(self):
        from .preferences_io import export_settings
        path,_=QFileDialog.getSaveFileName(self,'Export preferences','Sparky settings.json','Settings (*.json)')
        if path:
            try:
                export_settings(self.settings,path)
                self.main.toast('Preferences exported. API keys and classroom locks are excluded.')
            except (OSError,ValueError) as error:
                self.main.toast('Could not export preferences: '+str(error))

    def import_preferences(self):
        from .preferences_io import import_settings
        path,_=QFileDialog.getOpenFileName(self,'Import preferences','','Settings (*.json)')
        if path:
            try:
                import_settings(self.settings,path)
                self.main.code_font=self.settings.value('code_font','',type=str)
                self.main.load_settings(); self.main.apply_theme(); self.main.set_font_size_all(self.main.font_size)
                self.main.home_page.refresh()
                self.main.toast('Preferences imported. Reopen Settings to see them.')
                self.reject()
            except (OSError,ValueError) as error:
                self.main.toast('Could not import preferences: '+str(error))

    def page_stage(self, layout):
        m, s = self.main, self.settings
        form = self.form(layout)
        self.speed = QSlider(Qt.Orientation.Horizontal)
        self.speed.setRange(1, 10)
        self.speed.setValue(m.speed.value())
        form.addRow("Default speed", self.speed)
        self.grid = QCheckBox("Show the grid on the stage")
        self.grid.setChecked(s.value("stage_grid", False, type=bool))
        form.addRow("", self.grid)
        self.stage_color = QComboBox()
        self.stage_color.addItem("Follow the theme", "")
        for label, value in (("Cream", "#faf9f5"), ("White", "#ffffff"), ("Sky", "#e6f3fb"),
                             ("Mint", "#e8f5ec"), ("Ink (dark)", "#1c1b19"), ("Night (dark)", "#141a40")):
            self.stage_color.addItem(label, value)
        current = s.value("stage_color", "", type=str)
        index = self.stage_color.findData(current)
        if index < 0 and current:
            self.stage_color.addItem(current, current)
            index = self.stage_color.count() - 1
        self.stage_color.setCurrentIndex(max(0, index))
        pick = QPushButton("Pick…")
        pick.setObjectName("GhostButton")
        pick.clicked.connect(self.pick_stage_color)
        row = QHBoxLayout()
        row.addWidget(self.stage_color, 1)
        row.addWidget(pick)
        form.addRow("Stage color", row)
        self.sounds = QCheckBox("Play sounds")
        self.sounds.setChecked(m.sound_bank.enabled)
        form.addRow("Sounds", self.sounds)
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(int(m.sound_bank.volume * 100))
        form.addRow("Volume", self.volume)
        self.sound_events = {}
        for kind, label in [('run', 'When a program starts'), ('done', 'When a program finishes'), ('error', 'When a program has an error')]:
            box = QCheckBox(label)
            box.setChecked(m.sound_bank.events.get(kind, True))
            self.sound_events[kind] = box
            form.addRow('', box)

    def pick_stage_color(self):
        from PyQt6.QtGui import QColor
        from PyQt6.QtWidgets import QColorDialog
        start = QColor(self.stage_color.currentData() or "#faf9f5")
        color = QColorDialog.getColor(start, self, "Stage color")
        if color.isValid():
            value = color.name()
            index = self.stage_color.findData(value)
            if index < 0:
                self.stage_color.addItem(value, value)
                index = self.stage_color.count() - 1
            self.stage_color.setCurrentIndex(index)

    def page_languages(self, layout):
        s, languages = self.settings, self.languages
        form = self.form(layout)
        self.python = QComboBox()
        self.python.setEditable(True)
        self.python.addItem("Automatic", "")
        for cmd in languages.python_candidates():
            self.python.addItem(" ".join(cmd), cmd[0] if len(cmd) == 1 else "")
        current = s.value("python_path", "", type=str)
        if current:
            self.python.setEditText(current)
        prow = QHBoxLayout()
        prow.addWidget(self.python, 1)
        check = text_button("Find")
        check.setToolTip("List the Pythons on this computer and check for turtle graphics")
        check.clicked.connect(self.check_pythons)
        prow.addWidget(check)
        form.addRow("Python", prow)
        self.python_note = note("Python programs (and Sparky programs turned into Python) run with this.")
        form.addRow("", self.python_note)
        self.node = QComboBox()
        self.node.setEditable(True)
        self.node.addItem("Automatic", "")
        for cmd in languages.node_candidates():
            self.node.addItem(cmd[0], cmd[0])
        if s.value("node_path", "", type=str):
            self.node.setEditText(s.value("node_path", "", type=str))
        form.addRow("Node.js", self.node)
        self.commands = QPlainTextEdit(s.value("run_commands", languages.DEFAULT_CUSTOM, type=str))
        self.commands.setObjectName("Field")
        self.commands.setFixedHeight(120)
        form.addRow("Run commands", self.commands)
        form.addRow("", note("One per line: .ext = command. {file} is the file to run."))

    def page_ai(self, layout):
        s, ai = self.settings, self.ai
        form = self.form(layout)
        self.provider = QComboBox()
        self.provider.addItems(list(ai.PROVIDERS))
        self.provider.setCurrentText(s.value("ai_provider", "Anthropic (Claude)", type=str))
        self.provider.currentTextChanged.connect(self.provider_changed)
        form.addRow("Provider", self.provider)
        self.base_url = QLineEdit(s.value("ai_base_url", "", type=str))
        form.addRow("Base URL", self.base_url)
        self.key = QLineEdit(s.value("ai_key", "", type=str))
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("Paste your API key")
        form.addRow("API key", self.key)
        mrow = QHBoxLayout()
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.setEditText(s.value("ai_model", "", type=str))
        mrow.addWidget(self.model, 1)
        load = text_button("Load models")
        load.clicked.connect(self.load_models)
        mrow.addWidget(load)
        form.addRow("Model", mrow)
        self.tutor = QCheckBox("Tutor mode: hints and explanations before full answers")
        self.tutor.setChecked(s.value("ai_tutor", True, type=bool))
        form.addRow("", self.tutor)
        self.instructions = QPlainTextEdit(s.value("ai_instructions", "", type=str))
        self.instructions.setObjectName("Field")
        self.instructions.setPlaceholderText("Your own instructions for the AI, like: "
                                             "Explain things like I'm 10. Use lots of emojis.")
        self.instructions.setFixedHeight(90)
        form.addRow("Instructions", self.instructions)
        self.ai_note = note("")
        form.addRow("", self.ai_note)

    def page_updates(self, layout):
        m, s = self.main, self.settings
        boot = sys.modules.get("sparky_boot")
        service = m.updates
        running = f"Sparky {__version__}"
        if boot and boot.running_pack:
            running += f" — installed as an update (the app itself is {boot.BASE_VERSION})"
        version = QLabel(running)
        version.setObjectName("SubHeading")
        layout.addWidget(version)
        last = service.last_check()
        self.update_status = note(f"Last checked: {last.replace('T', ' ')}" if last else
                                  "Sparky hasn't checked for updates yet.")
        layout.addWidget(self.update_status)
        row = QHBoxLayout()
        check = text_button("Check for updates now", icon="refresh", object_name="Primary")
        check.clicked.connect(self.check_now)
        row.addWidget(check)
        row.addStretch(1)
        layout.addLayout(row)
        form = self.form(layout)
        self.channel = QComboBox()
        self.channel.addItem("Stable — finished versions", "stable")
        self.channel.addItem("Beta — try new things first", "beta")
        self.channel.setCurrentIndex(max(0, self.channel.findData(service.channel())))
        form.addRow("Channel", self.channel)
        self.auto_check = QCheckBox("Check for updates automatically")
        self.auto_check.setChecked(service.auto_check())
        form.addRow("", self.auto_check)
        self.auto_download = QCheckBox("Download updates in the background")
        self.auto_download.setChecked(service.auto_download())
        form.addRow("", self.auto_download)
        skipped = s.value("updates/skip", "", type=str)
        if skipped:
            unskip = text_button(f"Stop skipping {skipped}")
            unskip.clicked.connect(lambda: (s.remove("updates/skip"), unskip.hide()))
            form.addRow("", unskip)
        layout.addWidget(note(
            "Every update is signed with Sparky's release key. Sparky checks the signature "
            "and every file's SHA-256 before it installs anything, and goes back to the last "
            "version that worked if an update ever fails to start. "
            "<a href='https://sparky-code.web.app/verify.html'>How signing works</a>"))
        history = service.history()
        if history:
            layout.addWidget(QLabel("History"))
            box = QListWidget()
            box.setFixedHeight(120)
            for entry in reversed(history[-10:]):
                box.addItem(f"{entry['version']}  ·  {entry['date'].replace('T', ' ')}")
            layout.addWidget(box)
        if boot and boot.running_pack:
            back = text_button(f"Go back to {boot.BASE_VERSION} (built in)")
            back.clicked.connect(self.forget_updates)
            layout.addWidget(back, 0, Qt.AlignmentFlag.AlignLeft)

    def page_access(self, layout):
        s = self.settings
        form = self.form(layout)
        self.reduce_motion = QCheckBox("Reduce motion (no sliding or fading)")
        self.reduce_motion.setChecked(s.value("reduce_motion", False, type=bool))
        form.addRow("", self.reduce_motion)
        self.access_options = {}
        self.app_language=QComboBox()
        for label,key in [('English','en'),('हिन्दी (beta)','hi'),('తెలుగు (beta)','te')]: self.app_language.addItem(label,key)
        self.app_language.setCurrentIndex(max(0,self.app_language.findData(s.value('app_language','en',type=str))))
        form.addRow('App language',self.app_language)
        form.addRow('',note('Hindi and Telugu translate the core UI in this beta. Lessons and code stay in English.'))
        for key,label in [('readable','Readable mode: more letter spacing and larger line height'),
                          ('thick_cursor','Thicker text cursor'),('color_blind','Color-blind-safe syntax colors'),
                          ('read_aloud','Read console messages aloud'),('left_handed','Left-handed layout: stage on the left')]:
            box=QCheckBox(label); box.setChecked(s.value(key,False,type=bool))
            self.access_options[key]=box; form.addRow('',box)
        contrast = text_button("Use the High Contrast theme")
        contrast.clicked.connect(lambda: self.theme.setCurrentIndex(self.theme.findData("contrast")))
        form.addRow("", contrast)
        layout.addWidget(note("Everything in Sparky works from the keyboard: Tab moves between "
                              "controls, Ctrl/Cmd+Shift+P opens every command, F1 too."))

    def page_privacy(self, layout):
        s = self.settings
        self.offline = QCheckBox("Offline mode: pause online features and downloads")
        self.offline.setChecked(s.value("offline", False, type=bool))
        layout.addWidget(self.offline)
        layout.addWidget(note(
            "Sparky connects to the internet only for: update checks (sparky-code.web.app and "
            "huggingface.co), the AI helper (only the provider you choose, only when you ask), "
            "and finding VS Code themes (open-vsx.org). It never sends your programs anywhere "
            "unless you ask the AI helper about them. There are no accounts or remote analytics. "
            "Time on task is stored only on this computer."))

    def page_classroom(self, layout):
        s=self.settings; form=self.form(layout); self.pending_pin=None
        self.classroom_enabled=QCheckBox('Classroom mode: lock Settings with a teacher PIN')
        self.classroom_enabled.setChecked(s.value('classroom/enabled',False,type=bool)); form.addRow('',self.classroom_enabled)
        self.hide_ai=QCheckBox('Hide AI'); self.hide_ai.setChecked(s.value('classroom/hide_ai',True,type=bool)); form.addRow('',self.hide_ai)
        self.hide_extensions=QCheckBox('Hide and disable extensions'); self.hide_extensions.setChecked(s.value('classroom/hide_extensions',True,type=bool)); form.addRow('',self.hide_extensions)
        pin=text_button('Set or change teacher PIN'); pin.clicked.connect(self.choose_pin); form.addRow('PIN',pin)
        self.pin_status=QLabel('A PIN is saved.' if s.value('classroom/pin_hash','',type=str) else 'Set a PIN before enabling Classroom mode.')
        form.addRow('',self.pin_status)
        self.track_time=QCheckBox('Track time on task on this computer only')
        self.track_time.setChecked(s.value('time_tracking',True,type=bool)); form.addRow('',self.track_time)
        self.break_reminders=QCheckBox('Gentle break reminders')
        self.break_reminders.setChecked(s.value('break_reminders',False,type=bool)); form.addRow('',self.break_reminders)
        self.break_minutes=QSpinBox(); self.break_minutes.setRange(5,60); self.break_minutes.setSuffix(' minutes')
        self.break_minutes.setValue(s.value('break_minutes',20,type=int)); form.addRow('Remind after',self.break_minutes)
        form.addRow('Time on task',QLabel(f'{int(self.main.time_tracker.seconds)//60} minutes on this computer'))
        guide=text_button('Teacher guide'); guide.clicked.connect(self.teacher_guide)
        form.addRow('',guide)
        layout.addWidget(note('Open .sparkytask assignments from File → Open assignment. Use Hand in to save a named ZIP with code and assets. The PIN is a local app lock, not an operating-system security boundary.'))

    def teacher_guide(self):
        from ..paths import EXAMPLES_DIR
        dialog=QDialog(self); dialog.setWindowTitle('Teacher guide'); dialog.resize(760,600)
        layout=QVBoxLayout(dialog); text=QTextBrowser()
        text.setMarkdown((EXAMPLES_DIR/'Assignments'/'TEACHER-GUIDE.md').read_text(encoding='utf-8'))
        layout.addWidget(text); close=QPushButton('Close'); close.clicked.connect(dialog.accept); layout.addWidget(close)
        dialog.exec()

    def choose_pin(self):
        from PyQt6.QtWidgets import QInputDialog
        pin,ok=QInputDialog.getText(self,'Teacher PIN','Choose 4 to 12 digits:',QLineEdit.EchoMode.Password)
        if not ok: return
        if not pin.isdigit() or not 4<=len(pin)<=12:
            self.pin_status.setText('Choose 4 to 12 digits.'); return
        self.pending_pin=pin; self.pin_status.setText('New PIN will be saved when you press Save.')

    def page_about(self, layout):
        from .dialogs import open_site
        from . import mascot
        top = QHBoxLayout()
        pic = QLabel()
        pic.setPixmap(mascot.pixmap(64, "happy"))
        top.addWidget(pic)
        words = QVBoxLayout()
        name = QLabel(f"Sparky {__version__}")
        name.setObjectName("SubHeading")
        words.addWidget(name)
        words.addWidget(note("A coding app for kids (and grown-ups), made by Mohith. "
                             "Built with Python and Qt — no browser engine."))
        top.addLayout(words, 1)
        layout.addLayout(top)
        info = QPlainTextEdit(diagnostics(self.main))
        info.setObjectName("Field")
        info.setReadOnly(True)
        info.setFixedHeight(170)
        layout.addWidget(info)
        row = QHBoxLayout()
        copy = text_button("Copy details", icon="copy")
        copy.clicked.connect(lambda: (QGuiApplication.clipboard().setText(info.toPlainText()),
                                      self.main.toast("Copied ✓")))
        row.addWidget(copy)
        logs = text_button("Open logs folder", icon="files")
        logs.clicked.connect(self.main.open_logs)
        row.addWidget(logs)
        site = text_button("Mohith's website", icon="globe")
        site.clicked.connect(open_site)
        row.addWidget(site)
        row.addStretch(1)
        layout.addLayout(row)

    # ---------- actions ----------

    def check_now(self):
        self.update_status.setText("Checking…")
        service = self.main.updates
        service.settings.setValue("updates/channel", self.channel.currentData())

        def done(text):
            try:
                self.update_status.setText(text)
            except RuntimeError:
                pass
        service.up_to_date.connect(lambda v: done(f"You have the newest version ({v}). ✓"))
        service.available.connect(lambda u: done(f"Sparky {u.version} is available — downloading…"
                                                 if u.kind != "manual" else
                                                 f"Sparky {u.version} is available on sparky-code.web.app."))
        service.failed.connect(lambda msg, _manual: done(msg))
        service.ready.connect(lambda u: done(f"Sparky {u.version} is ready — restart to use it."))
        service.check(manual=True)

    def forget_updates(self):
        from ..update import install
        install.forget_packs()
        self.main.toast("Sparky will use its built-in version after a restart.")

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
        if self.settings.value('offline', False, type=bool):
            self.ai_note.setText('Offline mode is on. Model loading is paused.')
            return
        cfg = {"name": self.provider.currentText(),
               "kind": self.ai.PROVIDERS[self.provider.currentText()][0],
               "base_url": self.base_url.text().strip() or
               self.ai.PROVIDERS[self.provider.currentText()][1],
               "key": self.key.text().strip(), "model": ""}
        self.ai_note.setText("Loading models…")
        self.models_worker = self.ai.ModelsWorker(cfg, self)
        self.models_worker.loaded.connect(self.models_loaded)
        self.models_worker.failed.connect(lambda msg: self.ai_note.setText("⚠️ " + msg))
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
        self.python_note.setText("<br>".join(rows) if rows else
                                 "No Python found. Install it from python.org.")

    def apply_and_close(self):
        w, s = self.main, self.settings
        if self.classroom_enabled.isChecked() and not self.pending_pin and not s.value('classroom/pin_hash','',type=str):
            self.pin_status.setText('Set a teacher PIN before enabling Classroom mode.')
            self.pages.setCurrentIndex([n for n,_ in SECTIONS].index('Classroom')); return
        if self.pending_pin:
            from .classroom import set_pin
            set_pin(s,self.pending_pin)
        s.setValue('classroom/enabled',self.classroom_enabled.isChecked())
        s.setValue('classroom/hide_ai',self.hide_ai.isChecked()); s.setValue('classroom/hide_extensions',self.hide_extensions.isChecked())
        s.setValue('time_tracking',self.track_time.isChecked()); s.setValue('break_reminders',self.break_reminders.isChecked())
        s.setValue('break_minutes',self.break_minutes.value())
        w.code_font = self.code_font.currentFont().family()
        s.setValue('code_font', w.code_font)
        s.setValue('mascot_color', self.mascot_color)
        w.set_mascot_color(self.mascot_color)
        w.speed.setValue(self.speed.value())
        w.set_font_size_all(self.font_size.value())
        w.completions_enabled = self.autocomplete.isChecked()
        self.settings.setValue("autosave", self.autosave.isChecked())
        for editor in w.editors():
            editor.completions_enabled = w.completions_enabled
        w.sound_bank.enabled = self.sounds.isChecked()
        w.sound_bank.volume = self.volume.value() / 100
        w.sound_bank.events = {kind: box.isChecked() for kind, box in self.sound_events.items()}
        s.setValue("stage_grid", self.grid.isChecked())
        w.set_grid(self.grid.isChecked())
        s.setValue("stage_color", self.stage_color.currentData() or "")
        w.apply_stage_color()
        s.setValue("start_home", self.start_home.isChecked())
        s.setValue("ui_scale", self.scale.currentData())
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
        s.setValue("updates/channel", self.channel.currentData())
        s.setValue("updates/auto_check", self.auto_check.isChecked())
        s.setValue("updates/auto_download", self.auto_download.isChecked())
        s.setValue("offline", self.offline.isChecked())
        if self.offline.isChecked():
            w.updates.cancel()
            if w.home_page.feed_worker and w.home_page.feed_worker.isRunning():
                w.home_page.feed_worker.requestInterruption()
            if w.ai_panel.worker and w.ai_panel.worker.isRunning(): w.ai_panel.worker.cancel()
        s.setValue("reduce_motion", self.reduce_motion.isChecked())
        for key,box in self.access_options.items(): s.setValue(key,box.isChecked())
        s.setValue('app_language',self.app_language.currentData())
        w.apply_accessibility()
        w.set_reduce_motion(self.reduce_motion.isChecked())
        w.set_mode("kid" if self.kid.isChecked() else "pro")
        w.set_theme(self.theme.currentData())
        w.save_settings()
        w.ai_panel.refresh_header()
        w.refresh_ai_actions()
        self.accept()


def open_url(url):
    QDesktopServices.openUrl(QUrl(url))
