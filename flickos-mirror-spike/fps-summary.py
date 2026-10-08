#!/usr/bin/env python3
"""fps-summary.py LOG...: sum up scrcpy's --print-fps lines.

scrcpy prints one line a second: "INFO: 22 fps (+15 frames skipped)".
Shown frames reached the screen; skipped frames were decoded but replaced by
a newer one before they could be drawn. That means the computer was too slow
only while the shown fps is low: when the phone sends more frames a second
than the screen shows (a 90 Hz phone, a 60 Hz screen), frames are skipped
however fast the computer is. Compare the shown fps first. Seconds with
nothing at all (the phone sent no frame because nothing moved) are left out
of the average.
"""
import re
import sys

LINE = re.compile(r"INFO: (\d+) fps(?: \(\+(\d+) frames skipped\))?")


def summary(path):
    seconds = []
    with open(path, errors="replace") as f:
        for line in f:
            m = LINE.search(line)
            if m:
                seconds.append((int(m[1]), int(m[2] or 0)))
    moving = [(shown, skipped) for shown, skipped in seconds if shown or skipped]
    if not moving:
        return f"{path}: no fps lines with frames"
    shown = sum(s for s, _ in moving)
    skipped = sum(k for _, k in moving)
    smooth = sum(1 for s, _ in moving if s >= 20)
    return (f"{path}: {len(moving)} s with frames: average {shown / len(moving):.1f} fps, "
            f"best {max(s for s, _ in moving)}, {smooth} s at >= 20 fps, "
            f"{skipped} of {shown + skipped} frames skipped ({100 * skipped / (shown + skipped):.0f}%)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for p in sys.argv[1:]:
        print(summary(p))
