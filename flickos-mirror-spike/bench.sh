#!/bin/sh
# bench.sh: mirror the phone for 70 s while adb scrolls it the same way every
# time, measure scrcpy (tools/measure.py), then print the fps summary.
# Load env.sh first. Open the same long list on the phone before each run
# (Settings > Apps > See all apps) and leave it alone.
#
#   ./bench.sh full                                    scrcpy's defaults
#   ./bench.sh m1024 --max-size 1024
#   ./bench.sh m1024-gles --max-size 1024 --render-driver=opengles2
#   ./bench.sh nomip --no-mipmaps
#
# Output: logs/bench-NAME-scrcpy.log (scrcpy, with its fps lines) and
# logs/bench-NAME-measure.log (CPU, memory, wakeups).

cd "$(dirname "$0")" || exit 1
REPO=${FLICKOS_REPO:-$HOME/Documents/Projects/FlickOS}
[ $# -ge 1 ] || { sed -n '7,10p' "$0"; exit 2; }
[ -n "$ADB" ] || { echo "load env.sh first: . ./env.sh"; exit 2; }
name=$1; shift

# The phone's current address; old ports stay listed as "offline".
serial=$("$ADB" devices | awk '$2 == "device" && $1 ~ /:/ { print $1; exit }')
[ -n "$serial" ] || { echo "no phone connected: ./pair-qr.py --connect-only"; exit 1; }

mkdir -p logs
slog=logs/bench-$name-scrcpy.log
mlog=logs/bench-$name-measure.log
echo "$name: scrcpy -s $serial --print-fps $*"

setsid scrcpy -s "$serial" --print-fps --time-limit 70 "$@" >"$slog" 2>&1 &
pid=$!
"$REPO/tools/measure.py" "$pid" >"$mlog" 2>&1 &

# Let the window open and the first frames come, then scroll for about 60 s:
# down and back up, so every run ends where it started.
sleep 6
"$ADB" -s "$serial" shell '
    end=$(( $(date +%s) + 60 ))
    while [ $(date +%s) -lt $end ]; do
        input swipe 540 1800 540 700 300
        input swipe 540 700 540 1800 300
    done'
wait
./fps-summary.py "$slog"
tail -n 1 "$mlog"
