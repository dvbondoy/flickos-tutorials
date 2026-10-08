#!/usr/bin/python3
"""Hand-written hostile inputs for control-helper, run through the harness.

Reference answer for exercise 6. Every case says what a safe helper must do:

  refuse   exit code != 0, no program started, no file changed
  accept   exit code 0, and the case's check() holds on what it would do

A case whose expectation fails is printed as FINDING. Usage:

    python3 attack.py [HELPER]       (default: $FLICKOS/packages/flickos-control/...)
"""

import os
import pwd
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness  # noqa: E402

FLICKOS = os.environ.get("FLICKOS", os.path.expanduser("~/Documents/Projects/FlickOS"))
DEFAULT_HELPER = os.path.join(FLICKOS, "packages/flickos-control/usr/libexec/flickos/control-helper")
ME = os.getuid()
ME_NAME = pwd.getpwuid(ME).pw_name      # a regular account that exists: yours


def argv_of(result, program):
    return [argv for argv, _ in result.commands if os.path.basename(argv[0]) == program]


def stdin_of(result, program):
    return [given for argv, given in result.commands if os.path.basename(argv[0]) == program]


# --- checks for accepted inputs -------------------------------------------------

SAFE_KEYBOARD_LINE = re.compile(r'^XKB(MODEL|LAYOUT|VARIANT|OPTIONS)="[A-Za-z0-9_:(),.+-]*"$')


def keyboard_file_is_inert(result):
    """Every XKB line the helper wrote is a plain quoted word list: when a root
    shell sources the file (setupcon, console-setup), nothing runs."""
    text = result.changed.get("/etc/default/keyboard") or ""
    bad = [line for line in text.splitlines() if line.startswith("XKB") and not SAFE_KEYBOARD_LINE.match(line)]
    return not bad, f"unsafe lines: {bad}"


def one_chpasswd_line(name):
    def check(result):
        given = stdin_of(result, "chpasswd")
        ok = len(given) == 1 and given[0].count("\n") == 1 and given[0].startswith(f"{name}:")
        return ok, f"chpasswd stdin: {given!r}"
    return check


def comment_is_a_value(result):
    """adduser's --comment takes an OPTIONAL value (Getopt::Long 'comment:s'):
    a full name starting with '-' would be read as another option."""
    for argv in argv_of(result, "adduser"):
        i = argv.index("--comment") if "--comment" in argv else -1
        if i >= 0 and i + 1 < len(argv) and argv[i + 1].startswith("-"):
            return False, f"adduser would see an option, not a name: {argv}"
    return True, ""


def no_option_like_package(result):
    """Package names from apt's log must never reach apt-get as options."""
    for argv in argv_of(result, "apt-get"):
        words = argv[argv.index("remove") + 1:] if "remove" in argv else \
            argv[argv.index("install") + 1:] if "install" in argv else []
        if any(w.startswith("-") for w in words):
            return False, f"apt-get would see an option: {argv}"
    return True, ""


def both(*checks):
    def check(result):
        for one in checks:
            ok, why = one(result)
            if not ok:
                return ok, why
        return True, ""
    return check


# --- a crafted apt log (packages-undo) -----------------------------------------

EVIL_LOG = """
Start-Date: 2030-01-01  10:00:00
Commandline: apt-get install hello
Install: hello:amd64 (2.10-3), -oAPT::Get::Show-Versions=1:amd64 (1.0)
End-Date: 2030-01-01  10:00:05
"""


def evil_apt_log(fake):
    with open(fake("/var/log/apt/history.log"), "w") as f:
        f.write(EVIL_LOG)


def apt_responder(argv, stdin):
    name = os.path.basename(argv[0])
    if name == "dpkg":
        return 0, "amd64\n", ""
    if name == "dpkg-query" and "${Depends}" not in argv:
        packages = argv[argv.index("-f") + 2:]
        return 0, "".join(f"{p}\tinstalled\n" for p in packages), ""
    if name == "apt-get" and "-s" in argv:
        words = argv[argv.index("remove") + 1:] if "remove" in argv else []
        return 0, "".join(f"Remv {w} [1.0]\n" for w in words), ""
    return 0, "", ""


# --- the cases ----------------------------------------------------------------------
# (name, argv, stdin, expectation, check or None, extra run() options)

