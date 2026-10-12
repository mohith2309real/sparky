"""Zip the tested Windows runtime with a launcher and local user-data folders."""
import sys
import zipfile
from pathlib import Path
source,out=map(Path,sys.argv[1:])
launcher=r'''@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0userdata" mkdir "%~dp0userdata"
set "SPARKY_SETTINGS_FILE=%~dp0userdata\settings.ini"
set "SPARKY_USER_DIR=%~dp0userdata\Sparky"
set "SPARKY_DATA_DIR=%~dp0userdata\app-data"
start "" "%~dp0Python\pythonw.exe" "%~dp0Sparky.launch.pyw" %*
'''
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as archive:
    for top in ('Python','pkgs','Sparky.launch.pyw','sparky.ico'):
        path=source/top
        if not path.exists(): raise FileNotFoundError(path)
        paths=[path] if path.is_file() else sorted(path.rglob('*'))
        for item in paths:
            if item.is_file() and '__pycache__' not in item.parts:
                archive.write(item,'Sparky-Portable/'+item.relative_to(source).as_posix())
    # pynsist stages these outside pkgs and moves them during installation.
    # A portable archive must perform that move itself.
    for top in ('assets','examples','extensions','GUIDE.md','sparky-installed.txt'):
        path=source/top
        if not path.exists(): raise FileNotFoundError(path)
        paths=[path] if path.is_file() else sorted(path.rglob('*'))
        for item in paths:
            if item.is_file() and '__pycache__' not in item.parts:
                archive.write(item,'Sparky-Portable/pkgs/'+item.relative_to(source).as_posix())
    archive.writestr('Sparky-Portable/Sparky.bat',launcher.replace('\n','\r\n'))
    console=launcher.replace('start "" "%~dp0Python\\pythonw.exe"','"%~dp0Python\\python.exe"')
    archive.writestr('Sparky-Portable/Sparky-console.bat',console.replace('\n','\r\n'))
    archive.writestr('Sparky-Portable/README.txt','Extract this entire folder, then double-click Sparky.bat.\nSettings, projects and updates stay in userdata beside the launcher.\nMove the whole folder to keep your work. No installer or administrator account is needed.\nMade by Mohith - https://sparky-code.web.app\n')
print(out.name+': '+str(round(out.stat().st_size/1024/1024,1))+' MB')
