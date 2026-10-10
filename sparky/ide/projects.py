"""Local projects, recoverable drafts, immutable versions and portable bundles."""
import hashlib
import json
import os
import re
import shutil
import stat
import time
import uuid
import zipfile
from pathlib import Path, PurePosixPath

MAX_BUNDLE_BYTES = 128 * 1024 * 1024
ASSET_SUFFIXES = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.wav', '.mp3', '.ogg'}
BUNDLE_SUFFIXES = ASSET_SUFFIXES | {'.spark', '.py', '.ino', '.c', '.cpp', '.h', '.txt', '.json'}
TEMPLATES = {
    'Art': 'pen color "orange"\nrepeat 5 times\n  move 100\n  turn 144\nend\n',
    'Game': 'make sprite rocket with costume "🚀"\nwhen key "right" pressed\n  tell rocket\n    pen up\n    point 90\n    move 10\n  end\nend\n',
    'Story': 'backdrop "night"\nsay "Once upon a time..." for 2 seconds\nthink "What happens next?"\n',
    'Music': 'play note 1 for 0.3\nplay note 3 for 0.3\nplay note 5 for 0.6\n',
    'Quiz': 'set score to 0\nask "What is 2 + 2?" into answer\nif answer = 4 then\n  change score by 1\nend\nsay "Score: {score}"\n',
    'Blank': '# My new project\n',
}


def user_root():
    override = os.environ.get('SPARKY_USER_DIR')
    if override:
        return Path(override)
    # Headless tests and screenshots must never alter a child's projects.
    settings = os.environ.get('SPARKY_SETTINGS_FILE')
    return Path(settings).parent / 'Sparky' if settings else Path.home() / 'Sparky'


def atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    tmp.write_text(text, encoding='utf-8')
    if path.exists():
        tmp.chmod(stat.S_IMODE(path.stat().st_mode))
    os.replace(tmp, path)


def read_json(path, default):
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
        return value if isinstance(value, type(default)) else default
    except (OSError, ValueError):
        return default


def safe_name(text):
    value = re.sub(r'[^\w .-]', '', text, flags=re.UNICODE).strip(' .')[:80]
    if not value or value.lower().split('.')[0] in {'con', 'prn', 'aux', 'nul'} | {
            f'{kind}{n}' for kind in ('com', 'lpt') for n in range(1, 10)}:
        raise ValueError('Choose a project name with letters or numbers.')
    return value


