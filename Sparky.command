#!/bin/zsh
# Double-click me to open the Sparky IDE!
# First run sets up its own Python environment (takes a minute).

cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
  echo "First-time setup: preparing Sparky's environment..."
  python3 -m venv .venv || exit 1
fi

if ! .venv/bin/python -c "import PyQt6, anthropic" 2>/dev/null; then
  echo "Installing the IDE toolkit (PyQt6)..."
  .venv/bin/pip install --quiet PyQt6 anthropic || exit 1
fi

exec .venv/bin/python -m sparky
