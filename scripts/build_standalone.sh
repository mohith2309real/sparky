#!/bin/zsh
# Builds the fully self-contained Sparky app: Python, Qt, code, examples,
# assets — everything inside one Sparky.app. Output: dist/Sparky.app and
# dist/Sparky-macOS.zip (ready to attach to a GitHub release).
#
# Needs: .venv with PyQt6 + pyinstaller, and assets/sparky.icns
# (run scripts/make_app_bundle.sh once first if the icns is missing).

set -e
cd "$(dirname "$0")/.."

echo "Building standalone Sparky.app (this takes a minute)..."
.venv/bin/pyinstaller --noconfirm --clean --windowed \
  --name Sparky \
  --paths . \
  --icon assets/sparky.icns \
  --osx-bundle-identifier io.github.mohith2309.sparky \
  --add-data "assets:assets" \
  --add-data "examples:examples" \
  --add-data "extensions:extensions" \
  --add-data "GUIDE.md:." \
  scripts/sparky_entry.py

echo "Zipping for release..."
ditto -c -k --keepParent dist/Sparky.app dist/Sparky-macOS.zip

echo "Done:"
du -sh dist/Sparky.app dist/Sparky-macOS.zip
