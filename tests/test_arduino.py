# Arduino support: friendly compiler errors, Sparky for Arduino, sketch
# folders, and reading arduino-cli's answers. Compiles for real when
# arduino-cli is on this computer (Arduino IDE 2 counts).
# Run with: python3 tests/test_arduino.py

import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sparky.arduino import errors  # noqa: E402
from sparky.arduino.cli import ArduinoCLI, sketch_folder, size_summary  # noqa: E402
from sparky.arduino.translate import is_arduino_program, to_arduino  # noqa: E402
from sparky.lang import SparkyError, parse, Interpreter, Runtime  # noqa: E402

passed = 0


def check(name, got, want):
    global passed
    assert got == want, f"FAILED: {name}\n  got:  {got!r}\n  want: {want!r}"
    passed += 1
    print(f"  ok - {name}")


# ---------- friendly compiler errors (real gcc messages) ----------
SKETCH = """void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  serial.begin(9600);
}

void loop() {
  digitalWrite(LED_BUILTIN, HIGH)
  delay(500);
  ledState = 3;
  digitalwrite(13, LOW);
}
"""
LOG = """/tmp/x/Blink/Blink.ino: In function 'void setup()':
/tmp/x/Blink/Blink.ino:3:3: error: 'serial' was not declared in this scope
/tmp/x/Blink/Blink.ino:8:3: error: expected ';' before 'delay'
/tmp/x/Blink/Blink.ino:9:3: error: 'ledState' was not declared in this scope
/tmp/x/Blink/Blink.ino:10:3: error: 'digitalwrite' was not declared in this scope
/tmp/x/Blink/Blink.ino:10:3: note: suggested alternative: 'digitalWrite'
"""
problems = errors.explain(LOG, "Blink.ino", SKETCH)
check("errors in line order", [p.line for p in problems], [3, 7, 9, 10])
check("capital letters", problems[0].fix, "Serial.begin(9600);")
check("missing ; points at the line above", (problems[1].line, problems[1].fix),
      (7, "digitalWrite(LED_BUILTIN, HIGH);"))
check("not declared yet", "int ledState = 0;" in problems[2].message, True)
check("digitalwrite -> digitalWrite", problems[3].fix, "digitalWrite(13, LOW);")
check("pretty has You wrote / Try this", "Try this:   Serial.begin(9600);" in problems[0].pretty(), True)
missing = errors.explain("/a/S/S.ino:1:10: fatal error: Servo.h: No such file or directory",
                         "S.ino", "#include <Servo.h>\n")
check("missing library offers an install", (missing[0].library, "isn't installed" in missing[0].message),
      ("Servo", True))
curly = errors.explain("/a/S/S.ino:2:17: error: stray '\\342' in program", "S.ino",
                       'void setup() {\n  Serial.print(“hi”);\n}\n')
check("curly quotes", curly[0].fix, 'Serial.print("hi");')
brace = errors.explain("/a/S/S.ino:4:1: error: expected '}' at end of input", "S.ino",
                       "void setup() {\n\nvoid loop() {\n")
check("missing }", "never got its }" in brace[0].message, True)
check("busy port", "busy" in errors.explain_upload("avrdude: ser_open(): can't open device "
                                                   '"/dev/cu.usbmodem1": Resource busy'), True)
check("board not answering", "didn't answer" in errors.explain_upload(
    "avrdude: stk500_recv(): programmer is not responding"), True)

# ---------- Sparky for Arduino ----------
blink = to_arduino("forever\n  pin 13 on\n  wait 0.5\n  pin 13 off\n  wait 0.5\nend\n")
check("blink setup", "pinMode(13, OUTPUT);" in blink, True)
check("blink loop", "void loop() {\n  digitalWrite(13, HIGH);\n  delay(500);" in blink, True)
song = to_arduino("buzzer 8\nplay note 5 for 0.25\nservo 9 to 90\n")
check("notes and servos", ("tone(sparkyBuzzer, 392, 250);" in song, "#include <Servo.h>" in song,
                           "servo9.attach(9);" in song), (True, True, True))
sensor = to_arduino("set v to read pin A0\nset b to read pin 2\nsay v\n")
check("reading pins", ("analogRead(A0)" in sensor, "digitalRead(2)" in sensor,
                       "pinMode(2, INPUT);" in sensor, "Serial.begin(9600);" in sensor),
      (True, True, True, True))
try:
    to_arduino("move 10\n")
    check("stage commands explain", False, True)
except SparkyError as err:
    check("stage commands explain", "works on the stage, not on an Arduino" in err.message, True)
check("spot board programs", (is_arduino_program("pin 13 on\n"),
                              is_arduino_program('say "hi"\nmove 10\n')), (True, False))


class Quiet(Runtime):
    pass


try:
    for _ in Interpreter(parse("pin 13 on\n"), Quiet()).run():
        pass
    check("pin on the stage explains", False, True)
