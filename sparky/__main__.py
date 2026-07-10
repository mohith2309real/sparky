# Entry points:
#   python3 -m sparky                  -> open the Sparky IDE
#   python3 -m sparky run file.spark   -> run a program in the terminal
#   python3 -m sparky play file.spark  -> open a program in the player
#                                         (stage + console, no editor)

import sys


def main():
    args = sys.argv[1:]
    if args and args[0] == "play":
        if len(args) < 2:
            print("Usage: python3 -m sparky play <file.spark>")
            sys.exit(1)
        from .ide.player import play_file
        play_file(args[1])
        return
    if args and args[0] == "run":
        if len(args) < 2:
            print("Usage: python3 -m sparky run <file.spark>")
            sys.exit(1)
        from .lang import run_console, SparkyError
        try:
            with open(args[1], encoding="utf-8") as f:
                source = f.read()
        except OSError as err:
            print(f"Couldn't open {args[1]}: {err}")
            sys.exit(1)
        try:
            run_console(source)
        except SparkyError as err:
            print(err.pretty())
            sys.exit(1)
        except KeyboardInterrupt:
            print("\nStopped.")
        return

    try:
        from .ide.app import main as ide_main
    except ImportError:
        print("The Sparky IDE needs PyQt6, which isn't installed for this "
              "Python.\nEasiest fix: double-click Sparky.command in the "
              "sparky folder —\nit sets everything up and opens the IDE.")
        sys.exit(1)
    ide_main()


if __name__ == "__main__":
    main()
