# IDE panels: the file explorer, the find/replace bar, the command palette,
# and the Extensions panel (VS Code themes + snippets from Open VSX).

import os
from pathlib import Path

from PyQt6.QtCore import QDir, Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QFileSystemModel
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog,
                             QHBoxLayout, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QPushButton, QTreeView,
                             QVBoxLayout, QWidget)

from . import vscode

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "build",
             "dist", ".idea", ".vscode"}


# ---------- file explorer ----------

class FilesPanel(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 10)
        layout.setSpacing(8)
        title = QLabel("FILES")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        self.folder_label = QLabel("No folder open")
        self.folder_label.setObjectName("FileLabel")
        self.folder_label.setWordWrap(True)
        layout.addWidget(self.folder_label)
        open_btn = QPushButton("📂 Open folder…")
        open_btn.clicked.connect(self.choose_folder)
        layout.addWidget(open_btn)

        self.model = QFileSystemModel(self)
        self.model.setFilter(QDir.Filter.AllDirs | QDir.Filter.Files |
                             QDir.Filter.NoDotAndDotDot)
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        for col in (1, 2, 3):
            self.tree.hideColumn(col)
        self.tree.setHeaderHidden(True)
        self.tree.doubleClicked.connect(self.open_index)
        self.tree.hide()
        layout.addWidget(self.tree, 1)
        self.hint = QLabel("Open a folder to see its files here. Double-click a "
                           "file to open it in a tab.")
        self.hint.setWordWrap(True)
        self.hint.setObjectName("FileLabel")
        layout.addWidget(self.hint)
        layout.addStretch(0)
        self.folder = None

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Open a folder",
                                                str(self.folder or Path.home()))
        if path:
            self.set_folder(Path(path))

    def set_folder(self, folder):
        folder = Path(folder)
        if not folder.is_dir():
            return
        self.folder = folder
        root = self.model.setRootPath(str(folder))
        self.tree.setRootIndex(root)
        self.tree.show()
        self.hint.hide()
        self.folder_label.setText(str(folder))
        self.main.settings.setValue("folder", str(folder))

    def open_index(self, index):
        path = Path(self.model.filePath(index))
        if path.is_file():
            self.main.open_path(path)

    def all_files(self, limit=3000):
        """Files in the open folder, for quick open (Ctrl+P)."""
        if not self.folder:
            return []
        found = []
        for root, dirs, files in os.walk(self.folder):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            for f in files:
                found.append(Path(root) / f)
                if len(found) >= limit:
                    return found
        return found


# ---------- find / replace ----------

