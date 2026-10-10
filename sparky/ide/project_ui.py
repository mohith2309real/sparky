"""Project templates, assets, saved versions and share cards."""
import datetime
import html
import hashlib
import json
import shutil
from pathlib import Path

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog,
                             QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                             QMessageBox, QPushButton, QTextBrowser, QVBoxLayout, QWidget)

from .projects import ASSET_SUFFIXES, TEMPLATES, read_json


class NewProjectDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle('Make something new')
        self.resize(520, 330)
        layout = QVBoxLayout(self)
        title = QLabel('What will you make?')
        title.setObjectName('Heading')
        layout.addWidget(title)
        self.name = QLineEdit('My project')
        self.name.setObjectName('Field')
        self.name.setAccessibleName('Project name')
        layout.addWidget(self.name)
        self.template = QComboBox()
        self.template.addItems(TEMPLATES)
        self.template.setAccessibleName('Project template')
        layout.addWidget(self.template)
        self.preview = QTextBrowser()
        self.template.currentTextChanged.connect(self.show_preview)
        layout.addWidget(self.preview, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Create project')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.show_preview(self.template.currentText())

    def show_preview(self, key):
        self.preview.setPlainText(TEMPLATES[key])


class AssetsPanel(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        layout = QVBoxLayout(self)
        title = QLabel('PROJECT ASSETS')
        title.setObjectName('SectionTitle')
        layout.addWidget(title)
        self.hint = QLabel('Images and sounds travel with your project.')
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        self.list = QListWidget()
        self.list.setAccessibleName('Project images and sounds')
        self.list.itemDoubleClicked.connect(self.preview)
        layout.addWidget(self.list, 1)
        row = QHBoxLayout()
        for label, fn in [('Add', self.add), ('Preview', self.preview_selected), ('Insert path', self.insert_path)]:
            b = QPushButton(label)
            b.clicked.connect(fn)
            row.addWidget(b)
        layout.addLayout(row)

    def folder(self):
        project = self.main.project_store.project_for(self.main.editor.path)
        return project / 'assets' if project else None

    def refresh(self):
        self.list.clear()
        folder = self.folder()
        self.hint.setText('Images and sounds travel with your project.' if folder else
                          'Create or open a project to add its images and sounds.')
        if folder and folder.exists():
            for path in sorted(folder.iterdir()):
                if path.is_file() and not path.is_symlink() and path.suffix.lower() in ASSET_SUFFIXES:
                    item = QListWidgetItem(path.name)
                    item.setData(Qt.ItemDataRole.UserRole, str(path))
                    self.list.addItem(item)

    def showEvent(self, event):
        self.refresh()
        super().showEvent(event)

    def add(self):
        folder = self.folder()
        if folder is None:
            self.main.toast('Create or open a project first.')
            return
        paths, _ = QFileDialog.getOpenFileNames(self, 'Add images and sounds', '',
                                                'Images and sounds (*.png *.jpg *.jpeg *.gif *.svg *.wav *.mp3 *.ogg)')
        for name in paths:
            path = Path(name)
            if path.suffix.lower() not in ASSET_SUFFIXES:
                continue
            target = folder / path.name
            number = 2
            while target.exists():
                target = folder / (path.stem+' '+str(number)+path.suffix)
                number += 1
            try:
                folder.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
            except OSError as error:
                self.main.toast('Could not add '+path.name+': '+str(error))
        self.refresh()

    def preview_selected(self):
        item = self.list.currentItem()
        if item:
            self.preview(item)

    def preview(self, item):
        path = Path(item.data(Qt.ItemDataRole.UserRole))
        if path.suffix.lower() in {'.wav','.mp3','.ogg'}:
            try:
                from PyQt6.QtCore import QUrl
                from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
                if hasattr(self, 'player'):
                    self.player.stop()
                    self.player.deleteLater()
                    self.audio.deleteLater()
                self.audio = QAudioOutput(self)
                self.audio.setVolume(self.main.sound_bank.volume)
                self.player = QMediaPlayer(self)
                self.player.setAudioOutput(self.audio)
                self.player.setSource(QUrl.fromLocalFile(str(path)))
                self.player.play()
            except ImportError:
                self.main.toast('Audio preview needs a full Sparky runtime update.')
            return
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.main.toast('This image could not be previewed.')
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(path.name)
        layout = QVBoxLayout(dialog)
        image = QLabel()
        image.setPixmap(pixmap.scaled(QSize(700,500),Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(image)
        dialog.exec()

    def insert_path(self):
        item = self.list.currentItem()
        if item:
            self.main.editor.insertPlainText(json.dumps('assets/'+item.text(),ensure_ascii=False))


class VersionHistoryDialog(QDialog):
    def __init__(self, main, editor):
        super().__init__(main)
        self.main, self.editor = main, editor
        self.setWindowTitle('Saved versions — '+editor.display_name())
        self.resize(760, 550)
        layout = QVBoxLayout(self)
        self.list = QListWidget()
        self.list.setMaximumHeight(150)
        for path in main.project_store.versions(editor.path):
            value = read_json(path,{})
            stamp = datetime.datetime.fromtimestamp(value.get('time',0)).strftime('%b %d · %H:%M:%S')
            item = QListWidgetItem(stamp)
            item.setData(Qt.ItemDataRole.UserRole, value.get('text',''))
            self.list.addItem(item)
        self.list.currentItemChanged.connect(self.changed)
        layout.addWidget(self.list)
        self.preview = QTextBrowser()
        layout.addWidget(self.preview,1)
        self.restore = QPushButton('Restore this version')
        self.restore.setObjectName('Primary')
        self.restore.clicked.connect(self.restore_selected)
        self.restore.setEnabled(self.list.count()>0)
        layout.addWidget(self.restore)
        if self.list.count():
            self.list.setCurrentRow(0)
        else:
            self.preview.setPlainText('Saved versions appear after your first save.')

    def changed(self, item, previous):
        self.preview.setPlainText(item.data(Qt.ItemDataRole.UserRole) if item else '')

    def restore_selected(self):
        item = self.list.currentItem()
        if item is None:
            return
        # Save a snapshot of unsaved work as well as the file on disk before restoring.
        try:
            self.main.project_store.snapshot(self.editor.path,self.editor.toPlainText())
            text = item.data(Qt.ItemDataRole.UserRole)
            self.main.project_store.save(self.editor.path,text)
            self.editor.disk_digest = hashlib.sha256(self.editor.path.read_bytes()).hexdigest()
        except (OSError, ValueError, UnicodeError) as error:
            QMessageBox.warning(self, 'Could not restore version', str(error))
            return
        self.editor.setPlainText(text)
        self.editor.document().setModified(False)
        self.main.update_tab_title(self.editor)
        self.main.toast('Saved version restored. Your newer work is still in history.')
        self.accept()


def share_image(main):
    image = QImage(1600,1000,QImage.Format.Format_ARGB32)
    image.fill(QColor('#faf9f5'))
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QColor('#141413'))
    p.setFont(QFont('Figtree',30,QFont.Weight.Bold))
    p.drawText(50,65,main.editor.display_name())
    stage = main.stage.render_image(2)
    p.drawImage(50,130,stage.scaled(760,570,Qt.AspectRatioMode.KeepAspectRatio,
                                  Qt.TransformationMode.SmoothTransformation))
    p.setFont(QFont('JetBrains Mono',14))
    lines = main.editor.toPlainText().splitlines()
    for i,line in enumerate(lines[:34]):
        p.drawText(850,145+i*22,line[:56])
    p.setFont(QFont('Figtree',16))
    p.drawText(50,935,'Made with Sparky · sparky-code.web.app')
    if len(lines)>34:
        p.drawText(850,935,'Code preview: first 34 lines')
    p.end()
    return image
