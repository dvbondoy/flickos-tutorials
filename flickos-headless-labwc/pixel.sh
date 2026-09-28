#!/bin/sh
# pixel.sh: the colour of one pixel of the harness's screen, as #rrggbb.
# A test can check a colour without anyone looking at a picture.
#
#   ./pixel.sh 100 300       e.g. is the open start menu Arc-Dark (#404552)?
#
# grim -t ppm writes the uncompressed PPM format: a short text header
# ("P6", width, height, 255) and then 3 bytes (R, G, B) per pixel. For a
# 1x1 capture the last 3 bytes are the pixel.

. "$(dirname "$0")/harness.env"
[ $# -eq 2 ] || { sed -n '5,6p' "$0"; exit 2; }
harness_running || { echo "the harness isn't running (./start.sh)" >&2; exit 1; }
"$HARNESS_DIR/run.sh" grim -g "$1,$2 1x1" -t ppm - | tail -c 3 | od -An -tx1 | tr -d ' \n' | sed 's/^/#/'
echo
