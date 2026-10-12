#!/bin/zsh
# Builds the fully self-contained Sparky app: Python, Qt, code, examples,
# assets — everything inside one Sparky.app. Output: dist/Sparky.app,
# dist/Sparky-macOS.zip and dist/Sparky-Installer.dmg (the Mac download).
#
# Needs: .venv with PyQt6 + pyinstaller, and assets/sparky.icns
# (run scripts/make_app_bundle.sh once first if the icns is missing).

set -e
cd "$(dirname "$0")/.."
.venv/bin/python scripts/archive_build.py dist build/Sparky

echo "Building standalone Sparky.app (this takes a minute)..."
EXTRA=($(.venv/bin/python scripts/stdlib_imports.py))
.venv/bin/pyinstaller --noconfirm --clean --windowed \
  --name Sparky \
  --paths . \
  --hidden-import anthropic \
  --hidden-import sparky_boot \
  "${EXTRA[@]}" \
  --collect-data certifi \
  --icon assets/sparky.icns \
  --osx-bundle-identifier io.github.mohith2309.sparky \
  --add-data "assets:assets" \
  --add-data "examples:examples" \
  --add-data "extensions:extensions" \
  --add-data "GUIDE.md:." \
  scripts/sparky_entry.py

.venv/bin/python scripts/mac_plist.py dist/Sparky.app

echo "Zipping for release (this zip is also the Mac over-the-air full update)..."
rm -f dist/Sparky-macOS.zip
ditto -c -k --keepParent dist/Sparky.app dist/Sparky-macOS.zip

echo "Building the drag-to-Applications installer..."
.buildvenv/bin/python scripts/make_dmg.py

echo "Done:"
du -sh dist/Sparky.app dist/Sparky-macOS.zip dist/Sparky-Installer.dmg
