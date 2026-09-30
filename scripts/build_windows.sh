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
BUILD_PY="${BUILD_PY:-python3}"
PYVER=3.12.10
OUT=build/windows
rm -rf "$OUT"
mkdir -p "$OUT/wheels" "$OUT/stage"

echo "Fetching Windows PyQt6 wheels..."
# Qt 6.9: newer Qt needs Windows' own ICU (icuuc.dll), 6.9 carries what it needs
"$BUILD_PY" -m pip download --quiet --only-binary=:all: --platform win_amd64 \
  --python-version 3.12 --implementation cp -d "$OUT/wheels" "PyQt6>=6.9,<6.10"

echo "Staging Sparky..."
cp -R sparky assets examples extensions GUIDE.md "$OUT/stage/"
find "$OUT/stage" -name "__pycache__" -type d -prune -exec rm -rf {} +
echo "Installed copy of Sparky (user files live in ~/Sparky)." > "$OUT/stage/sparky-installed.txt"
[ -f assets/sparky.ico ] || .venv/bin/python scripts/make_ico.py
cp assets/sparky.ico "$OUT/sparky.ico"

cat > "$OUT/installer.cfg" <<CFG
[Application]
name=Sparky
version=1.0.0
publisher=Mohith
entry_point=sparky.__main__:main
icon=sparky.ico
console=false

[Python]
version=$PYVER
bitness=64

[Include]
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
[% block install_shortcuts %]
[[ super() ]]
  SetOutPath "%HOMEDRIVE%\%HOMEPATH%"
  CreateShortCut "$DESKTOP\Sparky.lnk" "$INSTDIR\Python\pythonw.exe" '"$INSTDIR\Sparky.launch.pyw"' "$INSTDIR\sparky.ico"
  SetOutPath "$INSTDIR"
[% endblock install_shortcuts %]
[% block uninstall_shortcuts %]
[[ super() ]]
  Delete "$DESKTOP\Sparky.lnk"
[% endblock uninstall_shortcuts %]
NSI

echo "Building installer..."
(cd "$OUT" && PYTHONPATH="$PWD/stage" "$BUILD_PY" -m nsist installer.cfg)
mv "$OUT/nsis/Sparky-Setup.exe" "$OUT/Sparky-Setup.exe"
ls -lh "$OUT/Sparky-Setup.exe"
