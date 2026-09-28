#!/bin/sh
# run.sh: run a program inside the harness (its Wayland display, its D-Bus,
# its home folder), instead of on your real desktop.
#
#   ./run.sh foot &                          a window; & so your shell stays free
#   ./run.sh wtype 'hello'                   type into the focused window
#   ./run.sh flickos-layout current          FlickOS's commands see the harness's settings
#   ./run.sh sh                              a shell whose programs all go to the harness

. "$(dirname "$0")/harness.env"
[ $# -gt 0 ] || { sed -n '5,8p' "$0"; exit 2; }
harness_running || { echo "the harness isn't running (./start.sh)" >&2; exit 1; }

# The environment the session inside has (harness_env), plus what a client
# started from outside needs:
# - WAYLAND_DISPLAY: the harness's socket, looked up in XDG_RUNTIME_DIR.
# - LABWC_PID: `labwc --reconfigure` and `--exit` signal this PID. It must be
#   the harness's labwc as your shell sees it, not its PID inside the
#   namespace, and never your real labwc's.
# - XDG_CONFIG_DIRS, XDG_DATA_DIRS: what flickos-session sets, with the
#   harness's own layout overlay first.
# exec: this script's PID becomes the program's, so `./run.sh foot & pid=$!`
# gives foot's PID.
HARNESS_EXEC=exec
harness_env \
    WAYLAND_DISPLAY=wayland-0 \
    LABWC_PID="$(harness_pids labwc | head -1)" \
    XDG_CONFIG_DIRS="$HL_RUN/flickos/xdg:/etc/xdg/flickos:/etc/xdg" \
    XDG_DATA_DIRS="/usr/share/flickos:/usr/local/share:/usr/share" \
    XDG_CURRENT_DESKTOP=labwc:wlroots XDG_SESSION_TYPE=wayland \
    "$@"
