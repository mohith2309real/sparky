#!/bin/zsh
# Verify every download in build/release on its own platform:
#   Mac (this computer), Linux arm64 (Debian 12) and x86_64 (Ubuntu 22.04) in Docker,
#   Windows under Wine (Debian 13). Each one: selfcheck with a streamed Claude reply
#   (mock server), running a program, the IDE + a screenshot, and an over-the-air update.
# Usage: tests/platform/verify_release.sh [LOGFILE]
set -eu
set -o pipefail
cd "$(dirname "$0")/../.."
LOG="${1:-build/verify.log}"
T=$(mktemp -d /tmp/sparky-verify-XXXX)
cp build/release/Sparky-Linux-*.tar.gz tests/mock_ai_server.py tests/platform/*.sh "$T/"
.buildvenv/bin/python tests/ota_e2e.py --prepare "$T/web" 8899 \
  linux-x86_64=build/release/Sparky-Linux-x86_64.tar.gz:linux-tar \
  linux-arm64=build/release/Sparky-Linux-arm64.tar.gz:linux-tar >/dev/null
W=$T/win && mkdir -p "$W/Sparky"
(cd build/windows/nsis && cp -R Python pkgs Sparky.launch.pyw "$W/Sparky/" \
  && cp -R assets examples extensions GUIDE.md sparky-installed.txt "$W/Sparky/pkgs/")
cp -R "$T/web" tests/mock_ai_server.py tests/platform/wine_test.sh "$W/"
cp build/release/Sparky-Setup.exe "$W/"
.buildvenv/bin/python -m zipfile -e build/release/Sparky-Portable.zip "$W/"
{
  echo "=== macOS ($(sw_vers -productVersion))"
  .venv/bin/python tests/mock_ai_server.py 8773 >/dev/null 2>&1 &
  mock_pid=$!
  trap 'kill "$mock_pid" 2>/dev/null || true' EXIT
  sleep 1
  SPARKY_SELFCHECK_AI_URL=http://127.0.0.1:8773 ./dist/Sparky.app/Contents/MacOS/Sparky selfcheck 2>&1 | tail -1
  kill "$mock_pid"
  trap - EXIT
  QT_QPA_PLATFORM=offscreen ./dist/Sparky.app/Contents/MacOS/Sparky selfcheck ui "$T/shot-mac.png" 2>&1 | grep "lines drawn"
  hdiutil verify build/release/Sparky-Installer.dmg 2>&1 | tail -1 | sed 's/.*is /dmg: /'
  codesign --verify --deep --strict dist/Sparky.app
  echo "codesign: valid (ad-hoc)"
  .buildvenv/bin/python tests/ota_e2e.py dist/Sparky.app/Contents/MacOS/Sparky 2>&1 | grep -E "^(PASS|FAIL|OTA)"
  echo "=== Python 3.10 (the oldest Python the Linux download supports)"
  docker run --rm -v "$PWD:/src:ro" -e PYTHONDONTWRITEBYTECODE=1 -e SPARKY_SKIP_ARDUINO_COMPILE=1 \
    python:3.10-slim bash -e -o pipefail -c 'cd /src
    python -B -c "from pathlib import Path; paths = list(Path(\"sparky\").rglob(\"*.py\")) + [Path(\"sparky_boot.py\")]; [compile(p.read_text(encoding=\"utf-8\"), str(p), \"exec\") for p in paths]; print(\"Python 3.10: all app modules compile\")"
    for t in test_lang test_lang_v2 test_lang_v3 test_to_python test_arduino test_editor_tools test_learning_projects test_extensions; do
      python -B "tests/$t.py" 2>&1 | tail -1
    done'
  echo "=== Linux arm64 / Debian 12"
  docker run --rm --platform linux/arm64 -v "$T:/t" debian:12 bash /t/linux_test.sh arm64 2>&1 | grep -v "^debconf"
  echo "=== Linux x86_64 / Ubuntu 22.04"
  docker run --rm --platform linux/amd64 -v "$T:/t" ubuntu:22.04 bash /t/linux_test.sh x86_64 2>&1 | grep -v "^debconf"
  echo "=== Windows / Wine (Debian 13)"
  docker run --rm --platform linux/amd64 -v "$W:/w" debian:13 bash /w/wine_test.sh 2>&1 | grep -v "^debconf"
  7zz x -y -o"$T/setup-x" build/release/Sparky-Setup.exe >/dev/null
  diff -rq build/windows/nsis/pkgs/sparky "$T/setup-x/pkgs/sparky" >/dev/null
  echo "installer matches the tested Windows build"
  (cd build/release
   openssl pkeyutl -verify -pubin -inkey ../../../mohith-sites/sparky/release-key.pem \
     -rawin -in SHA256SUMS.txt -sigfile SHA256SUMS.txt.sig
   shasum -a 256 -c SHA256SUMS.txt | tr '\n' ' ')
  echo
  echo "screenshots: $T/shot-*.png $W/shot-windows.png"
} 2>&1 | tee "$LOG"
