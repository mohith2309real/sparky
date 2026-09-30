# Entry points:
#   python3 -m sparky                  -> open the Sparky IDE
#   python3 -m sparky run file.spark   -> run a program in the terminal
#   python3 -m sparky play file.spark  -> open a program in the player
#                                         (stage + console, no editor)

import sys

from . import __version__


def main():
    args = sys.argv[1:]
    if args and args[0] == "selfcheck":
        import platform
        report = [f"Sparky {__version__}", f"Python {platform.python_version()}"]
        from .lang import run_console
        run_console('say "language ok"')
        try:
            from PyQt6.QtCore import QT_VERSION_STR
            report.append(f"Qt {QT_VERSION_STR}")
        except ImportError as err:
            report.append(f"Qt missing: {err}")
        try:
            import anthropic
            report.append(f"anthropic {anthropic.__version__}")
        except ImportError as err:
            report.append(f"anthropic missing: {err}")
        try:
            from .ide.vscode import ssl_context
            ssl_context()
            report.append("https ok")
        except Exception as err:
            report.append(f"https problem: {err}")
        import os
        url = os.environ.get("SPARKY_SELFCHECK_AI_URL")
        if url:   # a stand-in server proves the Claude connection works end to end
            from .ide.ai import stream_anthropic
            got = []
            stream_anthropic({"name": "check", "kind": "anthropic", "base_url": url,
                              "key": "check", "model": "claude-opus-5-5"},
                             "check", [{"role": "user", "content": "hi"}],
                             got.append, lambda: False)
            report.append(f"claude stream: {''.join(got)!r}")
        print(" | ".join(report))
        return
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
