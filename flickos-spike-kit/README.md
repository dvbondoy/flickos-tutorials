# FlickOS spike kit

> Set `TUTORIALS` to the root of the [tutorials repository](https://github.com/dvbondoy/flickos-tutorials) and `FLICKOS` to your clone of [FlickOS](https://github.com/dvbondoy/FlickOS). Paths below use those two variables. Scripts read the FlickOS checkout from `FLICKOS_REPO` or `FLICKOS`.

A starting folder for **phase 0** of any new FlickOS idea: the short,
throwaway experiment that answers the questions a design can't answer on
paper, before anything is built. For a full worked example with every tool
explained, see `$TUTORIALS/flickos-snip-spike/README.md`.

```
README.md          this page: the process, the tools, the patterns
results.md         the answer sheet: copy it, fill it in as you go
check-machine.sh   what this computer can do (edit the three lists at the top)
try-unpacked.sh    look at a program from a package without installing it
run-measured.sh    start a program, measure it, stop exactly it with Enter
```

Two more tools live **in the FlickOS repo**, because the HIG (PERF-7)
requires their numbers for every feature. The kit calls them from there:

```
tools/package-cost.py PKG…     packages and KB PKG would add to the image
tools/measure.py PID           CPU, PSS/Private memory, wakeups until it exits
```

---

## Starting a spike

```sh
cp -r $TUTORIALS/flickos-spike-kit $HOME/flickos-IDEA-spike
cd $HOME/flickos-IDEA-spike
```

Then go through the steps below. Everything the spike makes stays in that
folder (`debs/`, `unpacked/`, `logs/`, test files), never in the repo, and
never in `~/Pictures`, `~/Desktop` or `~/.config` unless a question needs it.

## The process

1. **Questions first** (results.md). Each one says *why it matters*: what
   in the design changes with the answer. If nothing changes, drop it.
2. **Riskiest first.** The question whose answer could kill or reshape the
   idea goes before the pleasant ones. It's often answerable in minutes
   without code: `wayland-info`, `strings PROGRAM | grep`, `busctl`, a
   package's `apt-cache show`.
3. **Know the machine**: edit the lists at the top of `check-machine.sh`,
   then `./check-machine.sh | tee machine.txt`.
4. **Cost before installing**: `tools/package-cost.py PKG` for every
   candidate package. Measure the whole chain: wf-recorder is 152 KB on its
   own and 57 MB with what it pulls in.
5. **Look before installing**: `./try-unpacked.sh PKG` gets the files and
   says whether the program can start from `unpacked/`. Unpack to look,
   install to measure.
6. **Write a prediction before each test**, then run it. Change one thing
   at a time, and include a control: a case that must work, so "nothing
   happened" means something.
7. **Test in stages.** Make a spike script able to test each half alone
   (`--check` for only the plumbing, `--test` for only the pipeline, as
   `record-portal.py` in the snip spike does), so a failure points at one
   half.
8. **Measure** with `./run-measured.sh` or `tools/measure.py`: with the
   window shown and hidden, idle and busy. Copy the summary lines into
   results.md.
9. **Compare and decide**, in one sentence with its numbers. Look for a
   result that *rules an option out* before weighing the rest.
10. **Clean up** (the checklist at the end of results.md).
11. **Write the results into the design doc**, `docs/design/NAME.md`:
    the status line, *Phase 0 results*, and an ADR per real choice with the
    measured reason. Results that only live in a chat are lost.

---

## The tools

### check-machine.sh

Reads only. Prints FlickOS's package versions, then the three lists you set
at the top:

- `PACKAGES`: installed version or `no` (`dpkg-query -W`).
- `PROTOCOLS`: whether the compositor offers each Wayland protocol
  (`wayland-info`). On Wayland, programs can only do what the compositor
  offers: screenshots, window lists, panels and more are all protocols.
- `DBUS_PROPERTIES`: `service object interface property` per line, read
  with `busctl --user get-property`. The portals, NetworkManager and
  logind answer this way.

Then screens (`wlr-randr`: position and scale matter for anything that
draws or captures), CPU, memory and graphics (`lspci`).

### try-unpacked.sh PKG…

`apt-get download` (no sudo) into `debs/`, `dpkg-deb -x` into `unpacked/`,
then `ldd` on every program with `LD_LIBRARY_PATH=unpacked/usr/lib/…` to
list libraries it can't find. Run a program that can start with the same
`LD_LIBRARY_PATH`. Limits: programs that need their data in `/usr/share`,
a D-Bus service or a daemon won't work unpacked. Install those (and remove
them at the end).

