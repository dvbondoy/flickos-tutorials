#!/usr/bin/python3
"""Try the scrolling strip in your own FlickOS session (phase 0b).

    ./live.py on [N]     open N terminals (default 6) as a strip on your right-most screen
    ./live.py off        close them and put labwc's config back
    ./live.py status     is it on?

How: the strip is chain.py's design, the "places" (V0, V1 in view, P peeking
in at the right edge, L1…/R1… parked below the screen). The fragment goes
where flick-tiler's would, $XDG_RUNTIME_DIR/flickos/tiler/labwc.xml, and
`flickos-layout reconfigure` merges it into your overlay rc.xml like the
tiler's. That slot is free only while tiling is off, so `on` refuses while it
is on. Don't press Super+T during the test: flick-tiler would replace the
fragment with its own (nothing breaks, the strip just ends).

Only the test terminals (foot with app ids scroll-1…N) are in the strip: the
keys move windows tiled to the places, and none of your own windows is. While
on, the fragment's keys replace these for the test only:

    Super+J or Super+Right   scroll right (the next column comes into view)
    Super+K or Super+Left    scroll left

`off` closes the terminals (by the PIDs it started, kept in live.pids),
deletes the fragment only if it is this script's, and reconfigures again, so
Super+Left/Right snap windows to the screen's halves again."""
import json
import os
import pathlib
import subprocess
import sys
import time

SPIKE = pathlib.Path(__file__).resolve().parent
PIDS = SPIKE / "live.pids"
MARK = "<!-- flickos-scrolling-spike live.py -->"
SIDE = 8                                    # parked places per side
VIEW, PEEK = 45, 10                         # column width and the peek, in percent
PLACES = [f"L{i}" for i in range(SIDE, 0, -1)] + ["V0", "V1", "P"] + [f"R{i}" for i in range(1, SIDE + 1)]
RIGHT_KEYS = ("W-j", "W-Right")
LEFT_KEYS = ("W-k", "W-Left")


def fragment_path():
    return pathlib.Path(os.environ["XDG_RUNTIME_DIR"]) / "flickos" / "tiler" / "labwc.xml"


def right_most_screen():
    """The enabled screen with nothing to its right: its peek spills nowhere."""
    screens = [o for o in json.loads(subprocess.run(["wlr-randr", "--json"], capture_output=True,
                                                    text=True, check=True).stdout) if o["enabled"]]
    def right_edge(o):
        mode = next(m for m in o["modes"] if m.get("current"))
        return o["position"]["x"] + mode["width"] / (o.get("scale") or 1)
    return max(screens, key=right_edge)["name"]


def geometry(place):
    """x, y, width in percent; parked places are below the screen."""
    return {"V0": (0, 0, VIEW), "V1": (VIEW, 0, VIEW), "P": (100 - PEEK, 0, VIEW)}.get(place, (0, 100, VIEW))


def shift(step):
    """Every window one place over, starting at the far end so none moves twice."""
    order = range(len(PLACES)) if step < 0 else range(len(PLACES) - 1, -1, -1)
    actions = [f'<action name="ForEach"><query tiled_region="{PLACES[i]}" /><then>'
               f'<action name="SnapToRegion" region="{PLACES[i + step]}" /></then></action>'
               for i in order if 0 <= i + step < len(PLACES)]
    actions.append('<action name="ForEach"><query tiled_region="V0" /><then>'
                   '<action name="Focus" /><action name="Raise" /></then></action>')
    return "\n      ".join(actions)


def fragment(count, screen):
    regions = "\n".join(f'    <region name="{p}" x="{geometry(p)[0]}%" y="{geometry(p)[1]}%" '
                        f'width="{geometry(p)[2]}%" height="100%" />' for p in PLACES)
    start = PLACES.index("V0")
    rules = "\n".join(f'    <windowRule identifier="scroll-{i + 1}"><action name="MoveToOutput" output="{screen}" />'
                      f'<action name="SnapToRegion" region="{PLACES[start + i]}" /></windowRule>'
                      for i in range(count))
    keys = "\n".join(f'    <keybind key="{key}">\n      {shift(step)}\n    </keybind>'
                     for keys, step in ((RIGHT_KEYS, -1), (LEFT_KEYS, 1)) for key in keys)
    return f"""<?xml version="1.0"?>
{MARK}
<labwc_config>
  <regions>
{regions}
  </regions>
  <windowRules>
{rules}
  </windowRules>
  <keyboard>
{keys}
  </keyboard>
</labwc_config>
"""


def ours(pid):
    """True if PID is still a foot this script started."""
    try:
        return pathlib.Path(f"/proc/{pid}/comm").read_text().strip() == "foot"
    except OSError:
        return False


def reconfigure():
    subprocess.run(["flickos-layout", "reconfigure"], check=True)


def on(count):
    path = fragment_path()
    status = json.loads(subprocess.run(["flick-tiler", "status"], capture_output=True, text=True).stdout or "{}")
    if status.get("alt") != "off":
        sys.exit("tiling is on (Super+T turns it off): its fragment is in use")
    if path.exists() and MARK not in path.read_text():
        sys.exit(f"{path} is not this script's; not touching it")
    if not 1 <= count <= SIDE + 3:
        sys.exit(f"N must be 1…{SIDE + 3}")
    screen = right_most_screen()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".spike-tmp")
    tmp.write_text(fragment(count, screen))
    os.replace(tmp, path)
    reconfigure()
    pids = []
    for i in range(1, count + 1):
        text = (f"\\n   Column {i} of {count}\\n\\n   Super+J or Super+Right: scroll right\\n"
                f"   Super+K or Super+Left: scroll left\\n\\n   ./live.py off ends the test\\n\\n")
        pids.append(subprocess.Popen(
            ["foot", f"--app-id=scroll-{i}", f"--title=Column {i}", "bash", "-c", f'printf "{text}"; exec bash'],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True).pid)
        time.sleep(0.15)                    # one at a time, in order
    PIDS.write_text(" ".join(map(str, pids)) + "\n")
    print(f"strip of {count} on {screen}: Super+J/Right and Super+K/Left scroll. End with ./live.py off")


def off():
    pids = PIDS.read_text().split() if PIDS.exists() else []
    for pid in pids:
        if ours(pid):
            os.kill(int(pid), 15)
    PIDS.unlink(missing_ok=True)
    path = fragment_path()
    if path.exists() and MARK in path.read_text():
        path.unlink()
        reconfigure()
        print("fragment removed, labwc reconfigured")
    else:
        print("no fragment of this script (nothing to put back)")


def status():
    path = fragment_path()
    alive = [p for p in (PIDS.read_text().split() if PIDS.exists() else []) if ours(p)]
    print(f"fragment: {'this script' if path.exists() and MARK in path.read_text() else 'not this script'}"
          f", terminals open: {len(alive)}")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "on":
        on(int(sys.argv[2]) if len(sys.argv) > 2 else 6)
    elif command == "off":
        off()
    elif command == "status":
        status()
    else:
        sys.exit(__doc__)
