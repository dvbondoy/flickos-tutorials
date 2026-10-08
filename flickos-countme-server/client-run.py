#!/usr/bin/python3
"""Run FlickOS's real flickos-countme program, but with its files moved into
a folder of your choice, so it can talk to a test server without sudo and
without touching /etc/flickos/countme or /var/lib/flickos-countme.

    client-run.py FOLDER show|status|run [--dry-run]

FOLDER holds countme.conf (like /etc/flickos/countme), flickos-release
(FLICKOS_VERSION=...), proc/cmdline (so it doesn't think it's a live
session) and state/ (the last week counted). local-test.sh makes one.
FLICKOS: the FlickOS checkout (default ~/Documents/Projects/FlickOS).
"""
import importlib.machinery
import importlib.util
import os
import sys

flickos = os.environ.get("FLICKOS", os.path.expanduser("~/Documents/Projects/FlickOS"))
program = os.path.join(flickos, "packages/flickos-countme/usr/bin/flickos-countme")
# The program has no .py ending, so load it by hand as a module named fc.
loader = importlib.machinery.SourceFileLoader("fc", program)
fc = importlib.util.module_from_spec(importlib.util.spec_from_loader("fc", loader))
loader.exec_module(fc)

folder = os.path.abspath(sys.argv[1])
fc.CONF = os.path.join(folder, "countme.conf")
fc.RELEASE = os.path.join(folder, "flickos-release")
fc.PROC = os.path.join(folder, "proc")
fc.STATE_DIR = os.path.join(folder, "state")
sys.exit(fc.main(sys.argv[2:]))
