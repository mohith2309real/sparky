# Entry point for the standalone Sparky app (PyInstaller builds this).
# Same behavior as `python -m sparky`:
#   Sparky                  -> the IDE
#   Sparky run file.spark   -> terminal runner
#   Sparky play file.spark  -> the player window

from sparky.__main__ import main

if __name__ == "__main__":
    main()
