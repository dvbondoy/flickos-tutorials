#!/bin/sh
# record-wf.sh: record the screen with wf-recorder, measured by measure.py.
# Recordings go into ./recordings/. Press Enter to stop.
#
#   ./record-wf.sh screen                 the whole screen, no sound
#   ./record-wf.sh region --audio         a rectangle, with the desktop's sound
#   ./record-wf.sh screen --mic           with the microphone
#   ./record-wf.sh screen --webm          VP8 + Opus in WebM instead of H.264 in MP4
#   ./record-wf.sh screen --kill          stop with SIGKILL instead (crash test)
#   ./record-wf.sh screen -- -p preset=ultrafast   the rest goes to wf-recorder

cd "$(dirname "$0")" || exit 1
mode=$1; shift 2>/dev/null
stop=INT ext=mp4
case $mode in screen|region) ;; *) sed -n '5,11p' "$0"; exit 2 ;; esac
command -v wf-recorder >/dev/null || { echo "wf-recorder isn't installed (see step 7)"; exit 1; }

node() { wpctl inspect "$1" | sed -n 's/.*node\.name = "\(.*\)"/\1/p'; }
# Turn our options into wf-recorder's; keep the rest as they are. Each
# argument is taken off the front and, if kept, put back at the end.
n=$#
while [ $n -gt 0 ]; do
    a=$1; shift; n=$((n - 1))
    case $a in
        # The desktop's sound is the speakers' "monitor": what they play.
        --audio) set -- "$@" --audio-backend=pulse "--audio=$(node @DEFAULT_AUDIO_SINK@).monitor" ;;
        --mic)   set -- "$@" --audio-backend=pulse "--audio=$(node @DEFAULT_AUDIO_SOURCE@)" ;;
        --webm)  ext=webm; set -- "$@" -c libvpx -C libopus ;;
        --kill)  stop=KILL ;;
        --)      while [ $n -gt 0 ]; do set -- "$@" "$1"; shift; n=$((n - 1)); done ;;
        *)       set -- "$@" "$a" ;;
    esac
done

if [ $mode = region ]; then
    where=$(slurp) || { echo "cancelled"; exit 1; }
    set -- -g "$where" "$@"
fi

mkdir -p recordings
file=recordings/$(date +%Y%m%d-%H%M%S)-wf-$mode.$ext
# -f: wf-recorder picks the format from the file name's extension.
# env --default-signal: a shell starts background programs with SIGINT
# ignored (POSIX); this puts the default back so kill -INT reaches it.
env --default-signal=INT wf-recorder -f "$file" "$@" >recordings/wf-recorder.log 2>&1 &
pid=$!
./measure.py $pid &
started=$(date +%s)
echo "recording (wf-recorder PID $pid) -> $file"
echo "press Enter to stop with SIG$stop"
read -r _
kill -$stop $pid
wait $pid
wait
seconds=$(( $(date +%s) - started ))
size=$(stat -c %s "$file" 2>/dev/null || echo 0)
echo "stopped after $seconds s: $(( size / 1024 )) KB, about $(( size * 60 / (seconds > 0 ? seconds : 1) / 1048576 )) MB a minute"
echo "wf-recorder's messages: recordings/wf-recorder.log"
echo "play it: gst-play-1.0 $file   (or: vlc $file)"
