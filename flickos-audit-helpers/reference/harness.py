#!/usr/bin/python3
"""Run a FlickOS privileged helper's main() as fake root, safely.

Reference answer for exercise 5 of the helper audit tutorial. Use it as a
library (attack.py and fuzz.py import it):

    import harness
    h = harness.Harness("/path/to/control-helper")
    result = h.run(["keyboard", "pc105", "us", "", ""])
    print(result.code, result.commands, result.changed)

What it does:
  * loads the helper as a Python module (it never runs as a program);
  * points every absolute path constant the helper writes to (/etc, /var,
    /run) into a throwaway "fake root", copying the real file in first so
    reads behave as on this computer;
  * replaces subprocess.run with a recorder: nothing is executed, the
    argv and standard input are kept, and a canned answer is returned;
  * pretends to be root (os.geteuid() == 0) and sets PKEXEC_UID;
  * installs an audit hook that refuses, for the rest of this process, any
    write outside the fake root and any program start that didn't go
    through the recorder. If the harness has a hole, the hook stops it
    before your real system is touched.

Lookups (pwd, grp, /proc, evdev.lst) read the real system; they only read.
"""

import contextlib
import importlib.machinery
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
from unittest import mock

# Constants under these folders are moved into the fake root. Everything else
# (/usr/share/X11/xkb, /proc, programs in /usr/sbin) stays real: read-only use.
REDIRECT = ("/etc/", "/var/", "/run/")
TEMP = tempfile.gettempdir()

_allowed_roots = []         # fake roots of this process; the hook allows writes there
_inside_recorder = [False]