except SparkyError as err:
    check("pin on the stage explains", "works on an Arduino board" in err.message, True)

# ---------- sketch folders ----------
scratch = Path(tempfile.mkdtemp())
folder, ino = sketch_folder(Path("/Users/kid/Desktop/my blink.ino"), "void setup(){}", scratch)
check("odd names get a matching folder", (folder.name, ino.name), ("my_blink", "my_blink.ino"))
good = scratch / "Blink" / "Blink.ino"
good.parent.mkdir()
good.write_text("x")
check("a proper sketch stays put", sketch_folder(good, "x", scratch), (good.parent, good))
check("program size", size_summary("Sketch uses 884 bytes (2%) of program storage space. "
                                   "Maximum is 32256 bytes.\nGlobal variables use 9 bytes (0%) of"),
      "Uses 884 bytes (2% of the board's space) and 9 bytes of memory (0%).")

# ---------- reading arduino-cli's answers (a pretend arduino-cli) ----------
fake_dir = Path(tempfile.mkdtemp())
answers = {
    "board list": {"detected_ports": [
        {"port": {"address": "/dev/cu.Bluetooth-Incoming-Port", "label": "bt", "protocol": "serial"}},
        {"port": {"address": "/dev/cu.usbmodem1101", "label": "usbmodem1101", "protocol": "serial"},
         "matching_boards": [{"name": "Arduino Uno", "fqbn": "arduino:avr:uno"}]}]},
    "board listall": {"boards": [{"name": "Arduino Yún", "fqbn": "arduino:avr:yun"},
                                 {"name": "Arduino Uno", "fqbn": "arduino:avr:uno"}]},
    "lib search": {"libraries": [{"name": "Servo", "latest": {"version": "1.2.2",
                                                              "sentence": "Servo motors."}}]},
}
script = fake_dir / "arduino-cli"
(fake_dir / "answers.json").write_text(json.dumps(answers))
script.write_text("#!/usr/bin/env python3\n"
                  "import json, sys, pathlib\n"
                  "answers = json.loads((pathlib.Path(__file__).parent / 'answers.json').read_text())\n"
                  "args = [a for a in sys.argv[1:] if not a.startswith('--') and a != 'json']\n"
                  "print(json.dumps(answers.get(' '.join(args[:2]), {})))\n")
script.chmod(script.stat().st_mode | stat.S_IEXEC)
if os.name != "nt":
    fake = ArduinoCLI(script)
    ports = fake.ports()
    check("boards first, Bluetooth last", [p.title() for p in ports],
          ["Arduino Uno on usbmodem1101", "Bluetooth-Incoming-Port"])
    check("favorite boards first", [b.fqbn for b in fake.boards()], ["arduino:avr:uno", "arduino:avr:yun"])
    check("library search", fake.lib_search("servo")[0]["version"], "1.2.2")

# ---------- compile for real (when arduino-cli is here) ----------
cli = ArduinoCLI.find()
if cli is None or os.environ.get("SPARKY_SKIP_ARDUINO_COMPILE"):
    print("  (skipped real compiles: no arduino-cli on this computer)")
else:
    for name, src in {
        "blink": "forever\n  pin 13 on\n  wait 0.5\n  pin 13 off\n  wait 0.5\nend\n",
        "everything": 'buzzer 8\nteach double n\n  give back n * 2\nend\nset total to 0\n'
                      'repeat 5 times\n  change total by double(3)\nend\n'
                      'say "Total {total}"\nsay total mod 4 > 1\nservo 9 to 45\n'
                      'for i from 1 to 8\n  play note i for 0.1\nend\n'
                      'forever\n  set light to read pin A0\n  pin 9 to light / 4\n'
                      '  if light > 500 then\n    pin 13 on\n  else\n    pin 13 off\n  end\n'
                      '  wait 0.1\nend\n',
    }.items():
        folder, _ = sketch_folder(None, to_arduino(src), Path(tempfile.mkdtemp()) / name)
        result = subprocess.run(cli.compile_command(folder, "arduino:avr:uno"),
                                capture_output=True, text=True)
        check(f"{name} compiles for an Uno", (result.returncode, result.stderr[-300:]) if result.returncode
              else 0, 0)

    examples = sorted((Path(__file__).resolve().parent.parent / "examples" / "arduino").iterdir())
    for path in examples:
        if path.suffix not in (".ino", ".spark"):
            continue
        source = path.read_text(encoding="utf-8")
        code = to_arduino(source) if path.suffix == ".spark" else source
        folder, _ = sketch_folder(Path(path.stem + ".ino"), code, Path(tempfile.mkdtemp()))
        result = subprocess.run(cli.compile_command(folder, "arduino:avr:uno"),
                                capture_output=True, text=True)
        check(f"example {path.name} compiles", (result.returncode, result.stderr[-400:])
              if result.returncode else 0, 0)

print(f"\nAll {passed} Arduino checks passed!")
