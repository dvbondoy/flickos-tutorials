#!/bin/bash
# A throwaway labwc with no screen of its own, for the tests that must not
# touch your session (many reconfigures, windows moved off the screen).
#
#   [OUTPUTS=2] ./headless.sh start   start it (config: cfg/labwc/rc.xml), with OUTPUTS screens
#   ./headless.sh run CMD…       run CMD against it (wlr-randr, wtype, win.py…)
#   ./headless.sh pid NAME       the PIDs of NAME running against it
#   ./headless.sh reload         reread cfg/labwc/rc.xml (labwc --reconfigure)
#   ./headless.sh stop           stop it and everything run against it
#
# Isolation: `env -i` starts it with an empty environment, its own
# XDG_RUNTIME_DIR (so its socket is not your session's wayland-0) and its
# own HOME (headless/home). WLR_BACKENDS=headless: no real screen, input or
# GPU; WLR_RENDERER=pixman draws in memory. Nothing reaches your desktop.
set -eu
SPIKE=$(cd "$(dirname "$0")" && pwd)
STATE=$SPIKE/rt
mkdir -p "$SPIKE/logs" "$SPIKE/home"

rt() { cat "$STATE" 2>/dev/null || { echo "not started (./headless.sh start)" >&2; exit 1; }; }

# The PIDs of NAME that belong to this labwc: picked by the XDG_RUNTIME_DIR
# in their environment, never by name alone (your desktop runs labwc too).
ours() {
    for p in $(pgrep -x "$1"); do
        grep -qz "XDG_RUNTIME_DIR=$(rt)" "/proc/$p/environ" 2>/dev/null && echo "$p"
    done
}

case "${1:-}" in
start)
    [ -f "$STATE" ] && { echo "already started: $(cat "$STATE")"; exit 1; }
    dir=$(mktemp -d "${TMPDIR:-/tmp}/sc.XXXX")   # short: socket paths max 108 bytes
    echo "$dir" > "$STATE"
    setsid env -i HOME="$SPIKE/home" XDG_RUNTIME_DIR="$dir" PATH=/usr/bin:/bin \
        WLR_BACKENDS=headless WLR_RENDERER=pixman WLR_HEADLESS_OUTPUTS="${OUTPUTS:-1}" \
        WLR_LIBINPUT_NO_DEVICES=1 labwc -C "$SPIKE/cfg/labwc" -d \
        > "$SPIKE/logs/labwc-headless.log" 2>&1 < /dev/null &
    for _ in $(seq 20); do [ -S "$dir/wayland-0" ] && break; sleep 0.2; done
    echo "labwc $(ours labwc) on $dir/wayland-0"
    ;;
run)
    shift
    exec env -i HOME="$SPIKE/home" XDG_RUNTIME_DIR="$(rt)" PATH=/usr/bin:/bin \
        WAYLAND_DISPLAY=wayland-0 GSETTINGS_BACKEND=memory "$@"
    ;;
pid)
    ours "$2"
    ;;
reload)
    # What `labwc --reconfigure` does: SIGHUP to labwc, which rereads rc.xml.
    kill -HUP "$(ours labwc)"
    ;;
stop)
    for name in win.py labwc; do
        for p in $(ours $name); do kill "$p" && echo "stopped $name $p"; done
    done
    rm -rf "$(rt)" "$STATE"
    ;;
*)
    sed -n '2,9p' "$0"; exit 2 ;;
esac
