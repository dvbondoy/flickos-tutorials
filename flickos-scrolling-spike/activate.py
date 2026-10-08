#!/usr/bin/python3
"""Do to every window with an app id what flick-tiler's daemon can do to it
(wlr-foreign-toplevel): ./headless.sh run ./activate.py APP_ID [activate|minimize|unminimize]

Uses flick-tiler's own small Wayland client from the FlickOS tree, with a
stand-in for its daemon, so this sends exactly what the daemon would."""
import importlib.machinery
import selectors
import socket
import sys
import time

TILER = "/home/jon/Documents/Projects/FlickOS/packages/flick-tiler/usr/bin/flick-tiler"
ft = importlib.machinery.SourceFileLoader("ft", TILER).load_module()


class StandIn:
    """What Toplevels calls on the daemon: just enough to collect windows."""
    def __init__(self):
        self.tiler = ft.Tiler(ft.Settings())
        self.changed = False
        self.ready = False

    def started(self):
        self.ready = True


app_id = sys.argv[1]
action = sys.argv[2] if len(sys.argv) > 2 else "activate"
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect(ft.wayland_socket_path())
daemon = StandIn()
toplevels = ft.Toplevels(sock, daemon)
selector = selectors.DefaultSelector()
selector.register(toplevels, selectors.EVENT_READ)
deadline = time.monotonic() + 2
while time.monotonic() < deadline and not (daemon.ready and any(w.app_id for w in daemon.tiler.windows.values())):
    if selector.select(0.05):
        toplevels.dispatch()
handles = [h for h, w in daemon.tiler.windows.items() if w.app_id == app_id]
for handle in handles:
    if action == "activate":
        toplevels.activate(handle)
    else:
        toplevels.minimize(handle, on=action == "minimize")
print(f"{action} {app_id}: {len(handles)} window(s)")
time.sleep(0.2)
