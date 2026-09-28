# Screenshot and recording spike: results

Date: ____  Machine: see `machine.txt` (`./check-machine.sh > machine.txt`)

Write the **prediction before** each test and the **result after**. Where
they differ, add one line on why. That line is usually the most useful one
in the file.

## Questions

| # | Question | Prediction | Result | Evidence (command, number, file) |
|---|---|---|---|---|
| Q1 | One window on labwc 0.8.3? | | no (pre-filled, check it yourself in step 3) | wayland-info: no `ext_image_copy_capture_manager_v1`; `grim -h`: no `-T`; portal `AvailableSourceTypes = 1` |
| Q2 | Rectangle, screen, one screen, delay? Menu survives until capture? | | | |
| Q3 | swappy good enough? Cost, looks, keyboard? | | | 1.5 MB with fonts-font-awesome |
| Q4 | wf-recorder or portal + GStreamer? | | | step 10 table |
| Q5 | Killed recording still plays? | | | |
| Q6 | Region recording in the right place (x = 1366)? | | | |
| Q7 | Desktop sound, microphone, in sync? | | | |
| Q8 | Anything shows a recording is running? | | | |

## Screenshots (step 6)

| Test | Prediction | Result |
|---|---|---|
| `screen`: ms per shot (PNG) | | 252 ms on 2026-09-27 |
| `screen` as JPEG (`grim -t jpeg`): ms | | |
| `region` on HDMI: x starts near 1366, picture right? | | |
| `region --delay 5` with a menu open: menu in picture? | | |
| `screen --delay 5` with a menu open: menu in picture? | | |
| `output` with one screen on: asks anyway? | | |
| `--copy`: pastes into another app? | | |

## swappy (step 7)

| Snipping Tool | swappy has it? | Notes |
|---|---|---|
| pen, colours | | |
| highlighter | | |
| eraser / undo | | |
| crop | | |
| arrow, rectangle, text | | |
| blur | | |
| copy / save | | |
| Arc-Dark look | | |
| keyboard only | | |

## Recording runs (steps 8 and 9)

Copy the `[measure]` summary line and the "stopped after" line for each.

| Run | Command | CPU avg / high % | PSS MB | MB/min | Plays? | Notes (stutter, sound sync) |
|---|---|---|---|---|---|---|
| R1 | `record-wf.sh screen` (still) | | | | | |
| R2 | `record-wf.sh screen` (moving) | | | | | |
| R3 | `record-wf.sh region --audio` | | | | | |
| R4 | `record-wf.sh screen --mic` | | | | | |
| R5 | `record-wf.sh screen --webm` (moving) | | | | | |
| R6 | `record-wf.sh screen --kill` (MP4) | | | | | |
| R7 | `record-wf.sh screen --webm --kill` | | | | | |
| P1 | `record-portal.py` (still) | | | | | |
| P2 | `record-portal.py` (moving) | | | | | |
| P2b | xdg-desktop-portal-wlr during P2 | | | – | – | |
| P3 | `record-portal.py --region --audio` | | | | | |
| P4 | `record-portal.py --mic` | | | | | |
| P5 | `record-portal.py --kill` | | | | | |

## Comparison (step 10)

| | wf-recorder | portal + GStreamer |
|---|---|---|
| disk | 55 MB (14 packages) | 0.6 MB (0.4 MB without the tools) |
| CPU, moving screen | | |
| memory (PSS) | | |
| MB per minute | | |
| killed file plays? | | |
| region right? | | |
| sound in sync? | | |
| shows it's recording? | | |

**Decision, in one sentence with its numbers:**

## New questions found on the way

-
