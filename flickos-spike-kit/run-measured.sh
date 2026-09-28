#!/bin/sh
# run-measured.sh: start a program, measure it with the repo's
# tools/measure.py, and stop exactly that process when you press Enter.
# Its output goes into ./logs/.
#
#   ./run-measured.sh -- flickos-control                stop with SIGTERM (a normal stop)
#   ./run-measured.sh --int -- wf-recorder -f x.mp4     SIGINT, like Ctrl+C: lets it finish files
#   ./run-measured.sh --kill -- my-daemon               SIGKILL: what a crash looks like
#   ./run-measured.sh --tree -- sh -c 'a & b & wait'    count the processes it starts too
#
# FLICKOS_REPO or FLICKOS: the FlickOS checkout (default ~/Documents/Projects/FlickOS).

cd "$(dirname "$0")" || exit 1
REPO=${FLICKOS_REPO:-${FLICKOS:-$HOME/Documents/Projects/FlickOS}}
MEASURE=$REPO/tools/measure.py
[ -x "$MEASURE" ] || { echo "no $MEASURE (set FLICKOS_REPO)"; exit 2; }

signal=TERM tree=
while [ $# -gt 0 ]; do
    case $1 in
        --int)  signal=INT ;;
        --kill) signal=KILL ;;
        --tree) tree=--tree ;;
        --)     shift; break ;;
        *)      sed -n '6,9p' "$0"; exit 2 ;;
    esac
    shift
done
[ $# -gt 0 ] || { sed -n '6,9p' "$0"; exit 2; }

mkdir -p logs
log=logs/$(date +%Y%m%d-%H%M%S)-$(basename "$1").log
# setsid: its own process group, so the stop below reaches the processes it
# starts too (a signal to one PID doesn't reach its children).
# env --default-signal: a shell starts background programs with SIGINT and
# SIGQUIT ignored (POSIX), so without it --int would do nothing to most.
setsid env --default-signal=INT,QUIT "$@" >"$log" 2>&1 &
pid=$!                       # the PID of exactly what we started, also its group's ID
"$MEASURE" $tree $pid &
started=$(date +%s)
echo "$1 is PID $pid; its output goes to $log"
echo "press Enter to stop it with SIG$signal"
read -r _
kill -s $signal -- -$pid 2>/dev/null || echo "(it had already ended)"
wait $pid
echo "exit status $? after $(( $(date +%s) - started )) s"
wait                         # for measure.py's summary
