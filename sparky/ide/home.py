# The Home screen: where Sparky starts. New program, open, learn, the tour,
# recent files, examples, and what's new.

import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QPixmap, QDesktopServices
from PyQt6.QtWidgets import (QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QMenu,
                             QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from . import mascot, whats_new
from .widgets import IconLabel, text_button
from .. import __version__
from ..paths import EXAMPLES_DIR, USER_DIR


class FeedWorker(QThread):
    loaded = pyqtSignal(object)
    failed = pyqtSignal()

    def run(self):
        from .feeds import fetch
        try:
            results = {}
            for kind in ('news', 'projects'):
                if self.isInterruptionRequested(): return
                results[kind] = fetch(kind, USER_DIR / '.feeds')
            if not self.isInterruptionRequested(): self.loaded.emit(results)
        except Exception:
            if not self.isInterruptionRequested(): self.failed.emit()


def greeting(now=None):
    hour = (now or datetime.datetime.now()).hour
    if hour < 5:
        return "Hello, night owl!"
    if hour < 12:
        return "Good morning!"
    if hour < 17:
        return "Good afternoon!"
    return "Good evening!"


def describe(path):
    """The first comment line of a .spark file, as a description."""
    try:
        for line in path.read_text(encoding="utf-8").splitlines()[:6]:
            line = line.strip()
            if line.startswith("#"):
                text = line.lstrip("#").strip()
                if text:
                    return text
    except OSError:
        pass
    return "An example program."


class HomeCard(QFrame):
    clicked = pyqtSignal()

    def __init__(self, icon, title, text, parent=None):
        super().__init__(parent)
        self.setObjectName("HomeCard")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setAccessibleName(title)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)
        if icon:
            badge = IconLabel(icon, role="accent", size=22)
            layout.addWidget(badge)
        heading = QLabel(title)
        heading.setObjectName("SubHeading")
        heading.setWordWrap(True)
        layout.addWidget(heading)
        body = QLabel(text)
        body.setObjectName("CardText")
        body.setWordWrap(True)
        layout.addWidget(body)
        layout.addStretch(1)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(event)


