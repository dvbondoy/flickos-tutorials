#!/usr/bin/env python3
"""record-portal.py: record the screen through the ScreenCast portal and
GStreamer, the way OBS and browsers do it. Recordings go into ./recordings/.
Press Enter to stop.

    ./record-portal.py --check        only talk to the portal: no window, no recording
    ./record-portal.py --test         only GStreamer: a test picture, no portal
    ./record-portal.py                the whole screen, no sound
    ./record-portal.py --region       drag a rectangle first (slurp)
    ./record-portal.py --audio        with the desktop's sound (--mic: microphone)
    ./record-portal.py --kill         stop with SIGKILL instead (crash test)

Needs gstreamer1.0-pipewire and gstreamer1.0-tools (see step 8).
"""
import argparse
import os
import random
import signal
import subprocess
import sys
import time

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PORTAL = "org.freedesktop.portal.Desktop"
OBJECT = "/org/freedesktop/portal/desktop"
SCREENCAST = "org.freedesktop.portal.ScreenCast"
MONITOR, EMBEDDED_CURSOR = 1, 2

bus = Gio.bus_get_sync(Gio.BusType.SESSION)
loop = GLib.MainLoop()


def log(message):
    print(f"[portal] {message}", flush=True)


def request(method, signature, args, options):
    """Call a portal method and wait for its answer.

    Portal methods don't answer directly: they return a Request object at
    once, and the answer comes later as that object's Response signal
    (the user may take a minute to pick a screen). The object's path is
    known in advance from our bus name and a token we choose, so we listen
    for the signal *before* calling, and can't miss it.
    """
    token = f"snip{random.randrange(1 << 30)}"
    sender = bus.get_unique_name()[1:].replace(".", "_")
    path = f"/org/freedesktop/portal/desktop/request/{sender}/{token}"
    answer = {}

    def on_response(_conn, _sender, _path, _iface, _signal, params):
        answer["code"], answer["results"] = params.unpack()
        loop.quit()

    sub = bus.signal_subscribe(None, "org.freedesktop.portal.Request", "Response", path,
                               None, Gio.DBusSignalFlags.NONE, on_response)
    options = dict(options, handle_token=GLib.Variant("s", token))
    log(f"{method} …")
    bus.call_sync(PORTAL, OBJECT, SCREENCAST, method,
                  GLib.Variant(signature, (*args, options)),
                  GLib.VariantType("(o)"), Gio.DBusCallFlags.NONE, -1, None)
    loop.run()
    bus.signal_unsubscribe(sub)
    # 0 = done, 1 = the user cancelled, 2 = failed.
    if answer["code"] != 0:
        sys.exit(f"[portal] {method}: {'cancelled' if answer['code'] == 1 else 'failed'}")
    return answer["results"]


def portal_property(name):
    value = bus.call_sync(PORTAL, OBJECT, "org.freedesktop.DBus.Properties", "Get",
                          GLib.Variant("(ss)", (SCREENCAST, name)),
                          GLib.VariantType("(v)"), Gio.DBusCallFlags.NONE, -1, None)
    return value.unpack()[0]


def close_session(session):
    bus.call_sync(PORTAL, session, "org.freedesktop.portal.Session", "Close",
                  None, None, Gio.DBusCallFlags.NONE, -1, None)


def open_screen(check_only):
    """Ask the portal for one screen; return (fd, node, size, position, session)."""
    cursors = portal_property("AvailableCursorModes")
    session = request("CreateSession", "(a{sv})", (),
                      {"session_handle_token": GLib.Variant("s", "snipsession")})["session_handle"]
    log(f"session {session}")
    options = {"types": GLib.Variant("u", MONITOR), "multiple": GLib.Variant("b", False)}
    if cursors & EMBEDDED_CURSOR:
        options["cursor_mode"] = GLib.Variant("u", EMBEDDED_CURSOR)
    request("SelectSources", "(oa{sv})", (session,), options)
    if check_only:
        close_session(session)
        log("the portal answers; --check stops before anything is shown")
        return None
    # Start is where xdg-desktop-portal-wlr runs its chooser (slurp -o).
    streams = request("Start", "(osa{sv})", (session, ""), {})["streams"]
    node, props = streams[0]
    log(f"PipeWire node {node}, properties {props}")
    # The fd is a PipeWire connection that can see only this one stream.
    result, fds = bus.call_with_unix_fd_list_sync(
        PORTAL, OBJECT, SCREENCAST, "OpenPipeWireRemote",
        GLib.Variant("(oa{sv})", (session, {})), GLib.VariantType("(h)"),
        Gio.DBusCallFlags.NONE, -1, None, None)
    fd = fds.get(result.unpack()[0])
    return fd, node, props.get("size"), props.get("position", (0, 0)), session


