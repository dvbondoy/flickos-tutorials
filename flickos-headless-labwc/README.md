# Testing in a headless labwc, step by step

> Set `TUTORIALS` to the root of the [tutorials repository](https://github.com/dvbondoy/flickos-tutorials) and `FLICKOS` to your clone of [FlickOS](https://github.com/dvbondoy/FlickOS). Paths below use those two variables. Scripts read the FlickOS checkout from `FLICKOS_REPO` or `FLICKOS`.

A **headless** labwc is a real labwc with no screen, keyboard or mouse. It
draws into memory instead. Programs connect to it like to any compositor,
and you look at the result with screenshots, drive it with a virtual
keyboard and mouse, and measure it. This folder is a small harness for that,
and this guide explains every piece, including the traps found while
building it (section 8), so you can build or fix such a thing yourself.

```
README.md            this guide
get-input-tools.sh   once: fetch wtype (keyboard) and wlrctl (mouse), no install
harness.env          the shared settings and functions (read this one)
start.sh             start the harness: plain labwc, or the whole FlickOS session
run.sh               run a program inside it
shot.sh              screenshot → shots/
pixel.sh             one pixel's colour
stop.sh              stop it (--clean: delete its files too)
first-frame.py       time from start to first drawn window (HIG PERF-1)
demo.sh              the whole round trip, to watch once
reference/           what the demos should look like (1366×768)
```

---

## 0. Do I still need this, now that I'm on FlickOS?

Less often than before, but yes. You now have four ways to test, and each
is best at something:

| Way | Best for | Can't do |
|---|---|---|
| **Your own FlickOS session** (build the .deb, `sudo apt install`, reload) | how it looks and feels: your screen, apps, theme, real hardware | anything that would disturb your work: logging in again, many key presses, a clean first login, measurements while you use the computer |
| **Headless harness** (this folder) | repeatable checks with no one watching: screenshots, pixel checks, key presses and clicks, start times, a clean new account, a fixed 1366×768 screen, trying a change before building a package | real hardware (GPU, sound, touchpad), how it *feels* |
| **QEMU** (`tools/test-iso.sh`) | the whole ISO: boot, installer, login screen, a real install | quick iterations (a build takes 30–50 min) |
| **Boot test** (`tools/boot-test.py`, CI) | "does the image still boot and run" after every change | anything interactive |

Rules of thumb:

- Use the **harness** whenever a check should run the same way every time,
  or would press keys and open windows you don't want on your screen. The
  HIG also asks for start times to be measured there (PERF-9), because your
  own desktop's load changes the numbers.
- Use **your session** for the final look, and whenever the harness can't
  have the thing (sound, GPU, Bluetooth, the real network).
- Use **QEMU** for anything about the image itself.

---

## 1. The idea, and what "isolated" means

A Wayland compositor listens on a **socket**, a file like
`$XDG_RUNTIME_DIR/wayland-0`. A program finds it through two variables,
`XDG_RUNTIME_DIR` and `WAYLAND_DISPLAY`. So a second compositor with its own
runtime folder is a second, separate desktop, and a program goes to
whichever one those variables point at.

**wlroots** (the library labwc is built on) has *backends* that decide where
the picture goes. On a normal login it's `drm` (the graphics card). With
`WLR_BACKENDS=headless` it's memory. `WLR_RENDERER=pixman` draws on the CPU,
so no GPU is needed, and `WLR_HEADLESS_OUTPUTS=1` makes one virtual screen
called `HEADLESS-1`.

The hard part is keeping the harness from touching your real desktop. This
is what separates them:

| Layer | How | Why it's needed |
|---|---|---|
| display | its own runtime folder `$HL/run` with its own `wayland-0` | windows go to the harness, not your screen |
| environment | built from nothing with `env -i` (`harness_env` in `harness.env`) | your terminal has `LABWC_PID=` your real labwc (so `labwc --reconfigure` would reload **your** desktop), `XDG_CONFIG_DIRS` with your real layout overlay, your session bus address… |
| D-Bus | its own session bus (`dbus-daemon --session`) at `$HL/run/bus` | notifications, portals, the settings database (dconf) and single-instance checks would otherwise go to your real session |
| files | its own `HOME` (`$HL/home`) and `XDG_*_HOME` | settings a test changes don't end up in your `~/.config` |
| processes | a PID namespace (`unshare --pid`) | FlickOS programs find each other by name: labwc's Super key runs `pkill -x flickos-menu`, the tiler signals `waybar` by name. Inside the namespace your real ones don't exist |
| X11 | its own empty `/tmp/.X11-unix` (a mount namespace) | XWayland refuses the real one inside the namespace (section 8) |

**Not** isolated, and worth knowing:

- the **system** D-Bus (NetworkManager, logind, polkit, Bluetooth) and the
  network: a test that changes system settings changes them for real;
- files outside the harness's home, like `/tmp` and anything a program
  writes by absolute path;
- programs started with `./run.sh` run *outside* the namespace (they only
  connect to it), so their own `pkill`s are not contained. Programs the
  session starts (autostart) are inside;
- your real session's `pkill -x NAME` can still reach harness processes.
  That's harmless for your desktop, but a test might see an extra signal.

---

## 2. Set up once

```sh
cd $TUTORIALS/flickos-headless-labwc
./get-input-tools.sh
```

The harness has no real keyboard or mouse. **wtype** makes a virtual
keyboard (`zwp_virtual_keyboard_v1`) and **wlrctl** a virtual pointer
(`zwlr_virtual_pointer_v1`). Both are small trixie packages that aren't
installed, so the script downloads and unpacks them into `tools/`, the same
`apt-get download` + `dpkg-deb -x` as `try-unpacked.sh` in the spike kit.
`harness_env` puts `tools/usr/bin` first on `PATH`.

Everything else is already on FlickOS: labwc, foot, grim, wlr-randr,
wayland-info, dbus-daemon, util-linux's `unshare`, ImageMagick.

---

## 3. First run: watch the demo

```sh
./demo.sh              # plain labwc + foot + typing + screenshot
./demo.sh --flickos    # the FlickOS desktop + Super → start menu
xdg-open shots/        # compare with reference/
```

Nothing appears on your screen. That's the point. What happens, step by
step (read `demo.sh` alongside):

1. `./start.sh` starts labwc headless, waits for its socket, and sets the
   screen to 1366×768 with `wlr-randr --output HEADLESS-1 --custom-mode`.
2. `./run.sh foot &` opens foot *inside*. `$!` is foot's PID, because
   `run.sh` `exec`s into the program (section 8, "`$!` of a function").
3. `./run.sh wtype 'echo hello…'` types into the focused window, and
   `wtype -k Return` presses a named key.
4. `./shot.sh demo-foot` takes the picture.
5. `./stop.sh` stops labwc. Everything inside the namespace goes with it,
   and foot, which only connected from outside, exits because its display
   is gone. That's the `Broken pipe` lines. The harness's files stay in
   `$HL` until `./stop.sh --clean`.

In `--flickos` mode, `start.sh` runs `flickos-session` instead of plain
labwc: the same script the login screen runs, so everything the installed
packages start at login starts here (wallpaper, panel, start menu daemon,
tiler, shortcuts, notifications…). `pixel.sh 100 300` after the Super tap
prints `#404552`, the Arc-Dark menu colour, so the menu opened, and a test
can check that without anyone looking.

---

## 4. The scripts, one by one

### harness.env

Read it first; the rest is small. It sets:

- `HL`: where everything lives, by default `$XDG_RUNTIME_DIR/harness`
  (`/run/user/1000/harness`), a RAM folder emptied at logout. Override it
  with `HL=/some/short/path ./start.sh`. It **must be short**, because a
  socket's full path must fit in 108 bytes.
- `harness_env CMD…`: runs CMD with the harness's environment, built from
  nothing (`env -i`) plus only what's needed.
- `harness_pids NAME`: the PIDs of processes called NAME **that belong to
  the harness**. It reads each candidate's `/proc/PID/environ` and keeps the
  ones whose `XDG_RUNTIME_DIR` is the harness's. That's how you find "the
  harness's waybar" when your real one has the same name. Use it in your
  shell: `. ./harness.env; harness_pids waybar`.

### start.sh

```sh
./start.sh                          # plain labwc: empty config (-C), starts nothing
./start.sh --flickos                # flickos-session: the whole FlickOS desktop
./start.sh --flickos --first-login  # with /etc/skel copied into the home: a new account
./start.sh --size 1920x1080         # another screen size (default 1366x768, the HIG's)
```

Read its comments from "The pieces, outside in". The command is a chain
where each program sets something up and then runs the next:

```
harness_env WLR_BACKENDS=headless …        a clean environment, headless wlroots
  setsid                                   own process group, detached from the terminal
    unshare --user --map-root-user         a user namespace: "root" inside it only
            --mount --pid --fork           own mounts, own process numbers
            --mount-proc --kill-child      own /proc; unshare's death ends it all
      sh -c 'mount -t tmpfs … /tmp/.X11-unix     (allowed: we're "root" in here)
             exec unshare --user --map-user=1000 …   back to being you
               sh -c "dbus-daemon … &  wait for its socket;  labwc -C … | flickos-session"'
```

**Plain** mode is for testing one program on its own: labwc with its
built-in defaults and nothing else running. **FlickOS** mode is for testing
how something fits into the real desktop.

### run.sh

```sh
./run.sh PROGRAM ARGS…      # run inside; add & for windows
./run.sh sh                 # a shell whose programs all go to the harness
```

It uses `harness_env` plus `WAYLAND_DISPLAY`, the **harness's** `LABWC_PID`
(as your shell sees it: inside the namespace labwc has another number),
and the `XDG_CONFIG_DIRS`/`XDG_DATA_DIRS` flickos-session sets, with the
harness's layout overlay first. So FlickOS's own commands work on the
harness: `./run.sh flickos-layout set cupertino` changes the *harness's*
layout.

### shot.sh and pixel.sh

```sh
./shot.sh                              # shots/HHMMSS.png
./shot.sh after-change                 # shots/after-change.png
./shot.sh panel "0,728 1366x40"        # only a rectangle: X,Y WxH
./pixel.sh X Y                         # #rrggbb
```

**grim** asks labwc for a copy of the screen through
`zwlr_screencopy_manager_v1`, the same way your Print key does. In the
harness that "screen" is labwc's memory, so the picture is exactly what a
monitor would show. `pixel.sh` asks grim for a 1×1 picture in **PPM**, the
simplest image format (a text header, then 3 bytes R, G, B per pixel), and
prints the last 3 bytes as hex.

### stop.sh

Stops **labwc** with SIGTERM. When labwc exits, the namespace's first
process ends, and the kernel ends every other process in the namespace. If
that doesn't work within 5 seconds, it SIGKILLs the first process. Then it
lists any programs still running with the harness's settings (ones you
started with `run.sh` that didn't notice). Section 8 explains why it can't
simply stop `unshare`.

---

## 5. Looking at the results

**Open them:** `xdg-open shots/NAME.png`. When I (Claude) test in a harness,
I do the same thing: take a screenshot with grim, then *read the PNG file*
(I can see images), and describe or compare what's there. That's all
"looking at the screen" means for a program.

**Compare two pictures:** ImageMagick's `compare` counts the pixels that
differ and can draw a diff image:

```sh
compare -metric AE shots/before.png shots/after.png shots/diff.png   # AE = absolute error: count
compare -metric AE -fuzz 2% …                                         # ignore tiny colour differences
```

The demo's foot picture matches `reference/plain-foot.png` exactly
(0 pixels). The start menu picture differs by about 40 pixels, from the
**clock** and the **blinking text cursor**. Anything that changes by itself
has to be left out of a comparison: capture a rectangle without it
(`shot.sh NAME "X,Y WxH"`), or check a few pixels instead of the whole
picture.

**Check without pictures:** `pixel.sh` for colours; `./run.sh wayland-info`
for what the compositor offers; and `wlrctl toplevel find` for "is this
window open?", which answers with its exit status, so a script can test it:

```sh
./run.sh wlrctl toplevel find app_id:foot && echo open
./run.sh wlrctl toplevel waitfor title:'Welcome to FlickOS'   # wait until it opens
```

The rules are `app_id:`, `title:` and `state:` (`maximized`, `active`,
`-fullscreen` …); give several and all must match.

**Logs:** `$HL/log/session.log` has everything labwc and the session print.
In FlickOS mode the panel's own log is `$HL/run/flickos/panel.log`.

---

## 6. Driving it: keyboard and mouse

**wtype** (keyboard):

```sh
./run.sh wtype 'some text'                 # type text
./run.sh wtype -k Return                   # a named key (xkb names: Escape, Tab, Left, F1 …)
./run.sh wtype -M ctrl -k l -m ctrl        # Ctrl+L: -M holds a modifier, -m lets go
./run.sh wtype -P Super_L -M logo -s 150 -m logo -p Super_L   # tap Super: press, wait 150 ms, release
```

`-P`/`-p` press and release a key, `-M`/`-m` a modifier (`logo` is Super),
`-s MS` waits. The Super tap needs both: labwc tracks the *modifier* for
the "Super alone" rule and the *key* for the `onRelease` keybind.

**wlrctl** (mouse and windows):

```sh
./run.sh wlrctl pointer move -3000 -3000   # far to the top-left: now at 0,0
./run.sh wlrctl pointer move 18 752        # then to the start button
./run.sh wlrctl pointer click left         # click (right, middle too)
./run.sh wlrctl pointer scroll 10 0        # scroll
./run.sh wlrctl toplevel focus app_id:foot # focus a window (also minimize, maximize, fullscreen)
./run.sh wlrctl toplevel find title:Settings   # exit status 0 if such a window exists
```

The virtual pointer only moves **relative** to where it is, so first push it
against the top-left corner, and then every move is from 0,0.

---

## 7. Recipes

**Try a change before building a package.** In FlickOS mode the installed
programs run. Stop the harness's copy by PID and start yours from the repo:

```sh
./start.sh --flickos
. ./harness.env
kill $(harness_pids flickos-menu)          # the harness's, never yours
./run.sh $FLICKOS/packages/flickos-menu/usr/bin/flickos-menu daemon &
```

Run a daemon as its own file, not `python3 file`, because FlickOS finds
daemons by process name (`pkill -x flickos-menu`), and under `python3` the
name would be `python3`. flickos-layout's `supervise` leaves a killed
program alone (it only restarts ones that *failed*), so yours isn't
replaced. Remember that one started with `run.sh` runs outside the
namespace (section 1).

**A layout change, before and after:**

```sh
./shot.sh before
./run.sh flickos-layout set cupertino
sleep 3; ./shot.sh after
compare -metric AE shots/before.png shots/after.png shots/diff.png
```

**A new account's first login** (Welcome window, first-run markers from
`/etc/skel`):

