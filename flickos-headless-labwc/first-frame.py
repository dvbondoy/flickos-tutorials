#!/usr/bin/env python3
"""first-frame.py: how long a Python GTK 3 program takes from starting to
its first window being drawn (HIG PERF-1: at most 1 s), then quit it.

    ./run.sh ./first-frame.py /usr/bin/flickos-control
    ./run.sh ./first-frame.py /usr/bin/flickos-welcome
    ./run.sh ./first-frame.py --stay /usr/bin/flickos-control    keep it open

Run it several times: the first run reads files from disk, later ones from
the cache, and the HIG's numbers are the later ones.

How: before running the program (runpy, as `python3 PROGRAM` would), it
wraps Gtk.Window's show methods so every window it shows reports its first
"draw" signal. The time counts from the moment the process started (from
/proc/self/stat), so Python's own start is included, as the user feels it.
"""
import os
import runpy
import sys
import time

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

TICK = os.sysconf("SC_CLK_TCK")


def seconds_since_start():
    with open("/proc/self/stat") as f:
        started = int(f.read().rsplit(")", 1)[1].split()[19]) / TICK  # field 22: starttime
    with open("/proc/uptime") as f:
        now = float(f.read().split()[0])
    return now - started


def main():
    args = sys.argv[1:]
    stay = args[:1] == ["--stay"]
    if stay:
        args = args[1:]
    if not args:
        sys.exit(__doc__)
    reported = []

    def on_draw(window, _cr):
        if not reported:
            reported.append(True)
            print(f"[first-frame] {os.path.basename(args[0])}: first window "
                  f"'{window.get_title()}' drawn {seconds_since_start() * 1000:.0f} ms after start",
                  flush=True)
            if not stay:
                GLib.timeout_add(200, lambda: os._exit(0))
        return False

    def wrap(name):
        original = getattr(Gtk.Window, name)

        def show(self, *a, **kw):
            self.connect_after("draw", on_draw)
            return original(self, *a, **kw)
        setattr(Gtk.Window, name, show)

    for name in ("show", "show_all", "present"):
        wrap(name)
    sys.argv = args
    runpy.run_path(args[0], run_name="__main__")


if __name__ == "__main__":
    main()
