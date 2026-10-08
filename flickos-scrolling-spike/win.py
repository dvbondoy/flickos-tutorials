#!/usr/bin/python3
"""A test window filled with one color: ./headless.sh run ./win.py NAME COLOR

NAME is its app id (what labwc's identifier= matches) and its title, COLOR
any CSS color. bbox.py finds the window on a screenshot by that color."""
import sys
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

name, color = sys.argv[1], sys.argv[2]
GLib.set_prgname(name)
css = Gtk.CssProvider()
css.load_from_data(f"window {{ background: {color}; }}".encode())
Gtk.StyleContext.add_provider_for_screen(
    __import__("gi.repository.Gdk", fromlist=["Gdk"]).Screen.get_default(),
    css, Gtk.STYLE_PROVIDER_PRIORITY_USER)
window = Gtk.Window(title=name)
window.set_default_size(400, 300)
window.connect("destroy", Gtk.main_quit)
# Wayland never tells a window where it is, only its size: print every new
# size (logs/win-NAME.log), so a window cut off by the screen's edge shows
# whether it was squeezed or is only partly on screen.
last = []
def configured(widget, event):
    if [event.width, event.height] != last:
        last[:] = [event.width, event.height]
        print(f"{GLib.get_monotonic_time() // 1000} size {event.width}x{event.height}", flush=True)
window.connect("configure-event", configured)
window.show_all()
Gtk.main()
