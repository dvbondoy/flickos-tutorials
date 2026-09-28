#!/bin/sh
# demo.sh: the whole round trip once, with nothing to do but watch the
# terminal: start the harness, open a terminal in it, type, take pictures,
# check a colour, stop. Compare shots/ with reference/ afterwards.
#
#   ./demo.sh             plain labwc with foot
#   ./demo.sh --flickos   the FlickOS desktop, then Super to open the start menu

cd "$(dirname "$0")" || exit 1
set -e
step() { printf '\n== %s\n' "$1"; }

step "start the harness"
if [ "$1" = --flickos ]; then
    ./start.sh --flickos
    sleep 6                          # autostart: wallpaper, panel, menu daemon …

    step "the desktop"
    ./shot.sh demo-desktop
    printf 'panel colour at (200, 755): '; ./pixel.sh 200 755

    step "tap Super: press, hold 150 ms, release"
    # -P/-p press/release a key, -M/-m a modifier, -s waits (ms).
    ./run.sh wtype -P Super_L -M logo -s 150 -m logo -p Super_L
    sleep 1.5
    ./shot.sh demo-menu
    printf 'menu colour at (100, 300): '; ./pixel.sh 100 300
else
    ./start.sh

    step "open foot inside and remember its PID"
    ./run.sh foot &
    foot=$!
    sleep 2
    echo "foot is PID $foot"

    step "type a command into it"
    ./run.sh wtype 'echo hello from the harness'
    ./run.sh wtype -k Return
    sleep 1
    ./shot.sh demo-foot
fi

step "stop (the files stay in \$HL until ./stop.sh --clean)"
./stop.sh
echo
echo "look at the pictures: xdg-open shots/   (compare with reference/)"
