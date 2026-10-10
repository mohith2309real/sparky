#!/bin/bash
# Runs INSIDE a debian:13 amd64 container with wine: wine_test.sh
# /w holds Sparky/ (the installed tree from build/windows/nsis), mock_ai_server.py and web/.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive WINEDEBUG=-all QT_QPA_PLATFORM=offscreen
apt-get update -qq >/dev/null
apt-get install -y -qq wine wine64 python3 >/dev/null 2>&1
PY="wine /w/Sparky/Python/python.exe"
APP="/w/Sparky/Sparky.launch.pyw"
python3 /w/mock_ai_server.py 8773 >/dev/null 2>&1 &
(cd /w/web && python3 -m http.server 8899 >/dev/null 2>&1 &)
sleep 1
echo "--- selfcheck"
SPARKY_SELFCHECK_AI_URL=http://127.0.0.1:8773 $PY $APP selfcheck 2>&1 | grep "Sparky" | tail -1
echo "--- run a program"
printf 'say 6 * 7\n' > /tmp/t.spark && $PY $APP run 'Z:\tmp\t.spark' 2>&1 | tail -1
echo "--- the IDE"
$PY $APP selfcheck ui 'Z:\w\shot-windows.png' 2>&1 | grep "lines drawn"
echo "--- over-the-air update"
export SPARKY_SETTINGS_FILE='Z:\tmp\ota.ini'
SPARKY_SELFCHECK_UPDATE_URL=http://127.0.0.1:8899 $PY $APP selfcheck 2>&1 | grep -o "installed pack [^ |]*"
$PY $APP selfcheck 2>&1 | grep -o "running pack [^ |]*"
