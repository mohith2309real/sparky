"""An offline sound library and piano that writes ordinary Sparky code."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
                             QGridLayout, QHBoxLayout, QLabel, QListWidget,
                             QPushButton, QTabWidget, QVBoxLayout, QWidget)
from ..lang.music import INSTRUMENTS, SOUND_NAMES, parse_notes


class MusicDialog(QDialog):
    def __init__(self, main):
        super().__init__(main)
        self.main = main
        self.setWindowTitle('Music and sounds')
        self.resize(780, 420)
        layout=QVBoxLayout(self)
        heading=QLabel('Make something you can hear.')
        heading.setObjectName('Heading'); layout.addWidget(heading)
        tabs=QTabWidget(); layout.addWidget(tabs,1)
        piano=QWidget(); keys=QVBoxLayout(piano)
        settings=QHBoxLayout()
        self.instrument=QComboBox(); self.instrument.addItems(INSTRUMENTS)
        self.instrument.setAccessibleName('Piano instrument')
        settings.addWidget(QLabel('Instrument')); settings.addWidget(self.instrument)
        self.duration=QDoubleSpinBox(); self.duration.setRange(.05,4); self.duration.setSingleStep(.05)
        self.duration.setValue(.4); self.duration.setSuffix(' seconds')
        self.duration.setAccessibleName('Note duration'); settings.addWidget(self.duration)
        self.insert=QCheckBox('Write notes into my code'); self.insert.setChecked(True)
        settings.addWidget(self.insert); keys.addLayout(settings)
        keyboard=QGridLayout()
        white=('C','D','E','F','G','A','B')
        for octave in (4,5):
            for degree,note in enumerate(white):
                label=note+str(octave)
                button=QPushButton(label); button.setMinimumHeight(90)
                button.setAccessibleName('Play '+label)
                button.clicked.connect(lambda checked=False,n=label:self.play_note(n))
                keyboard.addWidget(button, (octave-4)*2+1,degree)
                if note not in ('E','B'):
                    sharp=note+'#'+str(octave)
                    black=QPushButton(sharp); black.setMinimumHeight(42)
                    black.setAccessibleName('Play '+sharp)
                    black.clicked.connect(lambda checked=False,n=sharp:self.play_note(n))
                    keyboard.addWidget(black,(octave-4)*2,degree)
        keys.addLayout(keyboard,1)
        keys.addWidget(QLabel('Songs use note names: play song "C D E R G". Chords play notes together.'))
        tabs.addTab(piano,'Piano')
        library=QWidget(); sounds=QVBoxLayout(library)
        self.list=QListWidget(); self.list.addItems(SOUND_NAMES)
        self.list.setAccessibleName('Sound library'); self.list.setCurrentRow(0)
        self.list.itemDoubleClicked.connect(lambda item:self.preview_sound())
        sounds.addWidget(self.list,1)
        row=QHBoxLayout()
        preview=QPushButton('Preview'); preview.clicked.connect(self.preview_sound)
        add=QPushButton('Add to my code'); add.clicked.connect(self.insert_sound)
        row.addWidget(preview); row.addWidget(add); sounds.addLayout(row)
        tabs.addTab(library,'Sound library')
        close=QPushButton('Close'); close.clicked.connect(self.close); layout.addWidget(close,alignment=Qt.AlignmentFlag.AlignRight)

    def write_code(self, code):
        if self.main.editor.language.id != 'sparky':
            self.main.toast('Choose a Sparky tab to add music.')
            return
        self.main.show_workspace()
        cursor=self.main.editor.textCursor()
        if cursor.positionInBlock():
            cursor.insertText('\n')
        cursor.insertText(code)
        self.main.editor.setTextCursor(cursor)

    def play_note(self, note):
        instrument=self.instrument.currentText(); duration=self.duration.value()
        self.main.sound_bank.play_music(instrument,parse_notes(note),duration)
        if self.insert.isChecked():
            self.write_code(f'instrument "{instrument}"\nplay song "{note}" for {duration:g}\n')

    def preview_sound(self):
        item=self.list.currentItem()
        if item: self.main.sound_bank.play(item.text(),0,0)

    def insert_sound(self):
        item=self.list.currentItem()
        if item: self.write_code('play "'+item.text()+'"\n')
