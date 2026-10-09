# Entry points:
#   python3 -m sparky                  -> open the Sparky IDE
#   python3 -m sparky run file.spark   -> run a program in the terminal
#   python3 -m sparky play file.spark  -> open a program in the player
#                                         (stage + console, no editor)

import sys

from . import __version__


def update_selfcheck():
    """Prove the update system works. With SPARKY_SELFCHECK_UPDATE_URL it also
    fetches, verifies and installs the newest code pack, exactly like the app."""
    import os
    from .update import download, ed25519, install, manifest, where
    vector = ed25519.verify(
        bytes.fromhex("3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c"),
        bytes.fromhex("72"),
        bytes.fromhex("92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da"
                      "085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"))
    boot = sys.modules.get("sparky_boot")
    parts = ["signatures ok" if vector else "SIGNATURES BROKEN",
             f"running {'pack ' + boot.running_pack if boot and boot.running_pack else 'built-in code'}"]
    base = os.environ.get("SPARKY_SELFCHECK_UPDATE_URL")
    if base and boot is not None:
        channel = os.environ.get("SPARKY_SELFCHECK_CHANNEL", "beta")
        agent = f"Sparky/{__version__} selfcheck"
        data = manifest.read(download.fetch_bytes(f"{base}/{channel}.json", agent), channel)
        update = manifest.choose(data, __version__, boot.RUNTIME, where.platform_id())
        if update is None:
            parts.append(f"update: {__version__} is the newest")
        elif update.kind == "full":
            name = update.url.rsplit("/", 1)[-1]
            path = download.download(update.url, where.updates_dir() / "downloads" / name,
                                     update.sha256, update.size, agent)
            install.launch_detached(install.stage_full(path, update.artifact))
            parts.append(f"staged full update {update.version}")
        elif update.kind != "pack":
            parts.append(f"update: {update.version} needs a {update.kind} update")
        else:
            path = download.download(update.url, where.updates_dir() / "downloads" / "pack.zip",
                                     update.sha256, update.size, agent)
            install.install_pack(path, update.version, boot.RUNTIME, update.sha256)
            parts.append(f"installed pack {update.version}")
    return " | ".join(parts)


def ui_selfcheck(out):
    """Open the real IDE (offscreen if there's no screen), run the welcome
    program, save a screenshot, and report what happened."""
    import os
    import tempfile
    import time
    os.environ.setdefault("SPARKY_NEW_WINDOW", "1")
    os.environ.setdefault("SPARKY_SETTINGS_FILE", os.path.join(tempfile.mkdtemp(), "s.ini"))
    from PyQt6.QtCore import QT_VERSION_STR
    from PyQt6.QtWidgets import QApplication
    from .ide import app as appmod
    from .ide.theme import load_fonts
    from .paths import ASSETS_DIR, INSTALLED, USER_DIR
    qt = QApplication(sys.argv[:1])
    load_fonts(ASSETS_DIR)
    prefs = appmod.prefs.open_settings()
    prefs.setValue("first_run_done", True)
    prefs.setValue("start_home", False)
    window = appmod.MainWindow()
    window.resize(1280, 800)
    window.show()
    window.speed.setValue(10)
    window.run_program()
    end = time.time() + 20
    while (window.is_running() or time.time() < end - 18) and time.time() < end:
        qt.processEvents()
        time.sleep(0.02)
    for _ in range(20):
        qt.processEvents()
        time.sleep(0.01)
    window.grab().save(out)
    with window.stage_model.lock:
        lines = len(window.stage_model.segments)
    said = window.console.toPlainText().split("\n")[0]
    print(f"Qt {QT_VERSION_STR} | Sparky {__version__} | installed: {INSTALLED} | "
          f"files: {USER_DIR} | console: {said!r} | lines drawn: {lines} | "
          f"extensions: {[e.name for e in window.extension_manager.extensions]} | screenshot: {out}")
    boot = sys.modules.get("sparky_boot")
    if boot is not None:
        boot.mark_good()
    window.close()


def arduino_selfcheck():
    """Is Arduino support working here? Finds arduino-cli and compiles Blink
    (written in Sparky words) for an Arduino Uno when that board is installed."""
    import subprocess
    import tempfile
    from pathlib import Path
    from .arduino.cli import ArduinoCLI, sketch_folder, size_summary
    from .arduino.translate import to_arduino
    cli = ArduinoCLI.find()
    if cli is None:
        return "arduino: no arduino-cli here (Sparky can download it from the Arduino panel)"
    parts = [f"arduino-cli {cli.version()} from {cli.where()}"]
    code = to_arduino("forever\n  pin 13 on\n  wait 0.5\n  pin 13 off\n  wait 0.5\nend\n")
    folder, _ = sketch_folder(Path("blink.ino"), code, tempfile.mkdtemp())
    result = subprocess.run(cli.compile_command(folder, "arduino:avr:uno"), capture_output=True,
                            text=True, timeout=300)
    if result.returncode == 0:
        parts.append(f"Sparky blink compiles for Uno: {size_summary(result.stdout)}")
    else:
        parts.append("Uno boards aren't installed here (Boards → Arduino AVR)" if "platform not installed" in
                     (result.stdout + result.stderr).lower() else "compile FAILED")
    return " | ".join(parts)


def main():
    args = sys.argv[1:]
    if args[:2] == ["selfcheck", "arduino"]:
        print(arduino_selfcheck())
        return
    if args[:2] == ["selfcheck", "ui"]:
        ui_selfcheck(args[2] if len(args) > 2 else "sparky-selfcheck.png")
        return
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
        report.append(update_selfcheck())
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
        boot = sys.modules.get("sparky_boot")
        if boot is not None:
            boot.mark_good()
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
            from pathlib import Path
            run_console(source, base_dir=Path(args[1]).resolve().parent)
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
