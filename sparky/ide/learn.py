"""Offline learning worlds, real challenge checks, stars and progress reports."""
import html
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QImage, QPainter
from PyQt6.QtWidgets import (QComboBox, QDialog, QFileDialog, QHBoxLayout, QInputDialog,
                             QLabel, QLineEdit, QPushButton, QSplitter, QTextBrowser,
                             QTreeWidget, QTreeWidgetItem, QVBoxLayout)

from . import docs
from .learning import check_program, daily_lesson
from .learning_data import BY_ID, GLOSSARY, LESSONS, QUIZZES, WORLDS
from ..lang.to_python import to_python


def pre(text):
    return '<pre style="white-space:pre-wrap">' + html.escape(text) + '</pre>'


class CheckWorker(QThread):
    result = pyqtSignal(bool, str)

    def __init__(self, lesson, source, parent):
        super().__init__(parent)
        self.lesson, self.source = lesson, source

    def run(self):
        try:
            ok, text = check_program(self.lesson, self.source, self.isInterruptionRequested)
        except Exception:
            ok, text = False, 'The checker could not finish. Your code is still here; try a smaller program.'
        self.result.emit(ok, text)


class LearnDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.progress = main_window.learning_progress
        self.lesson = self.progress.next_lesson()
        self.checker = None
        self.page = 'lesson'
        self.setWindowTitle('Learn Sparky')
        self.setModal(False)
        self.resize(1080, 730)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        title = QLabel('A little code. A whole new world.')
        title.setObjectName('Heading')
        layout.addWidget(title)
        worlds = QHBoxLayout()
        for key, name, _ in WORLDS:
            button = QPushButton(name)
            button.clicked.connect(lambda checked=False, k=key: self.open_world(k))
            worlds.addWidget(button)
        layout.addLayout(worlds)
        tools = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setObjectName('Field')
        self.search.setPlaceholderText('Search lessons, the reference or glossary…')
        self.search.textChanged.connect(self.search_changed)
        tools.addWidget(self.search, 1)
        for name, fn in [('Daily challenge', self.open_daily), ('Reference', self.show_reference),
                         ('Glossary', self.show_glossary), ('Achievements', self.show_achievements)]:
            b = QPushButton(name)
            b.clicked.connect(fn)
            tools.addWidget(b)
        layout.addLayout(tools)
        split = QSplitter(Qt.Orientation.Horizontal)
        self.list = QTreeWidget()
        self.list.setHeaderHidden(True)
        self.list.setAccessibleName('Worlds, lessons and stars')
        self.list.currentItemChanged.connect(self.item_changed)
        split.addWidget(self.list)
        right = QVBoxLayout()
        from PyQt6.QtWidgets import QWidget
        pane = QWidget()
        pane.setLayout(right)
        self.body = QTextBrowser()
        self.body.setOpenExternalLinks(False)
        code_split = QSplitter(Qt.Orientation.Horizontal)
        code_split.addWidget(self.body)
        self.python_body = QTextBrowser()
        self.python_body.hide()
        code_split.addWidget(self.python_body)
        right.addWidget(code_split, 1)
        self.result = QLabel('Choose a world. Every lesson and challenge works offline.')
        self.result.setWordWrap(True)
        self.result.setObjectName('CardText')
        right.addWidget(self.result)
        self.hint_text = QTextBrowser()
        self.hint_text.setMaximumHeight(170)
        self.hint_text.hide()
        right.addWidget(self.hint_text)
        row = QHBoxLayout()
        self.try_button = QPushButton('Try this code')
        self.try_button.clicked.connect(self.load_code)
        self.challenge_button = QPushButton('Try the challenge')
        self.challenge_button.clicked.connect(self.load_challenge)
        self.check_button = QPushButton('Check my work')
        self.check_button.setObjectName('Primary')
        self.check_button.clicked.connect(self.check_work)
        self.hint_button = QPushButton('Hint')
        self.hint_button.clicked.connect(self.show_hint)
        for button in (self.try_button, self.challenge_button, self.check_button, self.hint_button):
            row.addWidget(button)
        right.addLayout(row)
        self.quiz_options = QComboBox()
        self.quiz_options.hide()
        self.quiz_button = QPushButton('Check my prediction')
        self.quiz_button.clicked.connect(self.grade_quiz)
        self.quiz_button.hide()
        right.addWidget(self.quiz_options)
        right.addWidget(self.quiz_button)
        split.addWidget(pane)
        split.setSizes([260, 750])
        layout.addWidget(split, 1)
        footer = QHBoxLayout()
        for name, fn in [('Predict the output', self.show_quiz), ('Python track', self.show_python),
                         ('Progress report', self.export_report), ('World certificate', self.export_certificate),
                         ('Replay a tour part', main_window.replay_tour_part)]:
            b = QPushButton(name)
            b.clicked.connect(fn)
            footer.addWidget(b)
        layout.addLayout(footer)
        self.refresh_map()
        self.select_lesson(self.lesson['id'])

    def refresh_map(self):
        query = self.search.text().casefold() if self.page == 'lesson' else ''
        self.list.blockSignals(True)
        self.list.clear()
        for key, title, _ in WORLDS:
            total = sum(self.progress.stars(l['id']) for l in LESSONS if l['world'] == key)
            group = QTreeWidgetItem([f'{title}   {total}/18 ★'])
            self.list.addTopLevelItem(group)
            for lesson in LESSONS:
                if lesson['world'] != key or (query and query not in
                        (lesson['title']+' '+lesson['explain']+' '+lesson['goal']).casefold()):
                    continue
                stars = self.progress.stars(lesson['id'])
                item = QTreeWidgetItem([lesson['title'] + ('  '+ '★'*stars if stars else '')])
                item.setData(0, Qt.ItemDataRole.UserRole, lesson['id'])
                group.addChild(item)
            group.setExpanded(True)
            group.setHidden(group.childCount() == 0)
        self.list.blockSignals(False)

    def select_lesson(self, key):
        for i in range(self.list.topLevelItemCount()):
            group = self.list.topLevelItem(i)
            for j in range(group.childCount()):
                item = group.child(j)
                if item.data(0, Qt.ItemDataRole.UserRole) == key:
                    self.list.setCurrentItem(item)
                    self.show_lesson(BY_ID[key])
                    return

    def open_lesson(self, title):
        # Keep old console links such as "3. Remember things" working.
        query = title.split('. ', 1)[-1].casefold()
        match = next((l for l in LESSONS if query in l['title'].casefold()), None)
        if match:
            self.page = 'lesson'
            self.search.clear()
            self.refresh_map()
            self.select_lesson(match['id'])

    def item_changed(self, item, previous):
        key = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        if key in BY_ID:
            self.show_lesson(BY_ID[key])

    def show_lesson(self, lesson):
        self.lesson, self.page = lesson, 'lesson'
        self.python_body.hide()
        self.quiz_options.hide()
        self.quiz_button.hide()
        self.hint_text.hide()
        self.set_lesson_buttons(True)
        self.body.setHtml('<h1>'+html.escape(lesson['title'])+'</h1><p>'+html.escape(lesson['explain'])+
                          '</p><h2>Try it</h2>'+pre(lesson['code'])+'<h2>Your challenge</h2><p>'+
                          html.escape(lesson['goal'])+'</p><p>Earn up to three stars. Hints are always here if you need them.</p>')
        stars = self.progress.stars(lesson['id'])
        self.result.setText('★'*stars+'  Completed' if stars else 'Open the challenge, write your code, then Check my work.')

    def set_lesson_buttons(self, visible):
        for b in (self.try_button, self.challenge_button, self.check_button, self.hint_button):
            b.setVisible(visible)

    def open_world(self, key):
        self.page = 'lesson'
        self.search.clear()
        self.refresh_map()
        self.select_lesson(next(l['id'] for l in LESSONS if l['world'] == key and not self.progress.stars(l['id']))
                           if not self.progress.finished_world(key) else next(l['id'] for l in LESSONS if l['world'] == key))

    def open_daily(self):
        self.page = 'lesson'
        self.search.clear()
        self.refresh_map()
        self.select_lesson(daily_lesson()['id'])
        self.result.setText('Today’s challenge. It changes every day and works offline.')

    def load_code(self):
        self.main_window.open_text(self.lesson['code'], self.lesson['title'])
        self.main_window.status.showMessage('Example opened in a new tab — run it, then make it your own.', 5000)

    def load_challenge(self):
        self.main_window.open_text(self.lesson['starter'], self.lesson['title']+' challenge')
        self.main_window.raise_()

    def check_work(self):
        if self.checker and self.checker.isRunning():
            return
        editor = self.main_window.editor
        if editor.language.id != 'sparky':
            self.result.setText('Choose a Sparky tab to check this challenge.')
            return
        self.result.setText('Trying your program with test answers and events…')
        self.check_button.setEnabled(False)
        self.checker = CheckWorker(self.lesson, editor.toPlainText(), self)
        self.checker.result.connect(self.checked)
        self.checker.finished.connect(lambda: self.check_button.setEnabled(True))
        self.checker.start()

    def checked(self, ok, text):
        lesson = self.checker.lesson
        if ok:
            try:
                finished_world = self.progress.complete(lesson)
            except OSError:
                self.result.setText('Your program passed, but progress could not be saved. Check the project folder permissions.')
                return
            self.refresh_map()
            self.main_window.celebrate()
            if finished_world:
                self.main_window.toast('World complete! You can save your certificate.', 5000)
        self.result.setText(lesson['title']+': '+text)

    def show_hint(self):
        try:
            level = self.progress.hint(self.lesson['id'])
        except OSError:
            level = 1
        self.hint_text.setHtml('<b>Hint '+str(level)+' of 3</b>'+pre(self.lesson['hints'][level-1]))
        self.hint_text.show()

    def search_changed(self):
        if self.page == 'reference':
            self.show_reference()
        elif self.page == 'glossary':
            self.show_glossary()
        else:
            self.page = 'lesson'
            self.refresh_map()

    def info_page(self, title, body):
        self.set_lesson_buttons(False)
        self.python_body.hide()
        self.hint_text.hide()
        self.quiz_options.hide()
        self.quiz_button.hide()
        self.body.setHtml('<h1>'+html.escape(title)+'</h1>'+body)
        self.result.setText('Everything here is built in and works offline.')

    def show_reference(self):
        self.page = 'reference'
        query = self.search.text().casefold()
        entries = dict(docs.COMMANDS, **docs.FUNCTIONS, **docs.VALUES)
        body = ''.join('<h2>'+html.escape(word)+'</h2><p>'+html.escape(info[0])+'</p>'+pre(info[1])
                       for word,info in sorted(entries.items()) if not query or query in (word+' '+str(info)).casefold())
        self.info_page('Language reference', body or '<p>No matching commands. Try a shorter word.</p>')

    def show_glossary(self):
        self.page = 'glossary'
        query = self.search.text().casefold()
        self.info_page('Coding words', ''.join('<h2>'+html.escape(k)+'</h2><p>'+html.escape(v)+'</p>'
                       for k,v in GLOSSARY.items() if not query or query in (k+' '+v).casefold()))

    def show_achievements(self):
        self.page = 'achievements'
        badges = self.progress.badges()
        self.info_page('Your achievements', '<p>'+str(sum(self.progress.stars(l['id']) for l in LESSONS))+
                       ' of 90 stars · '+str(self.progress.data['runs'])+' programs run</p>'+''.join(
                       '<h2>★ '+html.escape(b)+'</h2>' for b in badges)+
                       '<p>Milestones: your first program, your first game, 100 runs, and each completed world.</p>')

    def show_python(self):
        self.page = 'python'
        lesson = self.lesson if self.lesson['id'] in {'hello','memory','repeat','choices','lists','answers'} else BY_ID['hello']
        self.info_page('Sparky', pre(lesson['code']))
        self.python_body.setHtml('<h1>Python</h1>'+pre(to_python(lesson['code'])))
        self.python_body.show()
        self.result.setText('Compare the two programs. Use Run → Show as Python on your own code to try it.')

    def show_quiz(self):
        self.page = 'quiz'
        self.quiz_index = getattr(self, 'quiz_index', -1) + 1
        quiz = QUIZZES[self.quiz_index % len(QUIZZES)]
        self.info_page('Predict the output', '<p>Read this code before running it. What will it say?</p>'+pre(quiz[0]))
        self.quiz_options.clear()
        self.quiz_options.addItems(quiz[1])
        self.quiz_options.show()
        self.quiz_button.show()

    def grade_quiz(self):
        quiz = QUIZZES[self.quiz_index % len(QUIZZES)]
        ok = self.quiz_options.currentIndex() == quiz[2]
        self.result.setText(('You got it! ' if ok else 'Try another prediction. ')+quiz[3])

    def export_report(self):
        name, ok = QInputDialog.getText(self, 'Progress report', 'Learner’s name:', text='My')
        if not ok:
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Save progress report', 'Sparky progress.html', 'Web pages (*.html)')
        if path:
            try:
                Path(path).write_text(self.progress.report(name), encoding='utf-8')
                self.result.setText('Progress report saved.')
            except OSError:
                self.result.setText('Could not save the report there. Try another folder.')

    def certificate_image(self, name, world):
        image = QImage(1200, 850, QImage.Format.Format_ARGB32)
        image.fill(QColor('#faf9f5'))
        p = QPainter(image)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QColor('#d97757'))
        p.drawRect(30,30,1140,790)
        for y, size, text, color in [(130,24,'SPARKY • WORLD EXPLORER','#d97757'),
                                     (260,48,'You made it!','#141413'),(410,40,name,'#141413'),
                                     (530,28,'Completed the '+world+' world','#141413'),
                                     (670,20,'Six challenges. A world of new ideas.','#6b685f')]:
            font = QFont('Figtree',size)
            font.setBold(size >= 40)
            p.setFont(font)
            p.setPen(QColor(color))
            p.drawText(70,y-70,1060,140,Qt.AlignmentFlag.AlignCenter,text)
        p.end()
        return image

    def export_certificate(self):
        world = self.lesson['world']
        if not self.progress.finished_world(world):
            self.result.setText('Complete all six challenges in this world to earn its certificate.')
            return
        name, ok = QInputDialog.getText(self, 'World certificate', 'Learner’s name:')
        if not ok or not name.strip():
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Save world certificate', 'Sparky certificate.png', 'Pictures (*.png)')
        if path:
            title = next(title for key,title,_ in WORLDS if key == world)
            saved = self.certificate_image(name, title).save(path)
            self.result.setText('Certificate saved. Well done!' if saved else 'Could not save the certificate there.')

    def closeEvent(self, event):
        if self.checker and self.checker.isRunning():
            self.checker.requestInterruption()
            if not self.checker.wait(3500):
                event.ignore()
                return
        super().closeEvent(event)