def crop_for(region, size, position):
    """videocrop's left/top/right/bottom for a slurp rectangle "X,Y WxH".

    slurp and the portal both count in layout coordinates; at scale 1 those
    are the stream's pixels. (At other scales this would need multiplying.)
    """
    xy, wh = region.split()
    x, y = (int(v) for v in xy.split(","))
    w, h = (int(v) for v in wh.split("x"))
    left, top = x - position[0], y - position[1]
    w, h = w - w % 2, h - h % 2          # even sizes keep the encoder happy
    return f"videocrop left={left} top={top} right={size[0] - left - w} bottom={size[1] - top - h} ! "


def node_name(which):
    out = subprocess.run(["wpctl", "inspect", which], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if "node.name" in line:
            return line.split('"')[1]
    sys.exit(f"no {which}")


def pipeline(video_source, crop, audio_device, path):
    """The gst-launch-1.0 description, one element after another.

    Video: picture source → steady 30 fps → crop → the encoder's pixel
    format → VP8 encoder → WebM file. Audio (optional): sound source →
    convert → Opus encoder → the same WebM file. `queue` puts each branch in
    its own thread so a slow encoder doesn't hold up capturing.
    """
    video = (f"{video_source} ! videorate ! video/x-raw,framerate=30/1 ! {crop}"
             "videoconvert ! queue ! "
             f"vp8enc deadline=1 cpu-used=8 threads={os.cpu_count()} ! "
             f"webmmux name=mux ! filesink location={path}")
    if audio_device:
        video += (f" pulsesrc device={audio_device} ! audioconvert ! audioresample ! "
                  "opusenc ! queue ! mux.")
    return video


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--region", action="store_true")
    parser.add_argument("--audio", action="store_true")
    parser.add_argument("--mic", action="store_true")
    parser.add_argument("--kill", action="store_true")
    args = parser.parse_args()

    audio = None
    if args.audio:
        audio = node_name("@DEFAULT_AUDIO_SINK@") + ".monitor"
    elif args.mic:
        audio = node_name("@DEFAULT_AUDIO_SOURCE@")

    region = None
    if args.region:
        # Choose first: the chooser in Start picks only which screen.
        done = subprocess.run(["slurp"], capture_output=True, text=True)
        if done.returncode:
            sys.exit("cancelled")
        region = done.stdout.strip()

    session, pass_fds = None, ()
    if args.test:
        source, crop = "videotestsrc is-live=true pattern=ball ! video/x-raw,width=1280,height=720", ""
    else:
        opened = open_screen(args.check)
        if opened is None:
            return
        fd, node, size, position, session = opened
        # keepalive-time: the portal sends a frame only when the screen
        # changes; this repeats the last one so the video keeps its pace.
        source = f"pipewiresrc fd={fd} path={node} do-timestamp=true keepalive-time=1000"
        crop = crop_for(region, size, position) if region else ""
        pass_fds = (fd,)

    os.makedirs(os.path.join(HERE, "recordings"), exist_ok=True)
    path = os.path.join(HERE, "recordings",
                        time.strftime("%Y%m%d-%H%M%S") + ("-test" if args.test else "-portal") + ".webm")
    description = pipeline(source, crop, audio, path)
    log(f"gst-launch-1.0 -e {description}")
    # -e: on SIGINT, send end-of-stream through the pipeline first, so the
    # encoder and the muxer finish the file properly.
    gst = subprocess.Popen(["gst-launch-1.0", "-e", *description.split()], pass_fds=pass_fds,
                           stdout=open(os.path.join(HERE, "recordings", "gst.log"), "w"),
                           stderr=subprocess.STDOUT)
    measure = subprocess.Popen([os.path.join(HERE, "measure.py"), str(gst.pid)])
    started = time.monotonic()
    log(f"recording (gst-launch-1.0 PID {gst.pid}) -> {path}")
    log(f"press Enter to stop with {'SIGKILL' if args.kill else 'SIGINT'}")
    try:
        input()
    except (KeyboardInterrupt, EOFError):
        pass
    gst.send_signal(signal.SIGKILL if args.kill else signal.SIGINT)
    try:
        gst.wait(timeout=15)
    except subprocess.TimeoutExpired:
        log("gst-launch didn't finish in 15 s; killing it")
        gst.kill()
        gst.wait()
    seconds = time.monotonic() - started
    measure.wait()
    if session:
        close_session(session)
    size = os.path.getsize(path) if os.path.exists(path) else 0
    log(f"stopped after {seconds:.0f} s: {size // 1024} KB, "
        f"about {size * 60 / max(seconds, 1) / 1048576:.1f} MB a minute")
    log(f"GStreamer's messages: {os.path.join('recordings', 'gst.log')}")
    log(f"play it: gst-play-1.0 {os.path.relpath(path)}")


if __name__ == "__main__":
    main()
