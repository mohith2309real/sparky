"""Assignment instructions and bounded checks beside the student's own editor."""
import html
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog,QHBoxLayout,QLabel,QPushButton,QTextBrowser,QVBoxLayout
from .learn import CheckWorker


class AssignmentDialog(QDialog):
    def __init__(self,main,task):
        super().__init__(main); self.main,self.task=main,task; self.checker=None
        self.setWindowTitle('Assignment: '+task['title']); self.resize(680,470)
        layout=QVBoxLayout(self)
        title=QLabel(task['title']); title.setTextFormat(Qt.TextFormat.PlainText); title.setObjectName('Heading'); layout.addWidget(title)
        text=QTextBrowser(); text.setHtml('<p>'+html.escape(task['explain']).replace('\n','<br>')+'</p><h3>Starter code</h3><pre>'+html.escape(task['starter'])+'</pre>')
        layout.addWidget(text,1)
        self.result=QLabel('Open the starter in a new tab, then check your work.'); self.result.setWordWrap(True); layout.addWidget(self.result)
        row=QHBoxLayout()
        starter=QPushButton('Open starter'); starter.clicked.connect(lambda:main.open_text(task['starter'],task['title']+' assignment'))
        self.check=QPushButton('Check my work'); self.check.setObjectName('Primary'); self.check.clicked.connect(self.check_work)
        handin=QPushButton('Hand in…'); handin.clicked.connect(main.hand_in)
        row.addWidget(starter); row.addWidget(self.check); row.addWidget(handin); layout.addLayout(row)

    def check_work(self):
        if self.checker and self.checker.isRunning(): return
        if self.main.editor.language.id!='sparky':
            self.result.setText('Choose a Sparky tab to check this assignment.'); return
        self.checker=CheckWorker(self.task,self.main.editor.toPlainText(),self)
        self.check.setEnabled(False); self.result.setText('Checking your program…')
        self.checker.result.connect(self.checked); self.checker.finished.connect(lambda:self.check.setEnabled(True)); self.checker.start()

    def checked(self,ok,message):
        self.result.setText(message)
        if ok: self.main.celebrate()

    def closeEvent(self,event):
        if self.checker and self.checker.isRunning():
            self.checker.requestInterruption()
            if not self.checker.wait(3500): event.ignore(); return
        super().closeEvent(event)
