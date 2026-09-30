#!/bin/bash
# Builds portable Linux packages of Sparky on macOS or Linux:
#   build/linux/Sparky-Linux-x86_64.tar.gz    (most PCs and laptops)
#   build/linux/Sparky-Linux-arm64.tar.gz     (Raspberry Pi 4/5 with 64-bit OS)
#
# Each package bundles Qt (PyQt6 wheels, unpacked) and uses the Python 3.10+
# that Linux desktops already have. Unpack and run ./sparky, or run
# ./install.sh to add Sparky to the app menu (no sudo needed).
#
#   BUILD_PY=/path/to/python-with-pip ./scripts/build_linux.sh

set -euo pipefail
cd "$(dirname "$0")/.."
BUILD_PY="${BUILD_PY:-python3}"
OUT=build/linux
rm -rf "$OUT"
mkdir -p "$OUT"

# glibc floors: x86_64 wheels need glibc 2.28+ (2019+ distros);
# arm64 stops at 2.36 so Raspberry Pi OS (Debian 12) works.
platforms() {
  case "$1" in
    x86_64) echo manylinux_2_28_x86_64 manylinux2014_x86_64 manylinux1_x86_64 ;;
    arm64)  echo manylinux_2_36_aarch64 manylinux_2_35_aarch64 manylinux_2_34_aarch64 \
                 manylinux_2_31_aarch64 manylinux_2_28_aarch64 manylinux2014_aarch64 ;;
  esac
}

build_arch() {
  local arch="$1" pkg="$OUT/Sparky"
  local wheels="$OUT/wheels-$arch"
  local plat=()
  for p in $(platforms "$arch"); do plat+=(--platform "$p"); done

  echo "== $arch: fetching Qt"
  mkdir -p "$wheels"
  "$BUILD_PY" -m pip download --quiet --only-binary=:all: "${plat[@]}" \
    --python-version 3.12 --implementation cp -d "$wheels" PyQt6
  for v in 3.10 3.11 3.13 3.14; do   # one sip build per Python version
    "$BUILD_PY" -m pip download --quiet --only-binary=:all: "${plat[@]}" \
      --python-version "$v" --implementation cp --no-deps -d "$wheels" PyQt6-sip
  done

  echo "== $arch: assembling"
  rm -rf "$pkg"
  mkdir -p "$pkg/app"
  for w in "$wheels"/*.whl; do
    "$BUILD_PY" -m zipfile -e "$w" "$pkg/app/"
  done
  rm -rf "$pkg/app/"*.dist-info
  cp -R sparky assets examples extensions GUIDE.md "$pkg/app/"
  find "$pkg/app/sparky" -name "__pycache__" -type d -prune -exec rm -rf {} +
  echo "Installed copy of Sparky (user files live in ~/Sparky)." > "$pkg/app/sparky-installed.txt"
  cp assets/logo_256.png "$pkg/sparky.png"

  cat > "$pkg/sparky" <<'RUN'
#!/bin/sh
# Starts Sparky. Works from wherever this folder lives.
HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
PY=""
for c in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo "Sparky needs Python 3.10 or newer. Install it with your package manager (for example: sudo apt install python3)." >&2
  exit 1
fi
# prefer Wayland when the desktop uses it, fall back to X11
if [ -n "${WAYLAND_DISPLAY:-}" ] && [ -z "${QT_QPA_PLATFORM:-}" ]; then
  export QT_QPA_PLATFORM="wayland;xcb"
fi
export PYTHONPATH="$HERE/app${PYTHONPATH:+:$PYTHONPATH}"
exec "$PY" -m sparky "$@"
RUN

  cat > "$pkg/install.sh" <<'INST'
#!/bin/sh
# Adds Sparky to your app menu and to the terminal as `sparky`. No sudo.
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.local/share/sparky"
mkdir -p "$DEST" "$HOME/.local/bin" "$HOME/.local/share/applications" \
         "$HOME/.local/share/icons/hicolor/256x256/apps"
rm -rf "$DEST/app"
cp -R "$SRC/app" "$SRC/sparky" "$SRC/sparky.png" "$SRC/uninstall.sh" "$DEST/"
chmod +x "$DEST/sparky" "$DEST/uninstall.sh"
ln -sf "$DEST/sparky" "$HOME/.local/bin/sparky"
cp "$SRC/sparky.png" "$HOME/.local/share/icons/hicolor/256x256/apps/sparky.png"
cat > "$HOME/.local/share/applications/sparky.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=Sparky
Comment=A coding app for kids
Exec=$DEST/sparky
Icon=sparky
Terminal=false
Categories=Education;Development;
DESK
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true
echo "Sparky is installed. Find it in your app menu, or type: sparky"
if command -v ldconfig >/dev/null 2>&1 && ! ldconfig -p 2>/dev/null | grep -q libxcb-cursor; then
  echo "Tip: if Sparky doesn't open on X11, run: sudo apt install libxcb-cursor0"
fi
INST

  cat > "$pkg/uninstall.sh" <<'UNINST'
#!/bin/sh
# Removes Sparky. Your programs in ~/Sparky are kept.
rm -rf "$HOME/.local/share/sparky"
rm -f "$HOME/.local/bin/sparky" "$HOME/.local/share/applications/sparky.desktop" \
      "$HOME/.local/share/icons/hicolor/256x256/apps/sparky.png"
echo "Sparky was removed. Your programs in ~/Sparky are still there."
UNINST

  cat > "$pkg/README.txt" <<'TXT'
Sparky for Linux
================

Run it right away:     ./sparky
Add it to your menu:   ./install.sh     (no sudo; remove with ./uninstall.sh)

Needs Python 3.10 or newer, which most Linux desktops already have.
If Sparky doesn't open on an X11 desktop:  sudo apt install libxcb-cursor0

Your programs, gallery and extensions live in ~/Sparky.
Made by Mohith - https://mohith2309.web.app
TXT

  chmod +x "$pkg/sparky" "$pkg/install.sh" "$pkg/uninstall.sh"
  local name="Sparky-Linux-$arch.tar.gz"
  (cd "$OUT" && COPYFILE_DISABLE=1 tar --no-xattrs -czf "$name" Sparky)
  rm -rf "$pkg"
  ls -lh "$OUT/$name"
}

build_arch x86_64
build_arch arm64
