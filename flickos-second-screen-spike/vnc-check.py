#!/usr/bin/python3
"""A tiny VNC client (gtk-vnc's GVnc, no window) for checking wayvnc.

  vnc-check.py HOST PORT [--size WxH] [--user U --password P] [--seconds N]

Prints the screen size the server gives, asks for --size (what a tablet's
VNC app does when it says "resize the remote screen to fit"), and counts
the screen updates that arrive in --seconds.
"""
import argparse, time
import gi
gi.require_version("GVnc", "1.0")
from gi.repository import GLib, GVnc

p = argparse.ArgumentParser()
p.add_argument("host"); p.add_argument("port", type=int)
p.add_argument("--size"); p.add_argument("--user"); p.add_argument("--password")
p.add_argument("--seconds", type=float, default=3)
a = p.parse_args()

loop = GLib.MainLoop()
conn = GVnc.Connection.new()
start = time.monotonic()
updates = 0
fb = None

def say(text):
    print(f"{1000 * (time.monotonic() - start):6.0f} ms  {text}", flush=True)

def choose_type(c, types):
    offered = [types.get_nth(i) if hasattr(types, "get_nth") else v for i, v in enumerate(types)] \
        if not hasattr(types, "n_values") else [types.get_nth(i) for i in range(types.n_values)]
    say(f"security types offered: {offered}")
    # 1 None, 2 VNC, 19 VeNCrypt, 6 RSA-AES, 30 Apple DH
    for want in (1, 2, 19, 30):
        if want in offered:
            c.set_auth_type(want); say(f"chose {want}"); return
    say("no security type this client knows"); loop.quit()

def choose_subtype(c, kind, subtypes):
    offered = [subtypes.get_nth(i) for i in range(subtypes.n_values)]
    say(f"subtypes for {kind}: {offered}")
    c.set_auth_subtype(offered[0])

def credential(c, creds):
    for i in range(creds.n_values):
        what = creds.get_nth(i)
        value = {0: a.user, 1: a.password, 2: "flickos"}.get(int(what))
        c.set_credential(int(what), value or "")

def make_fb(w, h):
    global fb
    fmt = GVnc.PixelFormat.new()
    fmt.bits_per_pixel = 32; fmt.depth = 24; fmt.true_color_flag = 1
    fmt.red_max = fmt.green_max = fmt.blue_max = 255
    fmt.red_shift, fmt.green_shift, fmt.blue_shift = 16, 8, 0
    fmt.byte_order = 1234
    buf = bytearray(w * h * 4)
    fb = GVnc.BaseFramebuffer.new(buf, w, h, w * 4, fmt, conn.get_pixel_format())
    conn.set_framebuffer(fb)
    conn.framebuffer_update_request(False, 0, 0, w, h)

def initialized(c):
    w, h = c.get_width(), c.get_height()
    say(f"connected: {w}x{h} '{c.get_name()}'")
    c.set_encodings([0, -223, -308])          # raw, DesktopSize, ExtendedDesktopSize
    make_fb(w, h)
    if a.size:
        sw, sh = map(int, a.size.split("x"))
        GLib.timeout_add(300, lambda: (say(f"asking for {sw}x{sh}: {c.set_size(sw, sh)}"), False)[1])
    GLib.timeout_add(int(a.seconds * 1000), lambda: (say(f"updates: {updates}; size now {c.get_width()}x{c.get_height()}"), loop.quit()))

def resized(c, w, h):
    say(f"server resized the screen to {w}x{h}")
    make_fb(w, h)

def update(c, x, y, w, h):
    global updates
    updates += 1
    c.framebuffer_update_request(True, 0, 0, c.get_width(), c.get_height())

conn.connect("vnc-auth-choose-type", choose_type)
conn.connect("vnc-auth-choose-subtype", choose_subtype)
conn.connect("vnc-auth-credential", credential)
conn.connect("vnc-auth-failure", lambda c, m: (say(f"auth failed: {m}"), loop.quit()))
conn.connect("vnc-auth-unsupported", lambda c, t: (say(f"auth unsupported: {t}"), loop.quit()))
conn.connect("vnc-initialized", initialized)
conn.connect("vnc-desktop-resize", resized)
conn.connect("vnc-framebuffer-update", update)
conn.connect("vnc-disconnected", lambda c: (say("disconnected"), loop.quit()))
conn.connect("vnc-error", lambda c, m: say(f"error: {m}"))
conn.open_host(a.host, str(a.port))
GLib.timeout_add(15000, lambda: (say("timeout"), loop.quit()))
loop.run()
