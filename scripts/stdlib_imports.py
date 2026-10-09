# Print --hidden-import flags for the whole standard library (minus a few
# big or useless parts) plus the Qt modules Sparky 3 uses. Bundling all of it
# means later code-pack updates can use any of them without a full update.

import sys

SKIP = {"tkinter", "turtle", "turtledemo", "idlelib", "test", "lib2to3", "ensurepip", "venv",
        "pydoc_data", "distutils", "msilib", "nt", "winreg", "winsound", "_winapi", "msvcrt",
        "_msi", "_overlapped", "_tkinter", "this", "antigravity", "__phello__", "_testcapi",
        "_testinternalcapi", "_testbuffer", "_testimportmultiple", "_testmultiphase",
        "_xxtestfuzz", "xxlimited", "xxsubtype", "_ctypes_test", "_testclinic", "_testsinglephase",
        "_testlimitedcapi", "_testexternalinspection", "_testconsole", "_scproxy", "_android_support",
        "_ios_support", "_apple_support"}
QT = ["PyQt6.QtSvg", "PyQt6.QtNetwork", "PyQt6.QtMultimedia", "PyQt6.QtTextToSpeech",
      "PyQt6.QtPrintSupport"]
names = sorted(n for n in sys.stdlib_module_names if n not in SKIP and not n.startswith("_test"))
print(" ".join(f"--hidden-import {n}" for n in names + QT))
