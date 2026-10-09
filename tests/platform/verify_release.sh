#!/bin/zsh
# Verify every download in build/release on its own platform:
#   Mac (this computer), Linux arm64 (Debian 12) and x86_64 (Ubuntu 22.04) in Docker,
#   Windows under Wine (Debian 13). Each one: selfcheck with a streamed Claude reply
#   (mock server), running a program, the IDE + a screenshot, and an over-the-air update.
# Usage: tests/platform/verify_release.sh [LOGFILE]
set -e
cd "$(dirname "$0")/../.."
LOG="${1:-build/verify.log}"
T=$(mktemp -d /tmp/sparky-verify-XXXX)
cp build/release/Sparky-Linux-*.tar.gz tests/mock_ai_server.py tests/platform/*.sh "$T/"
.buildvenv/bin/python tests/ota_e2e.py --prepare "$T/web" 8899 \
  linux-x86_64=build/release/Sparky-Linux-x86_64.tar.gz:linux-tar \
  linux-arm64=build/release/Sparky-Linux-arm64.tar.gz:linux-tar >/dev/null
W=$T/win && mkdir -p "$W/Sparky"
(cd build/windows/nsis && cp -R Python pkgs Sparky.launch.pyw "$W/Sparky/" \
  && cp -R assets examples extensions GUIDE.md sparky-installed.txt "$W/Sparky/pkgs/" 2>/dev/null || true)
cp -R "$T/web" tests/mock_ai_server.py tests/platform/wine_test.sh "$W/"
{
  echo "=== macOS ($(sw_vers -productVersion))"
  (.venv/bin/python tests/mock_ai_server.py 8773 >/dev/null 2>&1 &); sleep 1
  SPARKY_SELFCHECK_AI_URL=http://127.0.0.1:8773 ./dist/Sparky.app/Contents/MacOS/Sparky selfcheck 2>&1 | tail -1
  pkill -f "mock_ai_server.py 8773" || true
  QT_QPA_PLATFORM=offscreen ./dist/Sparky.app/Contents/MacOS/Sparky selfcheck ui "$T/shot-mac.png" 2>&1 | grep "lines drawn"
  hdiutil verify build/release/Sparky-Installer.dmg 2>&1 | tail -1 | sed 's/.*is /dmg: /'
  codesign --verify --deep --strict dist/Sparky.app && echo "codesign: valid (ad-hoc)"
  .buildvenv/bin/python tests/ota_e2e.py dist/Sparky.app/Contents/MacOS/Sparky 2>&1 | grep -E "^(PASS|FAIL|OTA)"
  echo "=== Linux arm64 / Debian 12"
  docker run --rm --platform linux/arm64 -v "$T:/t" debian:12 bash /t/linux_test.sh arm64 2>&1 | grep -v "^debconf"
  echo "=== Linux x86_64 / Ubuntu 22.04"
  docker run --rm --platform linux/amd64 -v "$T:/t" ubuntu:22.04 bash /t/linux_test.sh x86_64 2>&1 | grep -v "^debconf"
  echo "=== Windows / Wine (Debian 13)"
  docker run --rm --platform linux/amd64 -v "$W:/w" debian:13 bash /w/wine_test.sh 2>&1 | grep -v "^debconf"
  rm -rf "$T/setup-x" && 7zz x -y -o"$T/setup-x" build/release/Sparky-Setup.exe >/dev/null \
    && diff -rq build/windows/nsis/pkgs/sparky "$T/setup-x/pkgs/sparky" >/dev/null \
    && echo "installer matches the tested Windows build"
  (cd build/release && openssl pkeyutl -verify -pubin -inkey ../../../mohith-sites/sparky/release-key.pem \
     -rawin -in SHA256SUMS.txt -sigfile SHA256SUMS.txt.sig && shasum -a 256 -c SHA256SUMS.txt | tr '\n' ' ')
  echo
  echo "screenshots: $T/shot-*.png $W/shot-windows.png"
} 2>&1 | tee "$LOG"