class ProjectStore:
    def __init__(self, root=None):
        self.root = Path(root) if root else user_root()
        self.projects = self.root / 'Projects'
        self.projects.mkdir(parents=True, exist_ok=True)
        self.history = self.root / '.history'
        self.recovery = self.root / '.recovery.json'

    def unique_folder(self, name):
        name = safe_name(name)
        target = self.projects / name
        number = 2
        while target.exists():
            target = self.projects / f'{name} {number}'
            number += 1
        return target

    def create(self, name, template='Blank'):
        if template not in TEMPLATES:
            raise ValueError('Choose one of the built-in templates.')
        folder = self.unique_folder(name)
        folder.mkdir()
        (folder / 'assets').mkdir()
        self.save(folder / 'main.spark', TEMPLATES[template])
        return folder

    def list(self):
        return sorted((p for p in self.projects.iterdir() if p.is_dir() and not p.is_symlink()),
                      key=lambda p: p.stat().st_mtime, reverse=True)

    def project_for(self, path):
        if path is None:
            return None
        path = Path(path).resolve()
        try:
            parts = path.relative_to(self.projects.resolve()).parts
        except ValueError:
            return None
        return self.projects / parts[0] if parts else None

    def managed_folder(self, folder):
        folder = Path(folder)
        if folder.is_symlink() or folder.parent.resolve() != self.projects.resolve() or not folder.is_dir():
            raise ValueError('Choose a project from your Projects folder.')
        return folder

    def rename(self, folder, name):
        folder = self.managed_folder(folder)
        target = self.projects / safe_name(name)
        if target.exists() and target != folder:
            raise ValueError('A project with that name already exists.')
        files = [p for p in folder.rglob('*') if p.is_file() and not p.is_symlink()]
        old_keys = [(p.relative_to(folder), hashlib.sha256(str(p.resolve()).encode()).hexdigest()) for p in files]
        folder.rename(target)
        for rel, old_key in old_keys:
            old_history = self.history / old_key
            new_key = hashlib.sha256(str((target / rel).resolve()).encode()).hexdigest()
            if old_history.exists():
                shutil.copytree(old_history, self.history / new_key, dirs_exist_ok=True)
        return target

    def duplicate(self, folder):
        folder = self.managed_folder(folder)
        target = self.unique_folder(folder.name + ' copy')
        # Do not copy symlinked files or folders outside the project.
        shutil.copytree(folder, target, ignore=lambda root, names: [
            n for n in names if (Path(root) / n).is_symlink()])
        return target

    def versions(self, path):
        key = hashlib.sha256(str(Path(path).resolve()).encode()).hexdigest()
        folder = self.history / key
        return sorted(folder.glob('*.json'), reverse=True) if folder.exists() else []

    def snapshot(self, path, text):
        key = hashlib.sha256(str(Path(path).resolve()).encode()).hexdigest()
        folder = self.history / key
        versions = self.versions(path)
        if versions and read_json(versions[0], {}).get('text') == text:
            return
        atomic_write(folder / f'{time.time_ns()}-{uuid.uuid4().hex[:8]}.json', json.dumps({
            'path': str(Path(path).resolve()), 'time': time.time(), 'text': text}, ensure_ascii=False))

    def save(self, path, text):
        path = Path(path)
        if path.is_symlink():
            raise ValueError('Save to a regular file instead of a shortcut.')
        if path.exists():
            previous = path.read_text(encoding='utf-8')
            if previous == text:
                return
            self.snapshot(path, previous)
        atomic_write(path, text)
        self.snapshot(path, text)

    def save_recovery(self, tabs, active=0, clean=False):
        atomic_write(self.recovery, json.dumps({'tabs': tabs, 'active': active, 'clean': clean},
                                              ensure_ascii=False))

    def load_recovery(self):
        return read_json(self.recovery, {})

    def bundle(self, folder, target):
        folder = self.managed_folder(folder)
        entries = []
        total = 0
        for path in sorted(folder.rglob('*')):
            rel = path.relative_to(folder)
            if any(p.startswith('.') for p in rel.parts) or path.is_symlink() or not path.is_file():
                continue
            if path.suffix.lower() not in BUNDLE_SUFFIXES:
                continue
            if not path.resolve().is_relative_to(folder.resolve()):
                continue
            total += path.stat().st_size
            entries.append((path, rel.as_posix()))
        if len(entries) > 1000 or total > MAX_BUNDLE_BYTES:
            raise ValueError('This project is too big to bundle (128 MB or 1,000 files).')
        if not any(rel == 'main.spark' for _, rel in entries):
            raise ValueError('The project needs a main.spark file.')
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
            for path, rel in entries:
                archive.write(path, rel)
        return Path(target)

    def import_bundle(self, source):
        try:
            return self._import_bundle(source)
        except (zipfile.BadZipFile, RuntimeError) as error:
            raise ValueError('This project bundle is damaged or needs a password.') from error

    def _import_bundle(self, source):
        with zipfile.ZipFile(source) as archive:
            infos = archive.infolist()
            if len(infos) > 1000 or sum(i.file_size for i in infos) > MAX_BUNDLE_BYTES:
                raise ValueError('This project bundle is too big.')
            names = set()
            contents = []
            for info in infos:
                rel = PurePosixPath(info.filename)
                if (not info.filename or '\\' in info.filename or ':' in info.filename or rel.is_absolute()
                        or any(p in ('..', '.') or p.startswith('.') for p in rel.parts)
                        or stat.S_ISLNK(info.external_attr >> 16)):
                    raise ValueError('This bundle contains an unsafe path.')
                key = str(rel).casefold()
                if key in names:
                    raise ValueError('This bundle contains duplicate file names.')
                names.add(key)
                if info.is_dir():
                    continue
                if rel.suffix.lower() not in BUNDLE_SUFFIXES:
                    raise ValueError('This bundle contains an unsupported file.')
                contents.append((str(rel), archive.read(info)))
            if not any(name == 'main.spark' for name, _ in contents):
                raise ValueError('The bundle needs a main.spark file.')
            file_names = {name.casefold() for name, _ in contents}
            for name in names:
                if any(str(parent).casefold() in file_names for parent in PurePosixPath(name).parents
                       if str(parent) != '.'):
                    raise ValueError('A bundle file cannot also be a folder.')
            if 'assets' in file_names:
                raise ValueError('Project assets must be a folder.')
        target = self.unique_folder(Path(source).stem)
        target.mkdir()
        for name, data in contents:
            path = target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (target / 'assets').mkdir(exist_ok=True)
        return target