### run-measured.sh [--int | --kill] [--tree] -- COMMAND…

Starts COMMAND with its output in `logs/`, runs `tools/measure.py` on it,
and stops it when you press Enter:

- default **SIGTERM**: a normal stop,
- `--int` **SIGINT**, like Ctrl+C: programs that write files (recorders,
  encoders) finish them properly on this one,
- `--kill` **SIGKILL**: can't be caught, so it's what a crash looks like.
  Use it to test what a crash leaves behind.
- `--tree`: measure the processes it starts too.

Two details that cost time to find, both handled by the script:

- It starts COMMAND in **its own process group** (`setsid`) and signals the
  whole group (`kill -s SIG -- -PID`), because a signal to one PID doesn't
  reach its children. In dash, `kill -SIG -- -PID` fails. Only the
  POSIX form `kill -s SIG -- -PID` works in both dash and bash.
- A shell starts background programs with **SIGINT ignored** (POSIX), so
  `kill -INT` does nothing to many of them (Python never raises
  KeyboardInterrupt). `env --default-signal=INT,QUIT` puts the default
  back. The same applies *inside* a program that's a shell script: its own
  `cmd &` children ignore SIGINT, so stop those families with the default
  SIGTERM.

### tools/package-cost.py (in the repo)

`apt-get install -s --no-install-recommends` (a simulation, no sudo), the
way the image installs packages, compared with the **image**: the last
build's `flickos-amd64.packages` becomes a pretend dpkg status file. So
what your own computer happens to have doesn't hide a cost. Without that
list (after `lb clean`) or with `--host`, it compares with this computer and
says so. It takes local `.deb` files too, for a FlickOS package you're
building.

### tools/measure.py (in the repo)

Reads only `/proc`: CPU from `/proc/PID/stat`, PSS and Private from
`/proc/PID/smaps_rollup`, wakeups from the voluntary context switches in
`/proc/PID/task/*/status`. PSS is the fair memory number (shared libraries
count by share), and Private is what closing the program would free.
`--tree` adds its children, `-- COMMAND` starts it, `--for S` stops
measuring after S seconds.

---

## Patterns worth copying into a spike script

```sh
cmd & pid=$!                 # start, keep exactly its PID
kill -s INT $pid; wait $pid  # stop exactly it, and wait until it's gone
```

```python
proc = subprocess.Popen([...])          # keep proc.pid
proc.send_signal(signal.SIGINT)
proc.wait(timeout=15)                   # then proc.kill() if it hangs
```

- **Never `pkill NAME` or `pkill -f PATTERN`** on your own FlickOS session:
  it also hits the desktop's own copies (your Print key runs grim, your
  panel runs waybar). And `pkill -f` matches your own shell's command line.
- **Log with timestamps** in anything that runs longer than a few seconds.
  Regular gaps in a log (every 5 s exactly) point at a timer in your own
  code.
- **Portals and other D-Bus requests**: subscribe to the answer *before*
  calling (see `request()` in the snip spike's `record-portal.py`).
- **A test that shows something on screen, or needs your mouse, is yours
  to run**, not a script's.

## Commands worth keeping

| Command | For |
|---|---|
| `wayland-info \| grep NAME` | what the compositor offers |
| `strings PROGRAM \| grep NAME` | what a program knows about, without running it |
| `nm -D --undefined-only LIB` | which functions a library calls from others |
| `busctl --user introspect SERVICE OBJECT` | the methods and properties of a D-Bus object |
| `apt-cache depends` / `rdepends --installed PKG` | why a package comes in / who here needs it |
| `apt-get download PKG; dpkg-deb -c FILE.deb` | what's in a package |
| `ldd PROGRAM` | which libraries it needs, and which are missing |
| `grep -E '^NAME\b' flickos-amd64.packages` (repo) | is it in the image |
| `ss -lntup` | who listens on which port |
| `wpctl status` | sound devices |
| `top -p PID` | quick look at one process |
