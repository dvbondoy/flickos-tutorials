# SPIKE NAME: results

Date: ____  Design doc: `docs/design/____.md`  Machine: `machine.txt`

Write the **prediction before** each test and the **result after**. Where
they differ, add one line on why.

## Questions

Riskiest first. Each question says why it matters: what in the design
changes with the answer.

| # | Question | Why it matters | Prediction | Result | Evidence (command, number, file) |
|---|---|---|---|---|---|
| Q1 | | | | | |
| Q2 | | | | | |
| Q3 | | | | | |

## Cost (HIG PERF-7)

| What | Number | How measured |
|---|---|---|
| disk: packages and KB added to the image | | `tools/package-cost.py PKG…` |
| memory: PSS / Private, window shown | | `tools/measure.py` or `./run-measured.sh` |
| memory: PSS / Private, window hidden or idle | | |
| CPU while idle, wakeups a minute | | |
| time: start → first frame, or effect on login | | |

## Runs

Copy the `[measure]` summary line for each.

| Run | Command | Prediction | Result | Notes |
|---|---|---|---|---|
| | | | | |

## Options compared

| | Option A | Option B |
|---|---|---|
| disk | | |
| CPU | | |
| memory | | |
| HIG problems | | |
| code to write | | |

**Decision, in one sentence with its numbers:**

## New questions found on the way

-

## Cleanup done

- [ ] `sudo apt purge …` then `sudo apt autoremove --purge` (list read first)
- [ ] test files, `debs/`, `unpacked/`, `logs/` deleted
- [ ] anything written to `~/.config` or `~/Desktop` by a tried program deleted
- [ ] results written into the design doc
