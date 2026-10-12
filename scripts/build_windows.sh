#!/bin/zsh
# Builds the Windows installer (build/windows/Sparky-Setup.exe) on macOS or
# Linux — no Windows machine needed. Uses pynsist: it bundles the official
# Windows "embeddable" Python, the Windows PyQt6 wheels and Sparky itself,
# then NSIS (makensis) wraps everything into a normal Setup.exe.
#
# Needs: makensis (brew install makensis) and a Python with pynsist:
#   BUILD_PY=/path/to/python-with-pynsist ./scripts/build_windows.sh

set -e
cd "$(dirname "$0")/.."
BUILD_PY="${BUILD_PY:-$PWD/.buildvenv/bin/python}"
VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' sparky/__init__.py)
PYVER=3.12.10
OUT=build/windows
"$BUILD_PY" scripts/archive_build.py "$OUT"
mkdir -p "$OUT/wheels" "$OUT/stage"

echo "Fetching Windows PyQt6 wheels..."
# Qt 6.9: newer Qt needs Windows' own ICU (icuuc.dll), 6.9 carries what it needs
"$BUILD_PY" -m pip download --quiet --only-binary=:all: --platform win_amd64 \
  --python-version 3.12 --implementation cp -d "$OUT/wheels" "PyQt6>=6.9,<6.10"
echo "Fetching the AI helper's Claude SDK..."
"$BUILD_PY" -m pip download --quiet --only-binary=:all: --platform win_amd64 \
  --python-version 3.12 --implementation cp -d "$OUT/wheels" anthropic==1.13.0 certifi

echo "Staging Sparky..."
cp -R sparky sparky_boot.py assets examples extensions GUIDE.md "$OUT/stage/"
find "$OUT/stage" -name "__pycache__" -type d -prune -exec rm -rf {} +
echo "Installed copy of Sparky (user files live in ~/Sparky)." > "$OUT/stage/sparky-installed.txt"
[ -f assets/sparky.ico ] || .venv/bin/python scripts/make_ico.py
cp assets/sparky.ico "$OUT/sparky.ico"

cat > "$OUT/installer.cfg" <<CFG
[Application]
name=Sparky
version=$VERSION
publisher=Mohith
entry_point=sparky_boot:main
icon=sparky.ico
console=false

[Python]
version=$PYVER
bitness=64

[Include]
packages=sparky
    sparky_boot
local_wheels=wheels/*.whl
files=stage/assets > \$INSTDIR\\pkgs
    stage/examples > \$INSTDIR\\pkgs
    stage/extensions > \$INSTDIR\\pkgs
    stage/GUIDE.md > \$INSTDIR\\pkgs
    stage/sparky-installed.txt > \$INSTDIR\\pkgs

[Build]
directory=nsis
installer_name=Sparky-Setup.exe
nsi_template=sparky.nsi
CFG

# desktop shortcut on install, removed again on uninstall
cat > "$OUT/sparky.nsi" <<'NSI'
[% extends "pyapp_msvcrt.nsi" %]
[% block modernui %]
!define MUI_WELCOMEFINISHPAGE_BITMAP "../../../assets/installer-sidebar.bmp"
[[ super() ]]
[% endblock modernui %]
[% block install_shortcuts %]
[[ super() ]]
  SetOutPath "%HOMEDRIVE%\%HOMEPATH%"
  CreateShortCut "$DESKTOP\Sparky.lnk" "$INSTDIR\Python\pythonw.exe" '"$INSTDIR\Sparky.launch.pyw"' "$INSTDIR\sparky.ico"
  SetOutPath "$INSTDIR"
  WriteRegStr HKCU "Software\Classes\Sparky.Program" "" "Sparky program or project"
  WriteRegStr HKCU "Software\Classes\Sparky.Program\DefaultIcon" "" '$INSTDIR\sparky.ico,0'
  WriteRegStr HKCU "Software\Classes\Sparky.Program\shell\open\command" "" '"$INSTDIR\Python\pythonw.exe" "$INSTDIR\Sparky.launch.pyw" "%1"'
  WriteRegStr HKCU "Software\Classes\.spark" "" "Sparky.Program"
  WriteRegStr HKCU "Software\Classes\.sparky" "" "Sparky.Program"
  WriteRegStr HKCU "Software\Classes\.sparkytask" "" "Sparky.Program"
  System::Call 'shell32::SHChangeNotify(i 0x08000000, i 0, p 0, p 0)'
[% endblock install_shortcuts %]
[% block uninstall_shortcuts %]
[[ super() ]]
  Delete "$DESKTOP\Sparky.lnk"
  ReadRegStr $0 HKCU "Software\Classes\.spark" ""
  StrCmp $0 "Sparky.Program" 0 spark_done
  DeleteRegValue HKCU "Software\Classes\.spark" ""
  DeleteRegKey /ifempty HKCU "Software\Classes\.spark"
  spark_done:
  ReadRegStr $0 HKCU "Software\Classes\.sparky" ""
  StrCmp $0 "Sparky.Program" 0 sparky_done
  DeleteRegValue HKCU "Software\Classes\.sparky" ""
  DeleteRegKey /ifempty HKCU "Software\Classes\.sparky"
  sparky_done:
  ReadRegStr $0 HKCU "Software\Classes\.sparkytask" ""
  StrCmp $0 "Sparky.Program" 0 task_done
  DeleteRegValue HKCU "Software\Classes\.sparkytask" ""
  DeleteRegKey /ifempty HKCU "Software\Classes\.sparkytask"
  task_done:
  DeleteRegKey HKCU "Software\Classes\Sparky.Program"
  System::Call 'shell32::SHChangeNotify(i 0x08000000, i 0, p 0, p 0)'
[% endblock uninstall_shortcuts %]
NSI

echo "Building installer..."
(cd "$OUT" && PYTHONPATH="$PWD/stage" "$BUILD_PY" -m nsist installer.cfg)
mv "$OUT/nsis/Sparky-Setup.exe" "$OUT/Sparky-Setup.exe"
"$BUILD_PY" scripts/make_windows_portable.py "$OUT/nsis" "$OUT/Sparky-Portable.zip"
ls -lh "$OUT/Sparky-Setup.exe"