class HomePage(QScrollArea):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.feed_worker = None
        from .feeds import cached
        self.feed_items = {kind: cached(kind, USER_DIR / '.feeds') for kind in ('news', 'projects')}
        self.setObjectName("HomePage")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.inner = QWidget()
        self.inner.setObjectName("HomeInner")
        self.setWidget(self.inner)
        outer = QHBoxLayout(self.inner)
        outer.setContentsMargins(24, 28, 24, 28)
        outer.addStretch(1)
        self.column = QVBoxLayout()
        self.column.setSpacing(18)
        holder = QWidget()
        holder.setLayout(self.column)
        holder.setMaximumWidth(1040)
        holder.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        outer.addWidget(holder, 20)
        outer.addStretch(1)
        self.build()

    def clear(self):
        while self.column.count():
            item = self.column.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
            elif item.layout() is not None:
                self._drop_layout(item.layout())

    def _drop_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
            elif item.layout() is not None:
                self._drop_layout(item.layout())

    def refresh(self):
        self.clear()
        self.build()
        from .widgets import retint
        retint(self.main.palette_colors)

    def build(self):
        main = self.main
        hero = QHBoxLayout()
        hero.setSpacing(16)
        face = QLabel()
        face.setPixmap(mascot.pixmap(76, "happy"))
        hero.addWidget(face)
        words = QVBoxLayout()
        words.setSpacing(2)
        title = QLabel(greeting())
        title.setObjectName("HeroTitle")
        words.addWidget(title)
        sub = QLabel("What do you want to make today?")
        sub.setObjectName("Muted")
        sub.setStyleSheet("font-size: 16px;")
        words.addWidget(sub)
        hero.addLayout(words, 1)
        self.column.addLayout(hero)

        actions = QGridLayout()
        actions.setSpacing(12)
        lesson = main.next_lesson_title() if hasattr(main, "next_lesson_title") else "Lessons"
        cards = [
            ("plus", "New program", "Start with a blank page.", main.new_file),
            ("open", "Open a file", "Keep working on something.", main.open_file),
            ("learn", "Learn to code", lesson, main.show_learn),
            ("tour", "Take the tour", "See everything Sparky can do.", main.start_tour),
        ]
        self.action_cards = {}
        for i, (icon, name, text, slot) in enumerate(cards):
            card = HomeCard(icon, name, text)
            card.clicked.connect(slot)
            card.setMinimumHeight(118)
            actions.addWidget(card, 0, i)
            self.action_cards[name] = card
        self.column.addLayout(actions)

        projects_head = QHBoxLayout()
        projects_head.addWidget(self.section('Your projects'))
        projects_head.addStretch(1)
        create = text_button('New project', icon='plus')
        create.clicked.connect(main.new_project)
        projects_head.addWidget(create)
        self.column.addLayout(projects_head)
        project_grid = QGridLayout()
        project_grid.setSpacing(12)
        projects = main.project_store.list()
        for i, folder in enumerate(projects):
            card = HomeCard(None, folder.name, 'Open, remix or keep creating.')
            picture = QPixmap(str(folder / 'thumbnail.png'))
            if not picture.isNull():
                thumb = QLabel()
                thumb.setPixmap(picture.scaled(220,120,Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation))
                card.layout().insertWidget(0, thumb)
            card.clicked.connect(lambda p=folder: main.open_project(p))
            card.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            card.customContextMenuRequested.connect(lambda pos, p=folder, c=card: self.project_menu(c,p,pos))
            project_grid.addWidget(card, i // 4, i % 4)
        if not projects:
            empty = QLabel('Your creations have a home here. Start a Game, Story, Art, Music or Quiz project.')
            empty.setObjectName('Muted')
            empty.setWordWrap(True)
            project_grid.addWidget(empty,0,0,1,4)
        self.column.addLayout(project_grid)

        lower = QHBoxLayout()
        lower.setSpacing(18)
        left = QVBoxLayout()
        left.setSpacing(10)
        left.addWidget(self.section("Recent"))
        recent = [Path(p) for p in main.recent_files() if Path(p).is_file()][:6]
        if recent:
            for path in recent:
                left.addWidget(self.recent_row(path))
        else:
            empty = QHBoxLayout()
            pic = QLabel()
            pic.setPixmap(mascot.pixmap(48, "thinking"))
            empty.addWidget(pic)
            note = QLabel("Programs you open or save show up here.")
            note.setObjectName("Muted")
            note.setWordWrap(True)
            empty.addWidget(note, 1)
            left.addLayout(empty)
        left.addStretch(1)
        lower.addLayout(left, 3)

        right = QVBoxLayout()
        right.setSpacing(8)
        release = whats_new.notes_for(__version__) or whats_new.latest()
        right.addWidget(self.section(f"What's new in {whats_new.pretty_version(release['version'])}"))
        box = QFrame()
        box.setObjectName("HomeCard")
        inner = QVBoxLayout(box)
        inner.setContentsMargins(16, 12, 16, 12)
        inner.setSpacing(6)
        headline = QLabel(release["title"])
        headline.setObjectName("SubHeading")
        headline.setWordWrap(True)
        inner.addWidget(headline)
        for item in release["items"][:6]:
            row = QLabel(f"•  {item}")
            row.setObjectName("CardText")
            row.setWordWrap(True)
            inner.addWidget(row)
        more = text_button("All release notes", object_name="LinkButton")
        more.clicked.connect(main.show_whats_new)
        inner.addWidget(more, 0, Qt.AlignmentFlag.AlignLeft)
        right.addWidget(box)
        right.addStretch(1)
        lower.addLayout(right, 2)
        self.column.addLayout(lower)

        feed_head = QHBoxLayout()
        feed_head.addWidget(self.section('News & ideas'))
        feed_head.addStretch(1)
        refresh = text_button('Refresh news')
        refresh.setEnabled(not main.settings.value('offline', False, type=bool) and
                           not (self.feed_worker and self.feed_worker.isRunning()))
        refresh.clicked.connect(self.refresh_feeds)
        feed_head.addWidget(refresh)
        self.column.addLayout(feed_head)
        self.feed_refresh_button = refresh
        for item in self.feed_items['news'][:3]:
            card = HomeCard('info', item['title'], item['description'])
            if item.get('url'):
                card.clicked.connect(lambda url=item['url']: QDesktopServices.openUrl(QUrl(url)))
            self.column.addWidget(card)
        featured = QGridLayout()
        for i, item in enumerate(self.feed_items['projects'][:3]):
            card = HomeCard('code', item['title'], item['description'] + ' Open a copy to try it.')
            card.clicked.connect(lambda entry=item: self.open_featured(entry))
            featured.addWidget(card, 0, i)
        self.column.addLayout(featured)
        if not any(self.feed_items.values()):
            self.column.addWidget(QLabel('No news yet. Try one of the examples below.'))

        self.column.addWidget(self.section("Examples"))
        examples = sorted(EXAMPLES_DIR.rglob('*.spark')) if EXAMPLES_DIR.is_dir() else []
        categories = sorted({p.parent.name if p.parent != EXAMPLES_DIR else 'Basics' for p in examples})
        category = QComboBox()
        category.addItems(['All examples'] + categories)
        selected = main.settings.value('example_category','All examples',type=str)
        category.setCurrentText(selected if selected in categories else 'All examples')
        category.currentTextChanged.connect(self.change_category)
        self.column.addWidget(category)
        grid = QGridLayout()
        grid.setSpacing(12)
        examples = [p for p in examples if category.currentText() == 'All examples' or
                    (p.parent.name if p.parent != EXAMPLES_DIR else 'Basics') == category.currentText()]
        for i, path in enumerate(examples):
            card = HomeCard(None, path.stem.replace("_", " ").title(), describe(path))
            card.setMinimumHeight(92)
            card.clicked.connect(lambda p=path: main.open_example(p))
            grid.addWidget(card, i // 4, i % 4)
        self.column.addLayout(grid)
        self.column.addStretch(1)

    def section(self, text):
        label = QLabel(text.upper())
        label.setObjectName("CardTitle")
        return label

    def refresh_feeds(self):
        if self.main.settings.value('offline', False, type=bool):
            self.main.toast('Turn off Offline mode to refresh news.'); return
        if self.feed_worker and self.feed_worker.isRunning(): return
        self.feed_worker = FeedWorker(self)
        self.feed_worker.loaded.connect(self.feeds_loaded)
        self.feed_worker.failed.connect(lambda: self.main.toast('News could not refresh. Your saved ideas are still here.'))
        self.feed_worker.finished.connect(lambda: self.feed_refresh_button.setEnabled(
            not self.main.settings.value('offline', False, type=bool)))
        self.feed_refresh_button.setEnabled(False)
        self.feed_worker.start()

    def feeds_loaded(self, items):
        self.feed_items = items
        self.refresh()

    def open_featured(self, item):
        self.main.new_tab(item['code'], None, None, item['title'] + '.spark')
        self.main.show_workspace()

    def change_category(self, key):
        self.main.settings.setValue('example_category', key)
        self.refresh()

    def project_menu(self, card, folder, pos):
        menu = QMenu(card)
        menu.addAction('Open', lambda: self.main.open_project(folder))
        for title, action in [('Rename…','rename'),('Duplicate','duplicate'),('Move to Trash','trash')]:
            menu.addAction(title, lambda checked=False, a=action: self.main.project_action(folder,a))
        menu.exec(card.mapToGlobal(pos))

    def recent_row(self, path):
        row = HomeCard(None, path.name, str(path.parent).replace(str(Path.home()), "~"))
        row.layout().setContentsMargins(14, 8, 14, 8)
        row.setMinimumHeight(0)
        row.clicked.connect(lambda p=path: self.main.open_path(p))
        return row
