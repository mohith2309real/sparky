# Entry point for the standalone Mac app (PyInstaller builds this).
# sparky_boot picks the newest installed update pack, then runs Sparky:
#   Sparky                  -> the IDE
#   Sparky run file.spark   -> terminal runner
#   Sparky play file.spark  -> the player window

import sparky_boot

if __name__ == "__main__":
    sparky_boot.main()
