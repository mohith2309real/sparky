#!/bin/zsh
# Builds every download into build/release/:
#   Sparky-Installer.dmg        macOS (Apple silicon) — the download
#   Sparky-mac-arm64.zip        macOS app as a zip — the over-the-air full update
#   Sparky-Setup.exe            Windows 10/11 (64-bit)
#   Sparky-Linux-x86_64.tar.gz  Linux PCs
#   Sparky-Linux-arm64.tar.gz   Raspberry Pi 4/5 and other ARM64 Linux
#   SHA256SUMS.txt (+ .sig)     checksums, signed with Sparky's release key
#
# Uses .buildvenv (pynsist, cryptography, huggingface_hub); makensis must be installed.
set -e
cd "$(dirname "$0")/.."
[ -x .buildvenv/bin/python ] || { python3 -m venv .buildvenv && .buildvenv/bin/pip install -q pynsist huggingface_hub cryptography; }
BUILD_PY="${BUILD_PY:-$PWD/.buildvenv/bin/python}"
./scripts/build_standalone.sh
BUILD_PY="$BUILD_PY" ./scripts/build_windows.sh
BUILD_PY="$BUILD_PY" ./scripts/build_linux.sh
rm -rf build/release && mkdir -p build/release
cp dist/Sparky-Installer.dmg build/windows/Sparky-Setup.exe build/linux/*.tar.gz build/release/
cp dist/Sparky-macOS.zip build/release/Sparky-mac-arm64.zip
(cd scripts/release && "$BUILD_PY" sign_sums.py ../../build/release)
ls -lh build/release
