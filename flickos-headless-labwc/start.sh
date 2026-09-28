#!/bin/sh
# start.sh: start a labwc with no screen, keyboard or mouse, in the
# background, isolated from your real session.
#
#   ./start.sh                   plain labwc, nothing else: test one program in it
#   ./start.sh --flickos         the whole FlickOS session (flickos-session: panel,
#                                start menu, tiler … from the installed packages)
#   ./start.sh --flickos --first-login   the same with /etc/skel copied in, as a new account
#   ./start.sh --size 1366x768   the screen size (default 1366x768, the HIG's target)

. "$(dirname "$0")/harness.env"

mode=plain size=1366x768 skel=no
while [ $# -gt 0 ]; do
    case $1 in
        --flickos)     mode=flickos ;;
        --first-login) skel=yes ;;
        --size)        size=$2; shift ;;
        *) sed -n '5,10p' "$0"; exit 2 ;;
    esac
    shift
done

if harness_running; then
    echo "already running (./stop.sh first)"; exit 1
fi
rm -rf "$HL"
mkdir -p "$HL_RUN" "$HL_HOME" "$HL_LOG" "$HL/labwc"
chmod 700 "$HL_RUN"                      # Wayland wants a private runtime folder
[ $skel = yes ] && cp -a /etc/skel/. "$HL_HOME"

# What runs inside: a session bus of our own (so nothing reaches your real
# session's D-Bus), then labwc. "plain" gives labwc an empty config folder
# (-C), so it uses its built-in defaults and starts nothing.
if [ $mode = flickos ]; then
    session=flickos-session
else
    session="labwc -C $HL/labwc"
fi
inside="dbus-daemon --session --address=unix:path=\$XDG_RUNTIME_DIR/bus --nofork --nopidfile &
while [ ! -S \"\$XDG_RUNTIME_DIR/bus\" ]; do sleep 0.1; done
$session"

# The pieces, outside in:
# - harness_env: an environment built from nothing (see harness.env), plus
#   WLR_BACKENDS=headless: wlroots draws into memory, not onto a screen;
#   pixman: drawing on the CPU, no GPU needed; one virtual output (HEADLESS-1);
#   no real keyboards or mice.
# - setsid: its own process group, not tied to this terminal.
# - unshare --user --map-root-user --mount --pid --fork --mount-proc: new
#   namespaces, no sudo needed (a user namespace makes you "root" inside it,
#   and only there):
#   - PID: inside, only the harness's own processes exist, so FlickOS's
#     `pkill -x flickos-menu` and friends can't reach your real desktop;
#   - mount: its own /proc, and its own empty /tmp/.X11-unix (a tmpfs),
#     because XWayland refuses the real one: inside the namespace it looks
#     owned by "nobody", as everything of the real root does.
#   --kill-child: when unshare is stopped, everything inside dies with it.
# - the second unshare (--map-user, --map-group) makes you your own user
#   again inside, after the mount: programs that check `id -u` see yours.
(HARNESS_EXEC=exec; harness_env \
    WLR_BACKENDS=headless WLR_RENDERER=pixman WLR_HEADLESS_OUTPUTS=1 WLR_LIBINPUT_NO_DEVICES=1 \
    setsid unshare --user --map-root-user --mount --pid --fork --mount-proc --kill-child \
    sh -c 'mount -t tmpfs -o mode=1777 tmpfs /tmp/.X11-unix &&
           exec unshare --user --map-user="$1" --map-group="$2" sh -c "$0"' \
    "$inside" "$(id -u)" "$(id -g)") >"$HL_LOG/session.log" 2>&1 &
echo $! >"$HL/unshare.pid"

# Wait for labwc's socket, at most 10 s.
i=0
until [ -S "$HL_RUN/wayland-0" ]; do
    i=$((i + 1))
    if [ $i -gt 100 ]; then
        echo "labwc didn't start; the last lines of $HL_LOG/session.log:"
        tail -15 "$HL_LOG/session.log"
        exit 1
    fi
    sleep 0.1
done

"$HARNESS_DIR/run.sh" wlr-randr --output HEADLESS-1 --custom-mode "$size" ||
    echo "(could not set the size $size)"
echo "harness running ($mode, $size): labwc PID $(harness_pids labwc), unshare PID $(cat "$HL/unshare.pid")"
echo "  its files:  $HL"
echo "  its log:    $HL_LOG/session.log"
echo "  next:       ./run.sh PROGRAM &   ./shot.sh   ./stop.sh"
