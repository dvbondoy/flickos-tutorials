#!/usr/bin/python3
"""Test 6: scroll without reloading labwc.
./headless.sh run ./chain.py write [BASE]   write cfg/labwc/rc.xml
./headless.sh run ./chain.py time N         N key presses (wtype), timed

Every place in the strip is a fixed region: L1…L{SIDE} parked to the left,
V0 and V1 in view, P peeking in at the right edge, R1…R{SIDE} parked to the
right (parked = below the screen, y=100%). Super+Right (here XF86Launch5,
pressed by wtype as a virtual keyboard) moves every window one place to the
left with ForEach tiled_region=… → SnapToRegion …, starting at the far end
so no window is moved twice. Nothing is reloaded. Super+Left (XF86Launch6)
is the same the other way. A window then focuses the one in V0.

With MONITORS=1 every query also has monitor="current" (only the focused
screen's strip moves), and windows t1…t3 open on HEADLESS-1 (two screens:
OUTPUTS=2 ./headless.sh start)."""
import os
import pathlib
import subprocess
import sys
import time

SIDE = 8
COLORS = ["ff0000", "00ff00", "0000ff", "ffff00", "ff00ff", "00ffff"]
RC = pathlib.Path(__file__).resolve().parent / "cfg/labwc/rc.xml"
PLACES = [f"L{i}" for i in range(SIDE, 0, -1)] + ["V0", "V1", "P"] + [f"R{i}" for i in range(1, SIDE + 1)]
GEOMETRY = {"V0": (0, 0, 45), "V1": (45, 0, 45), "P": (90, 0, 45)}   # x, y, width in percent


MONITOR = ' monitor="current"' if os.environ.get("MONITORS") else ""


def shift(step):
    """Actions moving every window `step` places (-1: to the left = scroll right)."""
    order = range(len(PLACES)) if step < 0 else range(len(PLACES) - 1, -1, -1)
    actions = []
    for i in order:
        j = i + step
        if 0 <= j < len(PLACES):
            actions.append(f'<action name="ForEach"><query tiled_region="{PLACES[i]}"{MONITOR} /><then>'
                           f'<action name="SnapToRegion" region="{PLACES[j]}" /></then></action>')
    actions.append(f'<action name="ForEach"><query tiled_region="V0"{MONITOR} /><then><action name="Focus" />'
                   '<action name="Raise" /></then></action>')
    return "\n      ".join(actions)


def write(base=None):
    regions = "\n".join(
        f'    <region name="{p}" x="{GEOMETRY.get(p, (0, 100, 45))[0]}%" y="{GEOMETRY.get(p, (0, 100, 45))[1]}%" '
        f'width="{GEOMETRY.get(p, (0, 100, 45))[2]}%" height="100%" />' for p in PLACES)
    start = ["V0", "V1", "P", "R1", "R2", "R3"]
    rules = "\n".join(f'    <windowRule identifier="s{i + 1}"><action name="SnapToRegion" region="{p}" /></windowRule>'
                      for i, p in enumerate(start))
    if MONITOR:
        rules += "\n" + "\n".join(
            f'    <windowRule identifier="t{i + 1}"><action name="MoveToOutput" output="HEADLESS-1" />'
            f'<action name="SnapToRegion" region="{p}" /></windowRule>' for i, p in enumerate(start[:3]))
    body = f"""  <regions>
{regions}
  </regions>
  <windowRules>
{rules}
  </windowRules>
  <keyboard>
    <keybind key="XF86Launch5">
      {shift(-1)}
    </keybind>
    <keybind key="XF86Launch6">
      {shift(1)}
    </keybind>
    <keybind key="XF86Launch7"><action name="None" /></keybind>
  </keyboard>
</labwc_config>"""
    text = (pathlib.Path(base).read_text().replace("</labwc_config>", body) if base else
            f'<?xml version="1.0"?>\n<labwc_config>\n  <core><gap>0</gap></core>\n{body}\n')
    RC.write_text(text)


def pixel(x, y):
    out = subprocess.run(["grim", "-g", f"{x},{y} 1x1", "-t", "ppm", "-"], capture_output=True).stdout
    return out[-3:].hex()


def press(key, want):
    start = time.monotonic()
    subprocess.run(["wtype", "-k", key], check=True)
    pressed = time.monotonic()
    while want and pixel(200, 360) != want:
        if time.monotonic() - start > 3:
            return None, 0
    return (time.monotonic() - start) * 1000, (pressed - start) * 1000


if sys.argv[1] == "write":
    write(sys.argv[2] if len(sys.argv) > 2 else None)
else:
    count = int(sys.argv[2])
    _, wtype_ms = press("XF86Launch7", None)
    print(f"wtype alone (key bound to nothing): {wtype_ms:.0f} ms")
    left, times = 0, []                      # index of the window in V0
    for n in range(count):
        right = (n // 3) % 2 == 0            # three steps right, three back
        left += 1 if right else -1
        ms, wt = press("XF86Launch5" if right else "XF86Launch6", COLORS[left])
        times.append(ms)
        print(f"{'right' if right else 'left '} → s{left + 1} in view: "
              f"{'timeout' if ms is None else f'{ms:.0f} ms'} (wtype {wt:.0f} ms)")
    done = sorted(t for t in times if t is not None)
    print(f"median {done[len(done) // 2]:.0f} ms, max {done[-1]:.0f} ms over {len(done)} steps, {len(times) - len(done)} timeouts")
