"""Make an App: a named fullscreen player with an icon and bundled assets."""
import json
import os
import re
import shlex
import shutil
import stat
import sys
from pathlib import Path

from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from .dialogs import SITE_URL
from ..paths import ASSETS_DIR, FROZEN

SPARKY_DIR = Path(__file__).resolve().parent.parent.parent


def safe_name(name):
    name = re.sub(r'[^\w \-]', '', name).strip()
    return name or 'My App'


def player_command_unix():
    flags = ' --fullscreen --icon "$DIR/icon.png"'
    if FROZEN:
        return 'exec '+shlex.quote(sys.executable)+' play "$DIR/$PROGRAM"'+flags
    return ('SPARKY='+shlex.quote(str(SPARKY_DIR))+'\n'
            'PY="$SPARKY/.venv/bin/python"\n[ -x "$PY" ] || PY=python3\n'
            'cd "$SPARKY" || exit 1\nexec "$PY" -m sparky play "$DIR/$PROGRAM"'+flags)


def build_app(folder, name, source, icon=None, assets=None):
    """Create a new export folder. Existing output is never overwritten."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    name = safe_name(name)
    prog = name+'.spark'
    (folder / prog).write_text(source, encoding='utf-8')
    image = QImage(str(icon or ASSETS_DIR / 'logo_256.png'))
    if image.isNull() or not image.save(str(folder / 'icon.png')):
        raise ValueError('Choose a readable image for the app icon.')
    if assets and Path(assets).is_dir():
        shutil.copytree(assets,folder/'assets',ignore=lambda root,names:[n for n in names if (Path(root)/n).is_symlink()])
    (folder/'app.json').write_text(json.dumps({'name':name,'program':prog,'icon':'icon.png','fullscreen':True},ensure_ascii=False),encoding='utf-8')
    launch = player_command_unix().replace('$PROGRAM',prog)
    common = 'DIR="$(cd "$(dirname "$0")" && pwd)"\n'
    mac = folder / ('Play '+name+'.command')
    mac.write_text('#!/bin/zsh\n'+common+'APP="/Applications/Sparky.app/Contents/MacOS/Sparky"\n'
                   '[ -x "$APP" ] && exec "$APP" play "$DIR/'+prog+'" --fullscreen --icon "$DIR/icon.png"\n'+launch+'\n',encoding='utf-8')
    linux = folder / ('play_'+name.replace(' ','_').lower()+'.sh')
    linux.write_text('#!/bin/sh\n'+common+'command -v sparky >/dev/null 2>&1 && exec sparky play "$DIR/'+prog+
                     '" --fullscreen --icon "$DIR/icon.png"\n'+launch+'\n',encoding='utf-8')
    for script in (mac,linux):
        script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    windows = folder / ('Play '+name+'.bat')
    windows.write_text('@echo off\nset "SPARKY=%LOCALAPPDATA%\\Programs\\Sparky"\n'
                       'if not exist "%SPARKY%\\Python\\pythonw.exe" set "SPARKY=%ProgramFiles%\\Sparky"\n'
                       'if not exist "%SPARKY%\\Python\\pythonw.exe" (\n'
                       '  echo Install Sparky from sparky-code.web.app to play this app.\n  pause\n  exit /b 1\n)\n'
                       'start "" "%SPARKY%\\Python\\pythonw.exe" -c "import os,sys,site; '
                       'site.addsitedir(os.path.join(os.environ[\'SPARKY\'],\'pkgs\')); '
                       'sys.argv=[\'sparky\']+sys.argv[1:]; import sparky_boot; sparky_boot.main()" '
                       'play "%~dp0'+prog+'" --fullscreen --icon "%~dp0icon.png"\n',encoding='utf-8')
    (folder/'README.txt').write_text(name+'\n\nMade with Sparky by Mohith — '+SITE_URL+
                                   '\n\nMac: double-click the Play .command file.\nWindows: double-click the Play .bat file.\n'
                                   'Linux: run the play .sh file.\n\nThe computer needs Sparky. Press Esc to leave fullscreen.\n'
                                   'The code, icon and project assets are included for remixing.\n',encoding='utf-8')
    return folder


def make_app(main_window):
    editor = main_window.editor
    if editor.language.id != 'sparky' or not editor.toPlainText().strip():
        QMessageBox.information(main_window,'Make an App','Write a Sparky program first, then make it an app.')
        return
    name,ok = QInputDialog.getText(main_window,'Make an App','What’s your app called?',text='My App')
    if not ok:
        return
    name = safe_name(name)
    icon,_ = QFileDialog.getOpenFileName(main_window,'Choose an app icon (Cancel uses Sparky’s icon)','',
                                        'Pictures (*.png *.jpg *.jpeg *.svg *.ico)')
    where = QFileDialog.getExistingDirectory(main_window,'Where should the app folder go?',str(Path.home()/'Desktop'))
    if not where:
        return
    folder = Path(where)/name
    number = 2
    while folder.exists():
        folder = Path(where)/(name+' '+str(number))
        number += 1
    project = main_window.project_store.project_for(editor.path)
    try:
        build_app(folder,name,editor.toPlainText(),icon or None,project/'assets' if project else None)
    except (OSError,ValueError) as error:
        QMessageBox.warning(main_window,'Could not make app',str(error))
        return
    QMessageBox.information(main_window,'Your app is ready!', 'Made '+name+' at:\n'+str(folder)+
                            '\n\nOpen the Play file inside. It launches your fullscreen player.')
