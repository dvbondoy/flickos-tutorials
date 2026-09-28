#!/usr/bin/env python3
"""try-checks.py: turn boot-test checks into a script for the ship
tutorial's vm-run.py, so a new check can be tried in the live ISO before the
ISO that contains your package exists.

    ./try-checks.py [--repo DIR] [--deb FILE.deb …] [--show] PATTERN …

It prints the script on stdout: the checks of DIR/tools/boot-test.py
(default: this folder's practice/ clone) whose description contains one of
the PATTERNs (any case), in their CHECKS order. With --deb, the script first
adds those packages to the ship tutorial's local repo (host: lines), trusts
that repo in the VM and installs them, so the checks see your versions.
--show prints the matching checks' descriptions only.

    ./try-checks.py --deb out/flickos-hello_2.1_all.deb Hello > hello-checks.txt
    ../flickos-ship-tutorial/local-repo.sh serve            (second terminal)
    ../flickos-ship-tutorial/vm-run.py --script "$PWD/hello-checks.txt"

A check that boot-test retries (its seconds) is retried here the same way:
run again every 3 s until it passes or the time is up. Screenshots aren't
taken (vm-run.py --shot takes one at the end).

Never run the printed checks on your own computer: they change settings,
and some close programs by name (pkill), which on your live FlickOS session
would hit your own.

Exit codes: 0 ok, 1 no check matched, 2 usage error.
"""
import argparse
import importlib.machinery
import importlib.util
import os
import shlex
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SHIP = os.path.normpath(os.path.join(HERE, "..", "flickos-ship-tutorial"))
# The test repo as the VM sees it (QEMU's 10.0.2.2 is this computer's 127.0.0.1).
TRUST = [
    "curl -fsS http://10.0.2.2:8000/test-key.asc | sudo tee /etc/apt/keyrings/flickos-test.asc >/dev/null",
    "printf 'Types: deb\\nURIs: http://10.0.2.2:8000\\nSuites: trixie\\nComponents: main\\n"
    "Signed-By: /etc/apt/keyrings/flickos-test.asc\\n' | sudo tee /etc/apt/sources.list.d/flickos-test.sources >/dev/null",
    "sudo apt-get update -q",
]


def load_checks(repo):
    """CHECKS of repo/tools/boot-test.py (it has no .py-less name, so by path)."""
    sys.dont_write_bytecode = True          # no __pycache__ in the repo's tools/
    loader = importlib.machinery.SourceFileLoader("boot_test", os.path.join(repo, "tools/boot-test.py"))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(module)
    return module.CHECKS


def retried(command, seconds):
    """The command, run again every 3 s for up to `seconds` until it passes."""
    if not seconds:
        return command
    return (f"end=$(($(date +%s) + {seconds})); until ( {command} ); do"
            f" [ $(date +%s) -lt $end ] || exit 1; sleep 3; done")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("patterns", nargs="+", metavar="PATTERN")
    parser.add_argument("--repo", default=os.path.join(HERE, "practice"), help="the FlickOS clone (default: practice/)")
    parser.add_argument("--deb", action="append", default=[], help="a package to install first (repeatable)")
    parser.add_argument("--show", action="store_true", help="only list the matching checks")
    opts = parser.parse_args()
    if not os.path.isfile(os.path.join(opts.repo, "tools/boot-test.py")):
        parser.error(f"{opts.repo} has no tools/boot-test.py")
    for deb in opts.deb:
        if not deb.endswith(".deb") or not os.path.isfile(deb):
            parser.error(f"{deb}: not a .deb file")
    words = [pattern.lower() for pattern in opts.patterns]
    checks = [check for check in load_checks(opts.repo) if any(word in check[0].lower() for word in words)]
    if not checks:
        print("try-checks: no check matches", file=sys.stderr)
        return 1
    if opts.show:
        for description, _command, seconds, *shot in checks:
            print(f"{description}\t{seconds} s" + (f"\t{shot[0]}.png" if shot else ""))
        return 0

    print(f"# Made by try-checks.py from {os.path.join(opts.repo, 'tools/boot-test.py')}")
    if opts.deb:
        names = [os.path.basename(deb).split("_")[0] for deb in opts.deb]
        print("\n# Your packages, through the local repo (keep ./local-repo.sh serve running)")
        for deb in opts.deb:
            print(f"host: ./local-repo.sh add {shlex.quote(os.path.abspath(deb))} >/dev/null")
        print(*TRUST, sep="\n")
        print(f"sudo apt-get install -q -y {' '.join(names)}")
        print(f"dpkg-query -W {' '.join(names)}")
    for description, command, seconds, *_shot in checks:
        print(f"\n# {description}")
        print(retried(command, seconds))
    return 0


if __name__ == "__main__":
    sys.exit(main())
