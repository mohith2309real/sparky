#!/bin/bash
# Runs INSIDE a Linux container: linux_test.sh ARCH
# /t holds Sparky-Linux-ARCH.tar.gz, mock_ai_server.py and web/ (a prepared OTA test).
set -euo pipefail
ARCH="$1"
export DEBIAN_FRONTEND=noninteractive QT_QPA_PLATFORM=offscreen
apt-get update -qq >/dev/null
apt-get install -y -qq python3 libgl1 libegl1 libxkbcommon0 libfontconfig1 libdbus-1-3 \
  libglib2.0-0 >/dev/null 2>&1
install_dir=$(mktemp -d /tmp/sparky-platform-XXXXXX)
cd "$install_dir"
tar -xzf "/t/Sparky-Linux-$ARCH.tar.gz"
cd Sparky
python3 /t/mock_ai_server.py 8773 >/dev/null 2>&1 &
sleep 1
echo "--- selfcheck"
SPARKY_SELFCHECK_AI_URL=http://127.0.0.1:8773 ./sparky selfcheck 2>&1 | tail -1
echo "--- run a program"
printf 'say 6 * 7\n' > /tmp/t.spark && ./sparky run /tmp/t.spark
echo "--- the IDE"
./sparky selfcheck ui "/t/shot-$ARCH.png" 2>&1 | grep "lines drawn"
echo "--- install.sh"
./install.sh >/dev/null && ~/.local/bin/sparky selfcheck 2>&1 | tail -1
echo "--- over-the-air update"
(cd /t/web && python3 -m http.server 8899 >/dev/null 2>&1 &)
sleep 1
export HOME=/tmp/otahome XDG_STATE_HOME=/tmp/otahome/.state SPARKY_SETTINGS_FILE=/tmp/ota.ini
mkdir -p "$HOME"
SPARKY_SELFCHECK_UPDATE_URL=http://127.0.0.1:8899 ./sparky selfcheck 2>&1 | tail -1 | grep -o "installed pack [^ |]*"
./sparky selfcheck 2>&1 | tail -1 | grep -o "running pack [^ |]*"
./sparky selfcheck ui "/t/shot-pack-$ARCH.png" 2>&1 | grep -o "Sparky [^ |]* | installed.*lines drawn: [0-9]*"
echo "--- full update (new runtime: swaps the app folder)"
SPARKY_UPDATE_NO_RELAUNCH=1 SPARKY_SELFCHECK_CHANNEL=stable SPARKY_SELFCHECK_UPDATE_URL=http://127.0.0.1:8899 \
  ./sparky selfcheck 2>&1 | tail -1 | grep -o "staged full update [^ |]*"
for i in $(seq 1 120); do grep -qE "^(ok|failed)" "$XDG_STATE_HOME/sparky/updates/full-update.log" 2>/dev/null && break; sleep 0.5; done
grep -q '^ok' "$XDG_STATE_HOME/sparky/updates/full-update.log"
echo "helper: ok"
./sparky selfcheck 2>&1 | tail -1 | grep -o "signatures ok"
