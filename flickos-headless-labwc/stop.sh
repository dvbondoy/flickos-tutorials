#!/bin/sh
# stop.sh: stop the harness and everything in it.
#
#   ./stop.sh            stop; keep its files (home folder, logs) to look at
#   ./stop.sh --clean    stop and delete its files too

. "$(dirname "$0")/harness.env"

pid=$(cat "$HL/unshare.pid" 2>/dev/null)
gone() { ! kill -0 "$pid" 2>/dev/null; }
wait_gone() { i=0; while ! gone && [ $i -lt 50 ]; do sleep 0.1; i=$((i + 1)); done; gone; }
# Only if that PID really is our unshare: a PID from an old file may belong
# to something else by now.
if [ -n "$pid" ] && [ "$(cat /proc/"$pid"/comm 2>/dev/null)" = unshare ]; then
    # Signals to unshare do nothing: with --fork it ignores SIGTERM and SIGINT.
    # And the namespace's first process (its "PID 1") ignores every signal it
    # has no handler for. So stop labwc, which does handle SIGTERM: when it
    # exits, the first process ends, and the kernel stops all the others.
    for p in $(harness_pids labwc); do kill "$p"; done
    if wait_gone; then
        echo "stopped (labwc exited, the namespace went with it)"
    else
        # SIGKILL always works, also on a namespace's first process.
        kill -KILL "$(pgrep -P "$pid")" 2>/dev/null
        wait_gone && echo "stopped with SIGKILL" || echo "could not stop unshare PID $pid"
    fi
else
    echo "not running"
fi
# Programs started with ./run.sh live outside the namespace; they lose their
# display and exit by themselves. Report any still there.
sleep 0.5
left=$(for n in $(ls /proc | grep -E '^[0-9]+$'); do
    tr '\0' '\n' 2>/dev/null <"/proc/$n/environ" | grep -qx "XDG_RUNTIME_DIR=$HL_RUN" && echo "$n $(cat /proc/$n/comm)"
done)
[ -n "$left" ] && echo "still running with the harness's settings (stop by PID):" && echo "$left"

if [ "$1" = --clean ]; then
    rm -rf "$HL"
    echo "deleted $HL"
fi
