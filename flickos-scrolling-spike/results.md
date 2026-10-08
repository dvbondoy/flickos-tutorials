# Scrolling tiling spike: results

Phase 0 for a niri-like scrolling mode in flick-tiler, run on 2026-10-08 in a
headless labwc 0.8.3 (pixman renderer) on the dev host (Intel i3-4030U, 4
threads). Your session was never touched: every labwc, window and key press
here ran against `headless.sh`'s own socket.

## Facts

| # | Question | Answer | How it was checked |
|---|---|---|---|
| 1 | Does labwc accept a region left of the screen (x < 0)? | **No.** `Removing invalid region 'r_neg': 50% x 100% @ -25%,0%` | test 1, labwc log |
| 2 | Wider than the screen (width > 100%)? | **No.** `r_wide` removed the same way | test 1 |
| 3 | A region that reaches past the right edge (x 75%, width 50%)? | **Yes.** The window keeps its full size (638 px) and half of it is off the screen | test 1, bbox.py + win.py's size log |
| 4 | A region that starts at the right edge (x = 100%)? | **Yes.** The window is fully off the screen, full size | test 1 |
| 5 | Below the screen (y = 100%)? | **Yes**, fully off the screen | test 4 |
| 6 | Can `MoveTo` / `MoveRelative` put a window past the left edge? | Yes, but **the next reconfigure undoes it**: a region-tiled window goes back to its region, and `MoveRelative` untiles a tiled window (natural size back), which a reconfigure then pulls back onto the screen | test 2 |
| 7 | Does a parked window come back when focused (foreign-toplevel `activate`), minimized and restored, or when the screen mode changes? | **No**, it stays parked in all three cases (regions follow the new mode) | test 3, activate.py |
| 8 | Two screens side by side: where does a window parked at x = 100% go? | **Onto the screen to the right**, and so does the overhang of a peeking column. Parked at y = 100% it shows on neither screen | test 4, OUTPUTS=2 |
| 9 | Does a reconfigure move a parked window to another screen? | No | test 4 |
| 10 | One scroll step by rewriting every region + `labwc --reconfigure` | **80 ms** median (max 196) with a bare rc.xml; **172 ms** median (max 284) with the FlickOS overlay rc.xml (theme, 43 keybinds, menus) | test 5, scroll.py |
| 11 | One scroll step as a labwc keybind: `ForEach tiled_region=PLACE → SnapToRegion NEXT_PLACE` for every place, no reload | **37–39 ms** median (max 69) from key press to the new picture, **of which ~22 ms is wtype starting up**: labwc's part is ~15 ms, the same with the bare and the FlickOS config | test 6, chain.py |
| 12 | Does that chain keep focus and survive a reconfigure? | Yes: its last `ForEach tiled_region=V0 → Focus, Raise` focused the window in view, and a reconfigure kept every window in its place | test 6 |
| 13 | Do windows redraw at a scroll step? | **No.** Every place has the same width, so a step only moves windows. win.py logged no new size after the first snap | win.py logs |
| 14 | One strip per screen with `monitor="current"` in the chain's queries? | **Matched nothing** in 0.8.3 (named screens work: `monitor="HEADLESS-2"` moved only that screen's strip) | test 7 |
| 15 | The chain guarded per screen by `If <query monitor="NAME"/>` around it? | **Did nothing** (perhaps `ForEach` inside `If` isn't run; not investigated) | test 7, cfg/test7-if-monitor.rc.xml |

Not tested: real hardware (GPU renderer, how a 15 ms jump feels), XWayland
windows, apps with a large minimum width in the peek, a screen unplugged
while windows are parked.

## What it means

- A strip like niri's is possible **without minimizing anything**: windows
  outside the view are parked below the screen with regions (fact 5, 7, 8).
- A peek at the **right** edge is possible (fact 3), at the **left** edge it
  isn't (facts 1, 6). With a screen to the right, the peek shows on it (fact 8).
- Scrolling by reloading labwc is too slow to feel like scrolling (fact 10).
  A labwc keybind chain over fixed "place" regions is fast (fact 11) and
  needs no daemon round trip, but every place has a fixed width, so **all
  columns are the same width** (niri lets each column choose its own).
- labwc has no animations: a step is a jump, not a slide.

## Files

- `headless.sh`: start/stop/reload the headless labwc (`OUTPUTS=2` for two screens)
- `win.py`, `fresh.sh`: colored test windows (logs/win-NAME.log has their sizes)
- `bbox.py`: where each colored window is on a grim screenshot
- `activate.py`, `focused.py`: flick-tiler's own foreign-toplevel client: focus/minimize, who is focused
- `scroll.py`: test 5 (reconfigure per step), `chain.py`: tests 6–7 (keybind chain)
- `live.py on [N]|off|status`: phase 0b, the strip in your own session (tiling must be off)
- `cfg/`: the configs of tests 1–2 and 7, and a copy of the session's overlay rc.xml
- `logs/`: labwc log, timing runs
