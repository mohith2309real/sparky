#!/bin/zsh
# Builds Sparky.app (macOS app bundle) in the repo root.
# Rerun after changing the logo or version. Keep Sparky.app inside the
# sparky folder — it launches the code that lives next to it.

set -e
cd "$(dirname "$0")/.."

echo "Building icon..."
rm -rf build_iconset.iconset
mkdir build_iconset.iconset
for size in 16 32 64 128 256 512; do
  sips -z $size $size assets/logo.png \
    --out "build_iconset.iconset/icon_${size}x${size}.png" >/dev/null
  double=$((size * 2))
  if [ $double -le 1024 ]; then
    sips -z $double $double assets/logo.png \
      --out "build_iconset.iconset/icon_${size}x${size}@2x.png" >/dev/null
  fi
done
iconutil -c icns build_iconset.iconset -o assets/sparky.icns
rm -rf build_iconset.iconset

echo "Building Sparky.app..."
rm -rf Sparky.app
mkdir -p Sparky.app/Contents/MacOS Sparky.app/Contents/Resources
cp assets/sparky.icns Sparky.app/Contents/Resources/

cat > Sparky.app/Contents/Info.plist <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Sparky</string>
  <key>CFBundleDisplayName</key><string>Sparky</string>
  <key>CFBundleIdentifier</key><string>io.github.mohith2309.sparky</string>
  <key>CFBundleShortVersionString</key><string>2.0.0</string>
  <key>CFBundleExecutable</key><string>sparky</string>
  <key>CFBundleIconFile</key><string>sparky</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

cat > Sparky.app/Contents/MacOS/sparky <<'LAUNCH'
#!/bin/zsh
# Sparky launcher — the app bundle lives inside the sparky folder,
# so the code is three directories up. First run sets up .venv.
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO" || exit 1
if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv || exit 1
fi
if ! .venv/bin/python -c "import PyQt6" 2>/dev/null; then
  .venv/bin/pip install --quiet PyQt6 || exit 1
fi
exec .venv/bin/python -m sparky
LAUNCH
chmod +x Sparky.app/Contents/MacOS/sparky

echo "Done: Sparky.app"
