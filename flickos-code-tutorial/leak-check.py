#!/usr/bin/env python3
"""leak-check.py: run a package's unit tests and report everything they touch
outside their own test folders: files opened or listed on the build host
(/etc/xdg/flickos, ~/.config, /proc, …) and programs started.

    ./leak-check.py PACKAGE_FOLDER
    ./leak-check.py $FLICKOS/packages/flickos-welcome

Why: the tests run while the package builds, and on your computer that is a
live FlickOS desktop. A test that reads the real /etc/xdg/flickos/NAME.conf
passes in CI (which has no such file) and fails, or does something, on yours.

How: Python's audit hooks (sys.addaudithook) see every open(), os.listdir()
and subprocess.Popen() the tests make. Each is labelled with the test that
made it. Allowed without a report: the package folder and the folder it
is in (a test may compare it with a neighbouring package), the temp folder,
/nonexistent, Python's own library folders and /dev/null. Programs a test
starts are listed but not followed (a test that starts Python itself, to try
the program in a fresh process, is left out): check what they are given.

Exit codes: 0 nothing touched the host, 1 something did (or a test failed),
2 usage error.
"""
import os
import sys
import sysconfig
import tempfile
import unittest

if len(sys.argv) != 2 or not os.path.isdir(os.path.join(sys.argv[1], "tests")):
    print(__doc__.split("\n\nWhy:")[0], file=sys.stderr)
    sys.exit(2)

PACKAGE = os.path.realpath(sys.argv[1])
# The folder around the package too: in the repo that is packages/, and a
# test comparing two packages' files (PKG-8) reads its neighbour on purpose.
# /nonexistent is where tests point a path that must not exist.
ALLOWED = {PACKAGE, os.path.dirname(PACKAGE), os.path.realpath(tempfile.gettempdir()), "/dev/null",
           "/nonexistent", "/usr/lib/python3/dist-packages", "/usr/lib/python3.13", "/usr/lib/locale",
           "/usr/share/locale"}
ALLOWED |= {os.path.realpath(sysconfig.get_paths()[key]) for key in ("stdlib", "platstdlib", "purelib", "platlib")}
current = ["(loading the tests)"]
touched = []                                    # (test, what, path)


def allowed(path):
    path = os.path.realpath(path)
    return any(path == top or path.startswith(top + os.sep) for top in ALLOWED)


def hook(event, args):
    if event in ("open", "os.listdir", "os.scandir") and args and isinstance(args[0], (str, bytes)):
        path = os.fsdecode(args[0])
        if not allowed(path):
            touched.append((current[0], "reads" if event == "open" else "lists", path))
    elif event == "subprocess.Popen":
        executable, command = args[0], args[1]
        if os.path.realpath(os.fsdecode(executable or command[0])) != os.path.realpath(sys.executable):
            touched.append((current[0], "runs", " ".join(map(os.fsdecode, command))))


_run = unittest.TestCase.run


def run(self, result=None):
    current[0] = self.id()
    try:
        return _run(self, result)
    finally:
        current[0] = "(between tests)"


unittest.TestCase.run = run
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True
os.chdir(PACKAGE)                               # as dh_auto_test runs them
sys.addaudithook(hook)
suite = unittest.defaultTestLoader.discover("tests", top_level_dir="tests")
result = unittest.TextTestRunner(verbosity=0, stream=sys.stderr).run(suite)

seen = set()
for test, what, path in touched:
    if (test, what, path) not in seen:
        seen.add((test, what, path))
        print(f"{test}\n    {what} {path}")
print(f"\n{len(seen)} host file(s)/program(s) touched" if seen else "\nnothing outside the test folders was touched")
sys.exit(1 if seen or not result.wasSuccessful() else 0)
