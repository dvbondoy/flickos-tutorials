#!/usr/bin/python3
"""Open one tiny window with the app id given, so a labwc window rule
runs its actions, then exit once labwc closes it (or after 3 s)."""
import sys, time
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

app_id = sys.argv[1]
GLib.set_prgname(app_id)          # GTK 3 on Wayland: app id = prgname
start = time.monotonic()
win = Gtk.Window(title=app_id)
win.set_default_size(1, 1)
win.connect("map-event", lambda *a: print(f"mapped after {1000*(time.monotonic()-start):.0f} ms", flush=True))
win.connect("delete-event", lambda *a: (print(f"closed by labwc after {1000*(time.monotonic()-start):.0f} ms", flush=True), Gtk.main_quit()))
GLib.timeout_add(3000, lambda: (print("not closed in 3 s", flush=True), Gtk.main_quit()))
win.show()
Gtk.main()