CASES = [
    # keyboard: /etc/default/keyboard is sourced by root shells.
    ("keyboard: valid", ["keyboard", "pc105", "us,de", ",nodeadkeys", "grp:alt_shift_toggle"], "",
     "accept", keyboard_file_is_inert, {}),
    ("keyboard: quote + command", ["keyboard", "pc105", 'us";touch /tmp/pwned;"', "", ""], "", "refuse", None, {}),
    ("keyboard: $(command)", ["keyboard", "$(id)", "us", "", ""], "", "refuse", None, {}),
    ("keyboard: newline adds a line", ["keyboard", "pc105", "us\nXKBMODEL=evil", "", ""], "", "refuse", None, {}),
    ("keyboard: empty list item", ["keyboard", "pc105", "us,", "", ""], "", "refuse", None, {}),
    ("keyboard: option of another layout", ["keyboard", "pc105", "us", "nodeadkeys", ""], "", "refuse", None, {}),

    # user-add: name, full name, password.
    ("user-add: valid", ["user-add", "ann", "Ann Lee", "no"], "s3cret:with:colons\n",
     "accept", both(one_chpasswd_line("ann"), comment_is_a_value), {}),
    ("user-add: name starts with -", ["user-add", "-ann", "Ann", "no"], "pw\n", "refuse", None, {}),
    ("user-add: name root", ["user-add", "root", "Root", "no"], "pw\n", "refuse", None, {}),
    ("user-add: uppercase name", ["user-add", "Ann", "Ann", "no"], "pw\n", "refuse", None, {}),
    ("user-add: name with newline", ["user-add", "ann\nroot", "Ann", "no"], "pw\n", "refuse", None, {}),
    ("user-add: full name with :", ["user-add", "ann", "Ann:0:0", "no"], "pw\n", "refuse", None, {}),
    ("user-add: full name --uid=0", ["user-add", "ann", "--uid=0", "no"], "pw\n", "refuse", None, {}),
    ("user-add: full name --system", ["user-add", "ann", "--system", "yes"], "pw\n", "refuse", None, {}),
    ("user-add: full name --add-extra-groups", ["user-add", "ann", "--add-extra-groups", "no"], "pw\n",
     "refuse", None, {}),
    ("user-add: password with newline", ["user-add", "ann", "Ann", "no"], "pw\nroot:owned\n",
     "accept", one_chpasswd_line("ann"), {}),
    ("user-add: no password", ["user-add", "ann", "Ann", "no"], "", "refuse", None, {}),
    ("user-add: admin maybe", ["user-add", "ann", "Ann", "maybe"], "pw\n", "refuse", None, {}),

    # user-password / user-admin: only regular accounts.
    ("user-password: root", ["user-password", "root"], "pw\n", "refuse", None, {}),
    ("user-password: carriage return", ["user-password", ME_NAME], "pw\rx\n", "refuse", None, {}),
    ("user-admin: root", ["user-admin", "root", "no"], "", "refuse", None, {}),
    ("user-admin: option as name", ["user-admin", "-a", "yes"], "", "refuse", None, {}),
    ("user-remove: option as files", ["user-remove", "nobody", "--force"], "", "refuse", None, {}),

    # autologin: only the caller, from PKEXEC_UID.
    ("autologin-on: no PKEXEC_UID", ["autologin-on"], "", "refuse", None, {"pkexec_uid": ""}),
    ("autologin-on: root caller", ["autologin-on"], "", "refuse", None, {"pkexec_uid": "0"}),
    ("autologin-on: uid with space", ["autologin-on"], "", "refuse", None, {"pkexec_uid": f"{ME} "}),
    ("autologin-on: a name argument", ["autologin-on", "root"], "", "refuse", None, {}),

    # Fixed-choice verbs.
    ("power: injected line", ["power", "lid", "suspend\nKillUserProcesses=yes"], "", "refuse", None, {}),
    ("power: unknown setting", ["power", "HandlePowerKey", "ignore"], "", "refuse", None, {}),
    ("updates: injected value", ["updates", "scope", 'all";\nAPT::X "1'], "", "refuse", None, {}),
    ("firewall-phones: extra word", ["firewall-phones", "on", "--dry-run"], "", "refuse", None, {}),
    ("firefox-memory: other value", ["firefox-memory", "maybe"], "", "refuse", None, {}),
    ("locale-add: path", ["locale-add", "../../../etc/passwd"], "", "refuse", None, {}),
    ("locale-add: newline", ["locale-add", "de_DE.UTF-8\nroot UTF-8"], "", "refuse", None, {}),

    # Software changes.
    ("packages-undo: id with command", ["packages-undo", "2030-01-01T10:00:00;id"], "", "refuse", None, {}),
    ("packages-undo: option-like package in the log", ["packages-undo", "2030-01-01T10:00:00"], "",
     "accept", no_option_like_package, {"setup": evil_apt_log, "responder": apt_responder,
                                        "patches": [("live_system", lambda: False)]}),
    ("packages-list: unicode digit", ["packages-list", "²"], "", "refuse", None, {}),

    # The dispatcher.
    ("unknown verb", ["shell"], "", "refuse", None, {}),
    ("no verb", [], "", "refuse", None, {}),
]


def main():
    helper = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HELPER
    h = harness.Harness(helper)
    findings = 0
    for name, argv, stdin, expect, check, options in CASES:
        result = h.run(argv, stdin, **options)
        if result.crashed:
            verdict, why = "FINDING", "uncaught exception: " + result.crashed.strip().splitlines()[-1]
        elif expect == "refuse":
            acted = result.commands or result.changed
            ok = result.code not in (0, None) and not acted
            verdict = "ok" if ok else "FINDING"
            why = "" if ok else f"exit {result.code}, would run {[a for a, _ in result.commands]}"
        else:
            ok, why = (result.code == 0, f"exit {result.code}: {result.stderr.strip()}")
            if ok and check:
                ok, why = check(result)
            verdict = "ok" if ok else "FINDING"
        findings += verdict == "FINDING"
        print(f"{verdict:8} {name}" + (f"\n         {why}" if why and verdict != "ok" else ""))
    print(f"\n{len(CASES)} cases, {findings} findings")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
