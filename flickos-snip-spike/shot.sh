#!/bin/sh
# shot.sh: every screenshot mode a Snipping Tool needs, with grim and slurp.
# Pictures go into ./shots/ (not ~/Pictures), so the spike leaves no mess.
#
#   ./shot.sh region            drag a rectangle (Esc cancels)
#   ./shot.sh screen            every screen
#   ./shot.sh output            click the screen you want
#   ./shot.sh region --delay 5  wait 5 s first (open a menu meanwhile)
#   ./shot.sh region --edit     open the picture in swappy to draw on it
#   ./shot.sh region --copy     to the clipboard instead of a file

cd "$(dirname "$0")" || exit 1
mode=$1; shift 2>/dev/null
delay=0 edit=no copy=no
while [ $# -gt 0 ]; do
    case $1 in
        --delay) delay=$2; shift ;;
        --edit)  edit=yes ;;
        --copy)  copy=yes ;;
        *) echo "unknown option $1" >&2; exit 2 ;;
    esac
    shift
done
case $mode in region|screen|output) ;; *) sed -n '5,10p' "$0"; exit 2 ;; esac

# The delay comes before choosing, as in the Snipping Tool: that is what
# lets you open a menu or a tooltip and then capture it.
while [ "$delay" -gt 0 ]; do
    printf '\r%s… ' "$delay"; sleep 1; delay=$((delay - 1))
done
echo

# Choosing is the user's part; its time doesn't count.
case $mode in
    region) where=$(slurp) || { echo "cancelled"; exit 1; }
            set -- -g "$where" ;;
    output) where=$(slurp -o -f %o) || { echo "cancelled"; exit 1; }
            set -- -o "$where" ;;
    screen) set -- ;;
esac

mkdir -p shots
file=shots/$(date +%Y%m%d-%H%M%S)-$mode.png
start=$(date +%s%N)
if [ $copy = yes ]; then
    grim "$@" - | wl-copy --type image/png
    what="clipboard"
else
    grim "$@" "$file"
    what=$file
fi
end=$(date +%s%N)
echo "captured ${where:+$where }in $(( (end - start) / 1000000 )) ms -> $what"

if [ $edit = yes ] && [ $copy = no ]; then
    swappy=$(command -v swappy) || swappy=unpacked/usr/bin/swappy
    [ -x "$swappy" ] || { echo "swappy isn't installed or unpacked (see step 5)"; exit 1; }
    # -o: when swappy closes, the drawn-on picture is written there too.
    LD_LIBRARY_PATH=unpacked/usr/lib/x86_64-linux-gnu \
        "$swappy" -f "$file" -o "${file%.png}-edited.png"
    [ -s "${file%.png}-edited.png" ] && echo "edited -> ${file%.png}-edited.png"
fi
