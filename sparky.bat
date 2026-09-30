@echo off
rem Double-click me on Windows to open the Sparky IDE!
rem First run sets up its own Python environment (needs Python 3 installed).
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo First-time setup: preparing Sparky's environment...
  py -3 -m venv .venv || python -m venv .venv || goto :fail
)

.venv\Scripts\python -c "import PyQt6, anthropic" 2>nul
if errorlevel 1 (
  echo Installing the IDE toolkit ^(PyQt6^)...
  .venv\Scripts\pip install --quiet PyQt6 anthropic || goto :fail
)

.venv\Scripts\python -m sparky
exit /b

:fail
echo Something went wrong. Is Python 3 installed? Get it at python.org
pause
