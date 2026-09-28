#!/bin/sh
# shot.sh: a screenshot of the harness's screen, into ./shots/.
#
#   ./shot.sh                     the whole screen, shots/TIME.png
#   ./shot.sh menu                shots/menu.png (a name makes it easy to compare later)
#   ./shot.sh panel "0,728 1366x40"   only a rectangle (X,Y WxH), here the bottom 40 px
#
# grim asks labwc for a copy of the screen (zwlr_screencopy); in the harness
# that screen is the memory labwc draws into, so the picture is exactly what
# a real screen would show, without one.

. "$(dirname "$0")/harness.env"
harness_running || { echo "the harness isn't running (./start.sh)" >&2; exit 1; }
cd "$HARNESS_DIR" || exit 1
mkdir -p shots
name=${1:-$(date +%H%M%S)}
file=shots/$name.png
if [ -n "$2" ]; then
    ./run.sh grim -g "$2" "$PWD/$file"
else
    ./run.sh grim "$PWD/$file"
fi && echo "$file"