def _audit(event, args):
    """Refuse writes outside a fake root and programs not started by the recorder."""
    if event == "open":
        path, mode, flags = args
        writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or \
                  (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if writing and isinstance(path, (str, bytes)):
            _check_path(os.fsdecode(path), event)
    elif event in ("os.remove", "os.rmdir", "os.mkdir", "os.chmod", "os.chown", "os.truncate"):
        # The last argument is dir_fd: shutil.rmtree passes names relative to it.
        if args and isinstance(args[0], (str, bytes, os.PathLike)):
            _check_path(_absolute(args[0], args[-1] if event != "os.truncate" else None), event)
    elif event in ("os.rename", "os.link"):
        _check_path(_absolute(args[0], args[2]), event)
        _check_path(_absolute(args[1], args[3]), event)
    elif event == "os.symlink":
        _check_path(_absolute(args[1], args[2]), event)
    elif event in ("subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork"):
        raise PermissionError(f"harness: blocked {event} {args!r:.200}: the helper tried to run a program "
                              "without going through the recorder")


def _absolute(path, dir_fd=None):
    path = os.fsdecode(path)
    if not os.path.isabs(path) and isinstance(dir_fd, int) and dir_fd >= 0:
        return os.path.join(os.readlink(f"/proc/self/fd/{dir_fd}"), path)
    return path


def _check_path(path, event):
    path = os.path.realpath(path)
    if any(path == root or path.startswith(root + os.sep) for root in _allowed_roots):
        return
    # Python's own .pyc files, and the harness making and deleting fake roots.
    if path.endswith(".pyc") or path.startswith(os.path.realpath(TEMP) + os.sep + "harness-root-"):
        return
    raise PermissionError(f"harness: blocked {event} on {path}: outside the fake root")


sys.addaudithook(_audit)


class Result:
    def __init__(self, code, stdout, stderr, commands, changed, crashed, before=None):
        self.before = before or {}      # {real path: text before main(), or None}
        self.code = code                # main()'s return value (None if it crashed)
        self.stdout = stdout
        self.stderr = stderr
        self.commands = commands        # [(argv list, stdin text or None)]
        self.changed = changed          # {real path: new text, or None if deleted}
        self.crashed = crashed          # traceback text of an exception main() didn't catch

    def __repr__(self):
        return (f"Result(code={self.code}, commands={self.commands}, changed={list(self.changed)}, "
                f"crashed={bool(self.crashed)})")


def default_responder(argv, stdin):
    """Canned answers for the programs control-helper reads output from."""
    name = os.path.basename(argv[0])
    if name == "dpkg" and "--print-architecture" in argv:
        return 0, "amd64\n", ""
    return 0, "", ""


class Harness:
    def __init__(self, helper_path):
        self.helper_path = os.path.abspath(helper_path)
        name = os.path.basename(helper_path).replace("-", "_")
        loader = importlib.machinery.SourceFileLoader(name, self.helper_path)
        self.module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader))
        loader.exec_module(self.module)
        self.path_constants = {key: value for key, value in vars(self.module).items()
                               if key.isupper() and isinstance(value, str) and value.startswith(REDIRECT)}

    def run(self, argv, stdin="", pkexec_uid=None, responder=default_responder, setup=None, patches=()):
        """Run main(argv) once in a fresh fake root.

        pkexec_uid: PKEXEC_UID to set (default: your own uid); "" leaves it unset.
        responder(argv, stdin) -> (returncode, stdout, stderr) answers recorded programs.
        setup(fake) is called with a function mapping a real path to its fake one,
            before main(), to put crafted files in place.
        patches: extra (attribute name, value) pairs set on the module."""
        fake_root = os.path.realpath(tempfile.mkdtemp(prefix="harness-root-"))
        _allowed_roots.append(fake_root)
        try:
            return self._run(fake_root, argv, stdin, pkexec_uid, responder, setup, patches)
        finally:
            shutil.rmtree(fake_root, ignore_errors=True)
            _allowed_roots.remove(fake_root)

    def _run(self, fake_root, argv, stdin, pkexec_uid, responder, setup, patches):
        def fake(path):
            return os.path.join(fake_root, path.lstrip("/"))

        before = {}
        for real in self.path_constants.values():
            target = fake(real)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with contextlib.suppress(OSError):
                if os.path.isfile(real):
                    shutil.copyfile(real, target)
            before[real] = _read(target)
        if setup:
            setup(fake)
            for real in self.path_constants.values():
                before[real] = _read(fake(real))

        commands = []

        def recorder(command, *args, **kwargs):
            argv_list = [os.fsdecode(a) for a in (command if isinstance(command, (list, tuple)) else [command])]
            given = kwargs.get("input")
            commands.append((argv_list, given))
            code, out, err = responder(argv_list, given)
            if kwargs.get("check") and code:
                raise subprocess.CalledProcessError(code, argv_list, out, err)
            if not kwargs.get("text") and not kwargs.get("encoding") and not kwargs.get("universal_newlines"):
                out, err = out.encode(), err.encode()
            return subprocess.CompletedProcess(argv_list, code, out, err)

        env = {"PKEXEC_UID": str(os.getuid()) if pkexec_uid is None else pkexec_uid}
        stdout, stderr = io.StringIO(), io.StringIO()
        crashed = None
        code = None
        with contextlib.ExitStack() as stack:
            for key, real in self.path_constants.items():
                stack.enter_context(mock.patch.object(self.module, key, fake(real)))
            for key, value in patches:
                stack.enter_context(mock.patch.object(self.module, key, value))
            stack.enter_context(mock.patch.object(self.module.os, "geteuid", return_value=0))
            stack.enter_context(mock.patch.dict(os.environ, env))
            if pkexec_uid == "":
                os.environ.pop("PKEXEC_UID", None)
            stack.enter_context(mock.patch.object(subprocess, "run", recorder))
            stack.enter_context(mock.patch("sys.stdin", io.StringIO(stdin)))
            stack.enter_context(contextlib.redirect_stdout(stdout))
            stack.enter_context(contextlib.redirect_stderr(stderr))
            try:
                code = self.module.main(list(argv))
            except SystemExit as error:
                code = error.code
            except BaseException:
                crashed = traceback.format_exc()

        changed = {}
        for real in self.path_constants.values():
            after = _read(fake(real))
            if after != before[real]:
                changed[real] = after
        return Result(code, stdout.getvalue(), stderr.getvalue(), commands, changed, crashed,
                      {path: before[path] for path in changed})


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def self_test(helper_path):
    """Prove the guard works: a write outside the fake root and a program
    started behind the recorder's back must both be refused."""
    h = Harness(helper_path)
    canary = os.path.expanduser("~/harness-canary")
    write = h.run(["keyboard", "pc105", "us", "", ""], patches=[("KEYBOARD_DEFAULTS", canary)])
    print("write outside the fake root:", "BLOCKED" if "harness: blocked" in write.stderr + (write.crashed or "")
          and not os.path.exists(canary) else "NOT BLOCKED, fix the harness")

    def start_program(_fake):
        subprocess.Popen(["true"])
    try:
        h.run(["firewall-on"], setup=start_program)
        print("program behind the recorder's back: NOT BLOCKED, fix the harness")
    except PermissionError as error:
        print("program behind the recorder's back:", "BLOCKED" if "harness: blocked" in str(error) else error)


if __name__ == "__main__":
    # Smoke test: python3 harness.py HELPER VERB ARGS...   or   harness.py HELPER --self-test
    if len(sys.argv) == 3 and sys.argv[2] == "--self-test":
        self_test(sys.argv[1])
        sys.exit(0)
    if len(sys.argv) < 3:
        print("usage: harness.py HELPER VERB [ARGS...] | HELPER --self-test", file=sys.stderr)
        sys.exit(2)
    result = Harness(sys.argv[1]).run(sys.argv[2:])
    print("exit code:", result.code)
    print("stdout:", result.stdout.rstrip())
    print("stderr:", result.stderr.rstrip())
    for argv, given in result.commands:
        print("would run:", argv, "stdin:" if given is not None else "", repr(given) if given is not None else "")
    for path, text in result.changed.items():
        print(f"would change {path}:")
        print("    " + (text or "(deleted)").rstrip().replace("\n", "\n    "))
    if result.crashed:
        print("CRASHED:\n" + result.crashed)