```sh
./start.sh --flickos --first-login
./run.sh wlrctl toplevel waitfor title:'Welcome to FlickOS'
./shot.sh first-login
```

On 2026-09-27 this showed the Welcome window with its last row of cards
(*Support FlickOS*, *Donate*) cut off at 1366×768, so the window scrolls. A
harness screenshot at the HIG's target size catches that kind of thing
without a 1366×768 laptop.

**Start time (HIG PERF-1: ≤ 1 s to the first frame):**

```sh
./run.sh ./first-frame.py /usr/bin/flickos-control
```

`first-frame.py` runs the program the way `python3 PROGRAM` would, but
first wraps GTK's `show`, `show_all` and `present` so the first `draw` of
any window prints the time since the process started. Run it 3 times and
use the later numbers (the first reads from disk). On 2026-09-27 in
FlickOS mode on your i3 it printed **Settings 1160–1190 ms**
(the HIG's table says 0.6 s, measured on an earlier, faster host) and
**Welcome 600 ms**. So Settings may be over budget on the target kind of
laptop. It's worth a look.

**Memory of something in the harness:**

```sh
. ./harness.env
$FLICKOS/tools/measure.py $(harness_pids waybar)
```

**Another screen:**
`./run.sh wlr-randr --output HEADLESS-1 --custom-mode 1920x1080` or
`--scale 1.25` (fractional scaling bugs show up here).

---

## 8. Traps found while building this

Each of these cost time, and each teaches something general.

1. **Socket paths are limited to 108 bytes.** A harness under a long
   folder name fails with a vague error. Hence the short `$HL`.
2. **Your environment leaks.** Anything started from your terminal
   inherits `LABWC_PID` (your real labwc: `labwc --reconfigure` would
   reload your desktop), `XDG_CONFIG_DIRS` (your real layout overlay),
   `DBUS_SESSION_BUS_ADDRESS`, `DISPLAY`… Removing variables one by one
   always misses one. **Start from `env -i` and add what's needed.**
3. **FlickOS programs signal each other by name** (`pkill -x flickos-menu`,
   `pkill -x fuzzel`, `pkill … -x waybar`). A second FlickOS session as the
   same user would open *your* start menu when the harness's Super key is
   tapped. Hence the PID namespace. On your machine
   (`unshare --user --pid …`) it needs no root.
4. **XWayland in a user namespace.** wlroots checks that `/tmp/.X11-unix`
   is owned by root or by you. Inside a user namespace the real root is
   unmapped, so the folder looks owned by `nobody`, and labwc wouldn't
   start. Fix: a mount namespace with an empty tmpfs there. That needs
   "root" in the namespace (`--map-root-user`), so a second, nested
   `unshare --map-user=1000` makes you yourself again. XWayland then says
   `Failed to bind … X0: Address already in use`: X also uses *abstract*
   sockets, which aren't per mount namespace, so it takes `:1`. That's
   harmless.
5. **`unshare --fork` ignores SIGTERM and SIGINT**, and a namespace's
   **first process ignores every signal it has no handler for**. So
   `kill UNSHARE_PID` does nothing. Stop the program that handles SIGTERM
   (labwc), or SIGKILL the first process. The first version of `stop.sh`
   said "stopped" and stopped nothing, because it didn't check. **Always
   check that a stop worked.**
6. **`$!` of a backgrounded shell function** is a subshell's PID, not the
   program's. Make the function `exec` (`HARNESS_EXEC=exec`), so the
   subshell *becomes* the program.
7. **Process names are cut to 15 characters.** `pgrep -x flickos-shortcuts`
   finds nothing; the kernel's name is `flickos-shortcu`. `harness_pids`
   cuts the name the same way.
8. **Errors to stderr.** `pixel.sh` once turned "the harness isn't running"
   into a colour, because the message went to stdout, into the pipe.
9. **In dash, `cmd <file 2>/dev/null` still prints the error** when *file*
   can't be opened: redirections apply left to right, so the failing `<`
   happens before `2>` does. Write `cmd 2>/dev/null <file`.
10. **Things that behave differently headless** (from earlier FlickOS
    work): GTK's clipboard needs a recent input event's serial, so
    `Gtk.Clipboard.set_text` silently fails without real input (`wl-copy`
    works); a layer-shell surface gets keyboard focus only after the first
    typed key; drawing is on the CPU, so GL-heavy programs are slower
    than on your screen; there's no sound; and AT-SPI warns that
    `org.a11y.Bus` isn't provided (harmless).

---

## 9. When the harness is the wrong tool

- **How something feels**: animations, fonts at your real DPI, your real
  screen. Use your session.
- **Hardware**: GPU encoding, sound, touchpads, Bluetooth, suspend. Use your
  session.
- **The login screen, installer, boot**: use QEMU (`tools/test-iso.sh`).
- **System settings** (firewall, users, logind): the system bus isn't
  isolated, so the change would be real. Use QEMU.

---

## 10. Cleaning up

```sh
./stop.sh --clean      # stop, and delete $HL (its home, logs, runtime folder)
rm -rf shots tools     # your screenshots; the unpacked wtype and wlrctl
```

Nothing was installed, nothing in your home folder was changed (the harness
has its own), and `/tmp/.X11-unix` was only replaced *inside* the namespace.
