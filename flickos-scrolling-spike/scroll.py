#!/usr/bin/python3
"""Time one scroll step the way a scrolling flick-tiler would do it:
./headless.sh run ./scroll.py write OFFSET       write cfg/labwc/rc.xml for that view
./headless.sh run ./scroll.py time LABWC_PID N   N steps there and back, timed

The strip has COLUMNS windows (s1, s2, …), each half the screen wide. The
view shows two columns from OFFSET on, plus PEEK percent of the next one at
the right edge. Columns before the view and after the peek are parked below
the screen (y=100%), where no screen beside it can show them. Every step
rewrites all the regions and reloads labwc once (SIGHUP = labwc --reconfigure),
then polls one pixel with grim until the left column has the expected color.

With BASE=FILE (e.g. cfg/flickos-overlay.rc.xml, a copy of your session's
$XDG_RUNTIME_DIR/flickos/xdg/labwc/rc.xml) the regions and rules go into that
config instead, so labwc reloads FlickOS's theme, keybinds and menus too."""
import os
import pathlib
import signal
import subprocess
import sys
import time

COLUMNS = 6
WIDTH = 50
PEEK = 10
COLORS = ["ff0000", "00ff00", "0000ff", "ffff00", "ff00ff", "00ffff"]
RC = pathlib.Path(__file__).resolve().parent / "cfg/labwc/rc.xml"


def regions(offset):
    lines = []
    for i in range(COLUMNS):
        x = (i - offset) * WIDTH
        if 0 <= x < 100:
            x = min(x, 100 - WIDTH) if x + WIDTH > 100 and x < 100 - PEEK else x
            y = 0
        elif x == 100:                          # the next column peeks in
            x, y = 100 - PEEK, 0
        else:
            x, y = 0, 100                       # parked below the screen
        lines.append(f'    <region name="s{i + 1}" x="{x}%" y="{y}%" width="{WIDTH}%" height="100%" />')
    return "\n".join(lines)


def write(offset):
    rules = "\n".join(f'    <windowRule identifier="s{i + 1}"><action name="SnapToRegion" region="s{i + 1}" /></windowRule>'
                      for i in range(COLUMNS))
    text = f"""<?xml version="1.0"?>
<!-- Test 5 (written by scroll.py): a strip of {COLUMNS} columns, view at column {offset + 1}. -->
<labwc_config>
  <core><gap>0</gap></core>
  <regions>
{regions(offset)}
  </regions>
  <windowRules>
{rules}
  </windowRules>
</labwc_config>
"""
    if os.environ.get("BASE"):
        base = pathlib.Path(os.environ["BASE"]).read_text()
        text = base.replace("</labwc_config>", f"""  <regions>
{regions(offset)}
  </regions>
  <windowRules>
{rules}
  </windowRules>
</labwc_config>""")
    tmp = RC.with_suffix(".tmp")
    tmp.write_text(text)
    os.replace(tmp, RC)


def pixel(x, y):
    out = subprocess.run(["grim", "-g", f"{x},{y} 1x1", "-t", "ppm", "-"], capture_output=True).stdout
    return out[-3:].hex()


def step(pid, offset):
    write(offset)
    start = time.monotonic()
    os.kill(pid, signal.SIGHUP)
    want = COLORS[offset]
    polls = 0
    while pixel(200, 360) != want:
        polls += 1
        if time.monotonic() - start > 3:
            return None, polls
    return (time.monotonic() - start) * 1000, polls


if sys.argv[1] == "write":
    write(int(sys.argv[2]))
else:
    pid, count = int(sys.argv[2]), int(sys.argv[3])
    grim = time.monotonic(); pixel(0, 0); grim = (time.monotonic() - grim) * 1000
    times = []
    for n in range(count):
        offset = (n + 1) % 2 + (n % 4 >= 2) * 2    # 1 0 3 2 1 0 …: steps of one and jumps
        ms, polls = step(pid, offset)
        times.append(ms)
        print(f"view at column {offset + 1}: {'timeout' if ms is None else f'{ms:.0f} ms'} ({polls} polls)")
    done = sorted(t for t in times if t is not None)
    print(f"one grim poll ≈ {grim:.0f} ms; median {done[len(done) // 2]:.0f} ms, max {done[-1]:.0f} ms over {len(done)} steps")