class FindBar(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.setObjectName("FindBar")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(4)

        row = QHBoxLayout()
        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("Find")
        self.find_edit.returnPressed.connect(lambda: self.step(False))
        self.find_edit.textChanged.connect(self.update_count)
        row.addWidget(self.find_edit, 1)
        self.count = QLabel("")
        self.count.setObjectName("FileLabel")
        row.addWidget(self.count)
        for text, back in (("↑", True), ("↓", False)):
            b = QPushButton(text)
            b.setObjectName("GhostButton")
            b.clicked.connect(lambda _=False, bk=back: self.step(bk))
            row.addWidget(b)
        self.case = QCheckBox("Aa")
        self.case.setToolTip("Match case")
        self.case.toggled.connect(self.update_count)
        row.addWidget(self.case)
        close = QPushButton("✕")
        close.setObjectName("GhostButton")
        close.clicked.connect(self.hide_bar)
        row.addWidget(close)
        layout.addLayout(row)

        self.replace_row = QWidget()
        rrow = QHBoxLayout(self.replace_row)
        rrow.setContentsMargins(0, 0, 0, 0)
        self.replace_edit = QLineEdit()
        self.replace_edit.setPlaceholderText("Replace with")
        rrow.addWidget(self.replace_edit, 1)
        one = QPushButton("Replace")
        one.clicked.connect(self.replace_one)
        rrow.addWidget(one)
        every = QPushButton("Replace all")
        every.clicked.connect(self.replace_every)
        rrow.addWidget(every)
        layout.addWidget(self.replace_row)
        self.hide()

    def open(self, replace=False):
        self.show()
        self.replace_row.setVisible(replace)
        selected = self.main.editor.textCursor().selectedText()
        if selected and " " not in selected:
            self.find_edit.setText(selected)
        self.find_edit.setFocus()
        self.find_edit.selectAll()
        self.update_count()

    def hide_bar(self):
        self.hide()
        self.main.editor.setFocus()

    def step(self, backward):
        found = self.main.editor.find_text(self.find_edit.text(), backward,
                                           self.case.isChecked())
        self.count.setText(self.count.text() if found else "no matches")

    def update_count(self):
        text = self.find_edit.text()
        if not text:
            self.count.setText("")
            return
        haystack = self.main.editor.toPlainText()
        n = haystack.count(text) if self.case.isChecked() else \
            haystack.lower().count(text.lower())
        self.count.setText(f"{n} found" if n else "no matches")

    def replace_one(self):
        editor = self.main.editor
        cursor = editor.textCursor()
        text = self.find_edit.text()
        same = cursor.selectedText() == text if self.case.isChecked() else \
            cursor.selectedText().lower() == text.lower()
        if cursor.hasSelection() and same:
            cursor.insertText(self.replace_edit.text())
        self.step(False)
        self.update_count()

    def replace_every(self):
        n = self.main.editor.replace_all(self.find_edit.text(), self.replace_edit.text(),
                                         self.case.isChecked())
        self.main.status.showMessage(f"Replaced {n} match{'es' if n != 1 else ''}.")
        self.update_count()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide_bar()
        else:
            super().keyPressEvent(event)


# ---------- command palette ----------

class CommandPalette(QDialog):
    """Type to filter; Enter runs. items: [(label, hint, callback)]."""

    def __init__(self, parent, items, placeholder):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("Palette")
        self.items = items
        self.resize(560, 380)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self.search = QLineEdit()
        self.search.setPlaceholderText(placeholder)
        self.search.textChanged.connect(self.refill)
        self.search.returnPressed.connect(self.run_current)
        layout.addWidget(self.search)
        self.list = QListWidget()
        self.list.itemActivated.connect(lambda _: self.run_current())
        layout.addWidget(self.list, 1)
        self.search.installEventFilter(self)
        self.refill("")
        geo = parent.geometry()
        self.move(geo.x() + (geo.width() - self.width()) // 2, geo.y() + 70)
        self.search.setFocus()

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj is self.search and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                row = self.list.currentRow() + (1 if event.key() == Qt.Key.Key_Down else -1)
                self.list.setCurrentRow(max(0, min(self.list.count() - 1, row)))
                return True
            if event.key() == Qt.Key.Key_Escape:
                self.reject()
                return True
        return super().eventFilter(obj, event)

    def refill(self, text):
        words = text.lower().split()
        self.list.clear()
        for label, hint, callback in self.items:
            hay = label.lower()
            if all(w in hay for w in words):
                item = QListWidgetItem(f"{label}    {hint}" if hint else label)
                item.setData(Qt.ItemDataRole.UserRole, callback)
                self.list.addItem(item)
                if self.list.count() >= 200:
                    break
        if self.list.count():
            self.list.setCurrentRow(0)

    def run_current(self):
        item = self.list.currentItem()
        if item is None:
            return
        callback = item.data(Qt.ItemDataRole.UserRole)
        self.accept()
        callback()


# ---------- extensions ----------

class NetWorker(QThread):
    done = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, fn, *args):
        super().__init__()
        self.fn, self.args = fn, args

    def run(self):
        try:
            self.done.emit(self.fn(*self.args))
        except vscode.ExtensionError as err:
            self.failed.emit(str(err))
        except OSError as err:
            self.failed.emit(f"I couldn't reach Open VSX ({err}). Check your internet.")
        except Exception as err:
            self.failed.emit(str(err))


class ExtensionsPanel(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.workers = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 10)
        layout.setSpacing(8)
        title = QLabel("EXTENSIONS")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        note = QLabel("Get VS Code color themes and code snippets from Open VSX. "
                      "Sparky uses only their themes and snippets — it never runs "
                      "code from an extension.")
        note.setWordWrap(True)
        note.setObjectName("FileLabel")
        layout.addWidget(note)

        row = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setPlaceholderText("Search, e.g. dracula")
        self.query.returnPressed.connect(self.search)
        row.addWidget(self.query, 1)
        self.category = QComboBox()
        self.category.addItems(["Themes", "Snippets", "Everything"])
        row.addWidget(self.category)
        layout.addLayout(row)
        go = QPushButton("Search Open VSX")
        go.clicked.connect(self.search)
        layout.addWidget(go)

        self.status = QLabel("")
        self.status.setObjectName("FileLabel")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.results = QListWidget()
        self.results.setWordWrap(True)
        self.results.itemDoubleClicked.connect(self.install_selected)
        layout.addWidget(self.results, 2)
        install = QPushButton("⬇ Install selected")
        install.clicked.connect(self.install_selected)
        layout.addWidget(install)

        installed_title = QLabel("INSTALLED")
        installed_title.setObjectName("SectionTitle")
        layout.addWidget(installed_title)
        self.installed = QListWidget()
        self.installed.setWordWrap(True)
        layout.addWidget(self.installed, 1)
        buttons = QHBoxLayout()
        remove = QPushButton("Remove")
        remove.clicked.connect(self.remove_selected)
        buttons.addWidget(remove)
        vsix = QPushButton("Install .vsix…")
        vsix.clicked.connect(self.install_file)
        buttons.addWidget(vsix)
        folder = QPushButton("📂")
        folder.setToolTip("Open the extensions folder")
        folder.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(vscode.VSCODE_DIR))))
        buttons.addWidget(folder)
        layout.addLayout(buttons)
        self.refresh_installed()

    def run(self, fn, done, *args):
        worker = NetWorker(fn, *args)
        worker.done.connect(done)
        worker.failed.connect(lambda m: self.status.setText("⚠️ " + m))
        worker.finished.connect(lambda: self.workers.remove(worker))
        self.workers.append(worker)
        worker.start()

    def search(self):
        query = self.query.text().strip()
        if not query:
            return
        category = {"Themes": "Themes", "Snippets": "Snippets"}.get(self.category.currentText())
        self.status.setText("Searching…")
        self.run(vscode.search_open_vsx, self.show_results, query, category)

    def show_results(self, results):
        self.results.clear()
        self.status.setText(f"{len(results)} found. Double-click one to install."
                            if results else "Nothing found — try other words.")
        for r in results:
            item = QListWidgetItem(f"{r['name']}  ·  {r['publisher']}  ·  "
                                   f"{r['downloads']:,} downloads\n{r['description'][:140]}")
            item.setData(Qt.ItemDataRole.UserRole, r)
            self.results.addItem(item)

    def install_selected(self, *_):
        item = self.results.currentItem()
        if item is None:
            return
        r = item.data(Qt.ItemDataRole.UserRole)
        self.status.setText(f"Installing {r['name']}…")
        self.run(vscode.download_and_install, self.installed_ok, r["download"])

    def install_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Install a VS Code extension",
                                              str(Path.home()), "VS Code extensions (*.vsix)")
        if path:
            try:
                self.installed_ok(vscode.install_vsix(path))
            except vscode.ExtensionError as err:
                self.status.setText("⚠️ " + str(err))

    def installed_ok(self, summary):
        parts = []
        if summary["themes"]:
            parts.append(f"{len(summary['themes'])} theme(s)")
        if summary["snippets"]:
            parts.append(f"snippets for {', '.join(sorted({s['language'] for s in summary['snippets']}))}")
        self.status.setText(f"✓ Installed {summary['name']}: {' and '.join(parts)}.")
        self.refresh_installed()
        self.main.vscode_changed()
        if summary["themes"]:
            self.main.set_theme(f"vscode:{summary['id']}:{summary['themes'][0]['label']}")

    def refresh_installed(self):
        self.installed.clear()
        for ext in vscode.installed():
            what = ", ".join(t["label"] for t in ext["themes"]) or \
                "snippets: " + ", ".join(sorted({s["language"] for s in ext["snippets"]}))
            item = QListWidgetItem(f"🎨 {ext['name']} — {what}")
            item.setData(Qt.ItemDataRole.UserRole, ext["id"])
            self.installed.addItem(item)
        for ext in self.main.extension_manager.extensions:
            label = f"⚠️ {ext.name}: {ext.error}" if ext.error else \
                f"🧩 {ext.name} — {ext.blocks_added} Sparky block(s)"
            self.installed.addItem(QListWidgetItem(label))

    def remove_selected(self):
        item = self.installed.currentItem()
        ext_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        if ext_id:
            vscode.uninstall(ext_id)
            self.refresh_installed()
            self.main.vscode_changed()
            if self.main.theme_key.startswith(f"vscode:{ext_id}:"):
                self.main.set_theme("light")
