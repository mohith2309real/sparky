#!/bin/zsh
# Builds every download into build/release/:
#   Sparky-Installer.dmg        macOS (Apple silicon)
#   Sparky-Setup.exe            Windows 10/11 (64-bit)
#   Sparky-Linux-x86_64.tar.gz  Linux PCs
#   Sparky-Linux-arm64.tar.gz   Raspberry Pi 4/5 and other ARM64 Linux
#
# BUILD_PY must be a Python with pip + pynsist; makensis must be installed.
set -e
cd "$(dirname "$0")/.."
./scripts/build_standalone.sh
BUILD_PY="${BUILD_PY:-python3}" ./scripts/build_windows.sh
BUILD_PY="${BUILD_PY:-python3}" ./scripts/build_linux.sh
rm -rf build/release && mkdir -p build/release
cp dist/Sparky-Installer.dmg build/windows/Sparky-Setup.exe build/linux/*.tar.gz build/release/
(cd build/release && shasum -a 256 * > SHA256SUMS.txt)
ls -lh build/release
