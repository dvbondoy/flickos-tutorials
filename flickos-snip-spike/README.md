# The screenshot and recording spike (phase 0), step by step

> Set `TUTORIALS` to the root of the [tutorials repository](https://github.com/dvbondoy/flickos-tutorials) and `FLICKOS` to your clone of [FlickOS](https://github.com/dvbondoy/FlickOS). Paths below use those two variables. Scripts read the FlickOS checkout from `FLICKOS_REPO` or `FLICKOS`.

This folder is a **guided spike** for a FlickOS screenshot and recording
tool, modelled on the Windows Snipping Tool. You run it yourself. Each step
says what to do, what every tool and command does and why, and what to look
for. The last steps show how the results turn into a design.

The earlier guide (`$TUTORIALS/flickos-phone-spike/README.md`) described a
spike *after* it was done. This one is the other way round: you do it, and
by the end you'll know the tools and the process well enough to run the next
spike without help.

Plan on 1½ to 2 hours: 20 minutes for steps 1–4, 20 for screenshots and
drawing, and about an hour for recording.

```
README.md          this guide
results.md         where your answers go (fill it in as you go)
check-machine.sh   step 2: what this computer and labwc can do (reads only)
package-cost.sh    step 4: what a package really adds, without installing it
try-unpacked.sh    step 5: try a program without installing it
shot.sh            step 6: every screenshot mode, delay, clipboard, drawing
measure.py         CPU and memory of a process (the recorders use it)
record-wf.sh       step 8: recording with wf-recorder
record-portal.py   step 9: recording through the portal with GStreamer
```

Created while you work (delete them at the end): `debs/`, `unpacked/`,
`shots/`, `recordings/`.

---

## Contents

0. [What a spike is](#0-what-a-spike-is)
1. [Write the questions down first](#1-write-the-questions-down-first)
2. [Know your machine](#2-know-your-machine)
3. [The riskiest question first: can we capture one window?](#3-the-riskiest-question-first-can-we-capture-one-window)
4. [What would it cost? Measure before installing](#4-what-would-it-cost-measure-before-installing)
5. [Try a program without installing it](#5-try-a-program-without-installing-it)
6. [Screenshots: modes, delay, clipboard](#6-screenshots-modes-delay-clipboard)
7. [Drawing on a screenshot with swappy](#7-drawing-on-a-screenshot-with-swappy)
8. [Recording, route A: wf-recorder](#8-recording-route-a-wf-recorder)
9. [Recording, route B: the portal and GStreamer](#9-recording-route-b-the-portal-and-gstreamer)
10. [Compare and decide](#10-compare-and-decide)
11. [Clean up](#11-clean-up)
12. [Turn the results into a design](#12-turn-the-results-into-a-design)
13. [Commands worth keeping](#13-commands-worth-keeping)

---

## 0. What a spike is

A **spike** is a short, throwaway experiment that answers the questions a
design can't answer on paper, *before* anything is built. It is "phase 0" in
every FlickOS design doc.

The rules:

1. **Questions first.** Know what you're trying to find out. Otherwise you
   are just playing with tools.
2. **The riskiest question first.** If the answer to one question could kill
   or reshape the whole idea, answer it before the easy ones.
3. **Write a prediction before each test.** When the result differs, you've
   learned something about how the system works, not only what it does.
4. **One change per test, and a control.** Change one thing at a time, and
   include a case that must work, so a "nothing happened" result means
   something.
5. **Measure, don't guess.** FlickOS states the cost of every feature (HIG,
   `docs/hig/08-performance.md`): disk space, memory, CPU.
6. **Throwaway code, safe place.** Scripts live here, not in the repo.
   Output goes into this folder, not `~/Pictures`. Nothing is installed
   without you choosing to, and everything installed gets removed at the end.
7. **Write the results into the design.** Results that only live in a chat
   or your head are lost.

One safety rule is special to this machine. You are working inside your real
FlickOS session, so **stop spike processes only by their PID** (`kill 1234`).
Never use `pkill -x grim` or similar: it would also hit the copies your
desktop runs (your Print key uses grim too). The scripts here always keep
the PID of what they start.

---

## 1. Write the questions down first

Open `results.md`. It has the questions below, with space for your
prediction and the result. Fill in the **prediction** column now, before
running anything. A guess is fine; the point is to compare it later.

| # | Question | Why it matters |
|---|---|---|
| Q1 | Can a program on labwc 0.8.3 capture **one window**? | The Snipping Tool's *Window* mode. If not, the design changes. |
| Q2 | Do grim and slurp cover the other modes (rectangle, screen, one screen of several) and a **delay**? Does an open menu survive until it is captured? | Menus and tooltips are why a delay exists. |
| Q3 | Is **swappy** good enough for drawing on a picture? What does it cost, and does it look right in FlickOS? | Writing our own editor would double the work. |
| Q4 | Which **recording route**: wf-recorder, or the portal with GStreamer? Compare disk, CPU, memory and MB per minute. | The biggest cost decision. |
| Q5 | Is the file still playable when the recorder **crashes** (SIGKILL)? | A crash mustn't lose the whole recording. |
| Q6 | Does **region** recording work, and does it land in the right place on your screen, which sits at x=1366? | Your two-screen layout is a real test. |
| Q7 | Do **desktop sound** and the **microphone** work? Does the sound stay in sync? | Snipping Tool records both. |
| Q8 | Does anything show that a recording is running? | Privacy: the user must always know. |

These questions came from the first quick look: what the tool must do (the
Snipping Tool's features), what FlickOS already has (the Print keys in
labwc's `rc.xml`), and what could go wrong.

---

## 2. Know your machine

**Do:**

```sh
cd $TUTORIALS/flickos-snip-spike
./check-machine.sh | tee machine.txt
```

`tee` shows the output *and* writes it to `machine.txt`, so the results have
a record of the machine they came from.

**What the script uses, and why:**

| Tool | What it is | What we ask it |
|---|---|---|
| `dpkg-query -W -f='${Status} ${Version}' PKG` | dpkg's query tool; `-W` shows installed packages in a format you choose | Is it installed, and which version? The version decides the features (grim 1.4 vs 1.5 matters in step 3). |
| `wlr-randr` | lists screens (outputs) on wlroots compositors like labwc | Names, resolution, **position** in the layout, scale. |
| `wayland-info` (package `wayland-utils`) | connects to the compositor and prints every **global** it offers | Which protocols labwc speaks. This is the key step (see step 3). |
| `busctl --user get-property …` | systemd's D-Bus tool; reads a property of an object on your session bus | What the screen-cast **portal** says it can share. |
| `wpctl inspect @DEFAULT_AUDIO_SINK@` | WirePlumber's control tool for PipeWire (the sound server) | The internal names of your speakers and microphone, which recorders need. |
| `/proc/cpuinfo`, `/proc/meminfo`, `/dev/dri/renderD*` | kernel files | CPU, memory, and whether a GPU could encode video. |
| `grep 'key="…Print"' rc.xml` | | Which Print keys labwc already has. The script reads the same `rc.xml` labwc reads: FlickOS's overlay in `$XDG_RUNTIME_DIR` comes first. |

**What it showed on 2026-09-27:**

- labwc 0.8.3, grim 1.4.0, slurp 1.5.0, xdg-desktop-portal-wlr 0.7.1.
  swappy, wf-recorder and the GStreamer PipeWire plugin were **not**
  installed.
- One screen in use: `HDMI-A-1`, 1920×1080, scale 1, at **position
  1366,0**. `eDP-1` (the laptop panel) is off. Remember that 1366 for Q6.
- Capture protocols: `zwlr_screencopy_manager_v1` yes, the three
  `ext_image_*capture*` ones **no**.
- Portal: `AvailableSourceTypes = 1`, meaning screens only, no windows.
- 4 CPUs (Core i3-4030U, from 2014), 11.6 GB memory, **no VA-API driver**,
  so the GPU can't encode video yet.
- Print, Shift+Print and Ctrl+Print are already bound.

If your output differs, for example after an upgrade, trust yours.

---

## 3. The riskiest question first: can we capture one window?

This is Q1. The *Window* mode is the one thing grim and slurp don't obviously
do, and the answer could change the design. So it comes before anything
pleasant.

### Background: why screenshots need the compositor's permission

On X11, any program could read the whole screen. On **Wayland** it can't:
each program sees only its own windows. Only the **compositor** (labwc) has
the whole picture. A screenshot tool must ask the compositor through a
**protocol**, which is a set of messages the compositor chooses to offer.
The names tell you where they come from:

- `zwlr_…`: from wlroots, "unstable" (the `z`). labwc is built on wlroots.
- `ext_…`: the newer shared standard (wayland-protocols' *staging*).
- `…_v1`: the version.

The protocols that matter here:

| Protocol | What it gives | labwc 0.8.3 |
|---|---|---|
| `zwlr_screencopy_manager_v1` | a copy of a **whole screen** or a **rectangle** of it | yes: grim and wf-recorder use this |
| `zwlr_foreign_toplevel_manager_v1`, `ext_foreign_toplevel_list_v1` | a **list of windows**: title, app id, maximized/focused. **No position, no size.** | yes: taskbars use this |
| `ext_image_copy_capture_manager_v1` + `ext_foreign_toplevel_image_capture_source_manager_v1` | a copy of **one window's** content, even when covered | **no** |

### Do it yourself

```sh
wayland-info | grep -E "screencopy|image_c|toplevel"    # what labwc offers
grim -h | grep -- -T                                     # can grim capture a window?
strings /usr/bin/labwc | grep -E '^ext_image'            # a second opinion, from the program file
busctl --user get-property org.freedesktop.portal.Desktop \
    /org/freedesktop/portal/desktop org.freedesktop.portal.ScreenCast AvailableSourceTypes
```

- `wayland-info` asks the running compositor, so it's the answer that
  counts.
- `strings FILE` prints every run of readable text in a program. Protocol
  names are compiled in as text, so it works even without a running
  compositor (for example on a build host). It's also how the flickos-phone
  spike found what libfm supports.
- `AvailableSourceTypes` is a **bit mask**: 1 = screens, 2 = windows,
  4 = virtual. `u 1` means screens only.

### Reading the answer

All four agree: **labwc 0.8.3 can't give a program one window's picture.**
There's no clean workaround either. To cut a window out of a screen
screenshot you need its position and size, and the window list protocols
don't carry them. That matters because slurp can let the user click one of
several rectangles given to it on standard input, so if we had window
positions, "click a window" would be three lines of code.

**Ideas you might consider, and why they're weak:**

- *Maximized windows only*: their rectangle is the screen minus the panels.
  But that's the least useful case.
- *flick-tiler's regions*: correct only for tiled windows, and only while
  tiling is on.
- *Wait for newer versions*: when labwc offers
  `ext_image_copy_capture_manager_v1` and the toplevel capture source, and
  grim gets `-T`, the answer flips. Check again after any labwc or grim
  upgrade: `check-machine.sh` prints the same lines.

**Write in results.md:** Q1 = no on labwc 0.8.3, with the evidence above.
The design will then say *Window* mode is left out (or added later), rather
than finding this out during the build.

This took ten minutes and no code. That's why the riskiest question goes
first.

---

## 4. What would it cost? Measure before installing

FlickOS's image installs packages **without Recommends**
(`--apt-recommends false` in `auto/config`), so what counts is what a package
*Depends* on. A package's own size is misleading. Ask apt to *simulate* the
install:

```sh
./package-cost.sh swappy
./package-cost.sh wf-recorder
./package-cost.sh gstreamer1.0-pipewire gstreamer1.0-tools
```

**What the script does:**

- `apt-get install -s --no-install-recommends PKG`: `-s` means simulate.
  apt works out everything it would install and prints `Inst NAME …` lines,
  but changes nothing, so no sudo is needed. `--no-install-recommends`
  matches the image.
- `apt-cache show --no-all-versions NAME`: the package's record.
  `Installed-Size` is KB on disk after install, `Size` is the download in
  bytes.

**What it showed on 2026-09-27:**

| For | New packages | On disk | Download |
|---|---|---|---|
| swappy | swappy, fonts-font-awesome (its icons) | 1.5 MB | 0.5 MB |
| wf-recorder | **14**, incl. libavfilter10, libflite1, libplacebo349 | **55 MB** | 20 MB |
| GStreamer route | gstreamer1.0-pipewire, gstreamer1.0-tools | 0.6 MB | 0.2 MB |

**The lesson:** `apt-cache show wf-recorder` says **152 KB**. The real cost
is 55 MB, and 27 MB of that is *libflite1*, a text-to-speech engine. It comes
in because FFmpeg's filter library has a speech filter, and wf-recorder
links to the filter library. No one would guess that. Always measure the
whole chain. To see *why* a package comes in:

```sh
apt-cache depends wf-recorder          # what it needs directly
apt-cache rdepends --installed libavfilter10   # who installed here needs it (nobody yet)
```

**Why GStreamer is so cheap here:** every FlickOS system already has
GStreamer's base and good plugins, because xdg-desktop-portal (a Depends of
flickos-desktop) needs them. `apt-cache rdepends --installed
gstreamer1.0-plugins-good` shows that. The VP8 video and Opus sound encoders
are in them. The portal route only adds the
PipeWire plugin. The tools package is only for the spike: the real program
would use GStreamer from Python (`gir1.2-gstreamer-1.0`, 0.4 MB) instead of
`gst-launch-1.0`.

> **Update:** the FlickOS repo now has `tools/package-cost.py`, a better
> version of this script. It compares with the **image** (the last build's
> `flickos-amd64.packages`) instead of this computer, which matters: on the
> image wf-recorder adds **16 packages, 57 MB** (libsdl2 and libxss1 are on
> this computer but not in the image). It also showed that **GTK 4 is
> already in the image**, because trixie's pavucontrol uses it. Use
> `tools/package-cost.py` for real numbers. This script stays for learning.

Write the table into results.md (Q3, Q4). For the image, the download size
is roughly what a package adds to the ISO (the ISO is compressed too): 20 MB
for wf-recorder. The HIG asks whether a feature is worth what it adds.

---

## 5. Try a program without installing it

Sometimes you want to *see* a program before deciding to install it:

```sh
./try-unpacked.sh swappy wf-recorder
```

**What the script does:**

- `apt-get download PKG`: fetches the `.deb` into `debs/` (no sudo, nothing
  installed).
- `dpkg-deb -x FILE.deb unpacked/`: unpacks its files into a folder instead
  of `/`. A `.deb` is just an archive of files plus scripts.
  `dpkg-deb -c FILE.deb` lists them without unpacking.
- `ldd PROGRAM`: lists the shared libraries a program needs and where they
  are found. `not found` means it can't start.
- `LD_LIBRARY_PATH=unpacked/usr/lib/x86_64-linux-gnu`: tells the loader to
  look in that folder first, so unpacked libraries are used.

**Result on 2026-09-27:**

```
swappy: all libraries found
wf-recorder: can't run here, missing: libavdevice.so.61 libavfilter.so.10
```

swappy can be tried unpacked. Its icons will be empty boxes because its icon
font (fonts-font-awesome) isn't installed, but it runs. wf-recorder needs the
14 packages from step 4, and unpacking all of them is more trouble than
installing and removing them. That's a judgement call you'll make often:
**unpack to look, install to measure**.

---

## 6. Screenshots: modes, delay, clipboard

This is Q2. `shot.sh` does what the tool would do, with the same programs
your Print keys already use.

```sh
./shot.sh region            # drag a rectangle; Esc cancels
./shot.sh screen            # every screen
./shot.sh output            # click the screen you want
./shot.sh region --copy     # to the clipboard; paste into e.g. LibreOffice
./shot.sh screen --delay 5  # wait 5 s first
```

**The tools:**

- **grim**: takes the picture through `zwlr_screencopy`. `-g "X,Y WxH"`
  captures a rectangle in **layout coordinates**: the whole desktop as one
  surface, where your HDMI screen starts at x=1366. `-o NAME` captures one
  screen, and `-` writes to standard output. It saves PNG by default; `-t
  jpeg` is smaller and faster.
- **slurp**: shows a see-through overlay (a layer-shell surface, like the
  panel) and prints the rectangle you drag, in the format grim wants.
  `-o` selects whole screens and `-f %o` prints the screen's name instead.
  It exits with status 1 when you press Esc. `slurp -p` picks a single
  point.
- **wl-copy --type image/png**: puts standard input on the Wayland
  clipboard. It stays running in the background to serve pastes, which is
  normal.
- `date +%s%N`: the time in nanoseconds. The script times grim alone, not
  your dragging.

**Experiments (write a prediction for each first):**

1. `./shot.sh screen` a few times: how many ms? It took 252 ms here
   (1920×1080). Most of that is PNG compression. Try it with `grim -t jpeg`
   by hand to compare.
2. `./shot.sh region`: drag across the top-left of the HDMI screen and look
   at the printed rectangle. Does x start near 1366? Open the picture: is it
   the right place?
3. **The menu test (the important one).** Run
   `./shot.sh region --delay 5`, then within the 5 seconds open a menu, for
   example right-click in PCManFM or open Firefox's ☰ menu. When slurp's
   overlay appears, **does the menu stay open?** Then repeat with
   `./shot.sh screen --delay 5`.

   *Why it might close:* Wayland menus are *popups* with a "grab". When
   another surface gets the keyboard (slurp takes it to catch Esc), the
   compositor closes the popup. `screen` mode doesn't start slurp, so
   nothing takes focus. If region + delay loses the menu, the real tool has
   to do what the Snipping Tool does: **freeze first**. Take the whole
   screen at the end of the countdown, show that picture full-screen, and
   let the user drag on the frozen picture. That's a design decision you'd
   only find by testing.
4. `./shot.sh output`: with only one screen on, does slurp still make you
   click? It's a small thing, but it decides whether the tool must skip the
   choice when there's one screen.

Things to note for the design: the Snipping Tool also has **free-form**
(draw any shape). slurp can only do rectangles, so free-form would need our
own overlay. Is it worth it? Put it under open questions.

---

## 7. Drawing on a screenshot with swappy

The rest of Q3. **swappy** is a small GTK 3 editor built for grim. Try it
unpacked first (step 5), then decide:

```sh
./shot.sh region --edit      # uses installed swappy, or unpacked/ if not installed
```

To see it properly (with icons), install it for the spike. It's 1.5 MB and
comes out again in step 11:

```sh
sudo apt install --no-install-recommends swappy
```

**How the script uses it:** `swappy -f FILE -o OUT`. `-f` opens a picture
(`-f -` reads it from standard input, so `grim - | swappy -f -` also works),
and `-o` writes the edited picture when you close the window. Its own
**Save** button writes to `save_dir` from `~/.config/swappy/config`, which
defaults to `~/Desktop`, so look there after the test and delete what you
saved. The real tool would set its own save folder by passing `-o`, not by
writing into the user's config (the FlickOS rule: never change user files).

**Check it against the Snipping Tool, and against FlickOS's HIG:**

| Snipping Tool | swappy? |
|---|---|
| pen, several colours | |
| highlighter | |
| eraser / undo | |
| crop | |
| arrow, rectangle, text | |
| blur (hide a password) | |
| copy / save | |

HIG points to look at (in `docs/hig/`): Does it follow the Arc-Dark theme
(it's GTK 3, so it should)? Can you use it with the **keyboard only**
(`07-accessibility.md`)? Are its labels clear English
(`05-writing.md`)? Does its window behave like the others
(`04-windows.md`)? Anything it fails is either a patch, a note in the
audit, or a reason to write our own. Write which in results.md.

---

## 8. Recording, route A: wf-recorder

Q4–Q8, first route. wf-recorder uses the same `zwlr_screencopy` as grim, but
many times a second, and FFmpeg's libraries to compress it into a video.

```
labwc ──screencopy──▶ wf-recorder ──FFmpeg (libavcodec…)──▶ file.mp4
                         ▲
              PipeWire/Pulse sound (optional)
```

Install it for the spike (55 MB, removed in step 11):

```sh
sudo apt install --no-install-recommends wf-recorder
```

### Background: codecs and containers

A video file is a **container** (MP4, WebM, MKV) holding **streams**
encoded by a **codec** (video: H.264, VP8/VP9; sound: AAC, Opus).
wf-recorder picks the container from the file name. MP4 by default holds
H.264 (`libx264`).

This matters for Q5: an **MP4 file writes its index at the end**. If the
recorder is killed before it finishes, the index is missing and most
players refuse the file. **WebM/MKV write as they go**, so a killed recording
usually still plays up to the crash. That's why the stop signal matters:

- **SIGINT** (what Ctrl+C sends) asks wf-recorder to finish: flush the
  encoder and write the index. `kill -INT PID` sends it.
- **SIGKILL** (`kill -KILL PID`) can't be caught. It's what a crash, the
  kernel's out-of-memory killer, or a hard logout looks like.

### Run it

`record-wf.sh` starts wf-recorder in the background, keeps its PID
(`$!`), starts `measure.py` on it, and stops it when you press Enter.

```sh
./record-wf.sh screen                  # R1: 30 s, don't touch anything
./record-wf.sh screen                  # R2: 30 s, drag a window around / play a video
./record-wf.sh region --audio          # R3: play music; is the sound in sync?
./record-wf.sh screen --mic            # R4: talk
./record-wf.sh screen --webm           # R5: VP8 + Opus instead: CPU compared to R2?
./record-wf.sh screen --kill           # R6: stopped with SIGKILL: does the file play?
./record-wf.sh screen --webm --kill    # R7: the same in WebM
```

Play each: `vlc recordings/FILE` (VLC is installed), or `gst-play-1.0
recordings/FILE` once you have gstreamer1.0-tools (step 9). If something
fails, read `recordings/wf-recorder.log`.

**The options, explained:**

- `-g "X,Y WxH"`: record a rectangle (from slurp, as in step 6).
- `--audio=DEVICE`: record sound. The `=` is required, because the value is
  optional. `--audio-backend=pulse` makes it use PulseAudio names, which
  PipeWire answers through `pipewire-pulse`.
- **Desktop sound** is the speakers' **monitor**: every PulseAudio/PipeWire
  output has a matching input called `NAME.monitor` that carries what it
  plays. `wpctl` gives `NAME` (step 2).
- `-c CODEC` / `-C AUDIOCODEC`: the video / sound encoder (`libvpx`,
  `libopus`). `-p preset=ultrafast`: an encoder option, so try
  `./record-wf.sh screen -- -p preset=ultrafast` to see what it does to CPU.

### Measuring: what `measure.py` reads

(The repo's `tools/measure.py` is the kept version of this script: it also
reports Private memory and wakeups, and `--tree` measures child processes.)

- **CPU**: `/proc/PID/stat` fields 14 and 15 count how long the process
  has run on a CPU (user + kernel time) in clock ticks. The difference
  between two readings, divided by the time between them, is the CPU use.
  100% means one CPU fully busy; this machine has 4, so 400% is the most.
- **Memory**: `Pss` from `/proc/PID/smaps_rollup`. PSS counts shared
  libraries only by this process's share, so it's the fair number (RSS
  counts them in full).
- The same by hand: `top -p PID` (press `1` to see each CPU).

For every run, write CPU average and highest, PSS, and MB per minute into
results.md. **Also note what you see**: dropped frames, stutter, sound out
of step.

Q8: while it records, does anything on screen say so? (wf-recorder shows
nothing.) If nothing does, the real tool must add its own sign, a panel
button, and that goes into the design as a must.

---

## 9. Recording, route B: the portal and GStreamer

The same questions, the second route. It's the route OBS and browsers'
screen sharing use. It's more code but, as step 4 showed, 1% of
the disk cost.

```
record-portal.py ──D-Bus──▶ xdg-desktop-portal ──▶ xdg-desktop-portal-wlr ──screencopy──▶ labwc
       │                                                    │
       │◀──── a PipeWire connection (a file descriptor) ─────┘  the picture flows here
       ▼
gst-launch-1.0: pipewiresrc ! videorate ! [videocrop] ! videoconvert ! vp8enc ! webmmux ! filesink
                pulsesrc (sound) ! audioconvert ! opusenc ───────────────────────▲
```

### Background: the three pieces

- **D-Bus** is the desktop's message bus: programs call methods on each
  other's objects by name. `busctl --user` looks at it by hand. Try
  `busctl --user introspect org.freedesktop.portal.Desktop /org/freedesktop/portal/desktop`
  to list every portal method.
- **xdg-desktop-portal** is the standard front door for "ask the user for
  something": screen sharing, file choosers, screenshots. It passes the
  request to a desktop-specific **backend**, here **xdg-desktop-portal-wlr**
  (a Depends of flickos-desktop), which uses screencopy. The backend lets
  the user choose a screen by running `slurp -o` (its `chooser_cmd`, see
  `man xdg-desktop-portal-wlr`).
- **PipeWire** carries the picture (and your sound). The portal hands us a
  file descriptor: a PipeWire connection that can only see the one stream we
  were given.

**The portal conversation**, as `record-portal.py` does it:

1. `CreateSession`: open a screen-cast session.
2. `SelectSources`: what we want: one screen (`types = 1`), cursor drawn
   in (`cursor_mode = 2`, allowed because `AvailableCursorModes` was 3).
3. `Start`: the portal asks the **user** to choose (the slurp overlay) and
   answers with the stream's PipeWire node, size and position.
4. `OpenPipeWireRemote`: gives us the file descriptor.

Portal methods don't answer directly. They return a *Request* object at
once, and the real answer arrives later as that object's `Response` signal,
because the user may take a minute to choose. The script works out the
Request's path in advance and listens *before* calling, so it can't miss the
answer. The `request()` function in the script is 30 lines, and it's the
pattern for every portal.

**GStreamer** is a media framework where a **pipeline** is a chain of
**elements** joined by `!`. `gst-launch-1.0` builds one from a text
description, the same way a shell builds a pipe:

| Element | Does |
|---|---|
| `pipewiresrc fd=… path=NODE` | reads the picture from the portal's PipeWire stream |
| `keepalive-time=1000` | the portal only sends a frame when the screen changes, so this repeats the last one to keep the video's pace |
| `videorate ! video/x-raw,framerate=30/1` | a steady 30 frames a second. The part after `!` without a name is a **caps filter**: it says what format must flow there |
| `videocrop left= top= right= bottom=` | for `--region`: cut the slurp rectangle out of the screen |
| `videoconvert` | converts the pixels to the format the encoder wants |
| `queue` | a thread boundary, so a slow encoder doesn't hold up capture |
| `vp8enc deadline=1 cpu-used=8` | VP8 video; `deadline=1` means real time (fast over good) |
| `webmmux` → `filesink location=…` | the WebM container, into a file |
| `pulsesrc device=NAME.monitor ! audioconvert ! audioresample ! opusenc ! queue ! mux.` | the sound branch; `mux.` means "the element named mux" |

`gst-launch-1.0 -e`: on SIGINT, send **end-of-stream** down the pipeline
first, so everything finishes the file properly (the same job as
wf-recorder's SIGINT handling).

`gst-inspect-1.0 ELEMENT` lists an element's properties. That's how this
pipeline was checked before you got it (every property above exists in
trixie's versions). `x264enc` (H.264) is **not** installed, which is why this
route records VP8.

### Run it, in three stages

Install the two small packages:

```sh
sudo apt install --no-install-recommends gstreamer1.0-pipewire gstreamer1.0-tools
```

Then test the halves separately before putting them together. That way, if
something fails, you know which half failed:

```sh
./record-portal.py --check          # stage 1: only D-Bus. Nothing appears on screen.
./record-portal.py --test --audio   # stage 2: only GStreamer, with a moving test picture
./record-portal.py                  # stage 3: the real thing
```

Stage 1 printed this here on 2026-09-27, so the portal side answers:

```
[portal] CreateSession …
[portal] session /org/freedesktop/portal/desktop/session/1_139/snipsession
[portal] SelectSources …
[portal] the portal answers; --check stops before anything is shown
```

Stage 2 worked here too: a playable WebM with sound, finished properly on
SIGINT. Its CPU number (165%) is **not** a real result, because drawing the
test picture costs CPU too. Only stage 3 counts.

Then the same runs as route A:

```sh
./record-portal.py                    # P1 still screen, P2 moving: CPU, PSS, MB/min
./record-portal.py --region --audio   # P3 = Q6 + Q7: is the crop in the right place?
./record-portal.py --mic              # P4
./record-portal.py --kill             # P5 = Q5: does a killed WebM play?
```

**What to watch for in stage 3:**

- `Start` shows the portal's chooser (slurp in screen mode). Click your
  screen. Does it ask even with only one screen on? Does anything show that
  sharing is on (Q8)?
- The script prints the stream's properties: check that `position` is
  `(1366, 0)` and `size` is `(1920, 1080)`. `--region` uses both to work out
  the crop. At a scale other than 1 this would need multiplying, which is a
  note for the design.
- If it fails, read `recordings/gst.log`. `GST_DEBUG=3` in front of the
  command prints more.

`measure.py` measures only `gst-launch-1.0`. The portal backend does some
of the work in its own process, so for a fair comparison with wf-recorder,
look at the backend too while recording:

```sh
pgrep -f xdg-desktop-portal-wlr       # find its PID (pgrep only lists, it's safe)
./measure.py PID                      # in a second terminal; Ctrl+C to stop
```

---

## 10. Compare and decide

Fill in the comparison in results.md:

| | wf-recorder | portal + GStreamer |
|---|---|---|
| disk (step 4) | 55 MB | 0.6 MB (0.4 MB without the tools) |
| CPU, moving screen | | |
| memory (PSS), plus the backend for the portal | | |
| MB per minute | | |
| killed file plays? | MP4: / WebM: | |
| region right? | | |
| sound in sync? | | |
| shows it's recording? | | |
| code | a command line | ~200 lines (D-Bus + pipeline) |
| window capture later | when labwc + grim can | when portal-wlr offers windows (`AvailableSourceTypes` bit 2) |

**How to decide.** Look for a result that *rules one out* before
weighing the rest. For example, if the portal route can't keep up on this
2014 i3 while wf-recorder can, the cost difference doesn't matter. If both
work, 55 MB versus 0.6 MB will probably decide it: the HIG's performance
chapter (`08-performance.md`) starts with "FlickOS has to feel quick on a
ten-year-old laptop with 4 GB of RAM and a slow disk", and that's the laptop
you're testing on.

Write the decision as a sentence, with the numbers that made it, in
results.md. That sentence becomes an ADR in step 12.

---

## 11. Clean up

Remove what the spike installed. First look at what apt will remove:
`purge` removes the packages and their system config files.

```sh
sudo apt purge swappy wf-recorder gstreamer1.0-pipewire gstreamer1.0-tools
sudo apt autoremove --purge
```

**Read the list before you say yes to autoremove.** It removes packages
that were installed only as dependencies and are now unused, which should be
exactly the ones `package-cost.sh` listed. If it lists anything else, stop
and find out why. `apt-mark showauto PKG` tells you whether apt thinks it
was a dependency.

Then the files:

```sh
rm -rf debs unpacked shots recordings
ls ~/Desktop                    # swappy's Save button puts pictures here
ls ~/.config/swappy 2>/dev/null # only if you made a config; delete it
```

Keep `results.md` and `machine.txt`. They're the record.

---

## 12. Turn the results into a design

This is where the spike pays off. FlickOS designs live in
`docs/design/NAME.md` in the repo. Read `docs/design/flickos-phone.md` for
the shape:

- **Status** line: *Proposed*, the date, and "phase 0 done".
- **Problem**: what users can't do today (Print keys only: no delay, no
  window, no drawing, no recording), and what exists (Snipping Tool, other
  Linux tools and why not them).
- **Goals and non-goals**: for example *Window* mode could be a non-goal
  "until labwc offers window capture" (Q1).
- **Decisions (ADRs)**: one per real choice, each with context, the choice,
  the alternatives and **the numbers from the spike**. Likely ones:
  recording route (Q4), swappy vs own editor (Q3), freeze-first or not (Q2's
  menu test), the recording sign (Q8), file format (Q5).
- **Phases**: phase 0 = this spike, phase 1 = screenshots with delay and
  drawing, phase 2 = recording with the panel sign, and so on.
- **Phase 0 results**: the table from results.md.
- **Risks and open questions**: free-form shapes, scales other than 1,
  window mode later, microphone permission.

Then before any code, the FlickOS checklist says where a new package
touches the repo (`CLAUDE.md`, `docs/04-packages.md`): a new package in
`packages/`, a Depends in flickos-desktop, the sanity hook's `REQUIRED`,
the labwc keys in flickos-settings' `rc.xml` plus a description in
flickos-shortcuts' `COMMANDS`, both menus (`tools/check-menus.py`), a
boot-test check, `debian/copyright`, and the HIG checklist.

You can hand me results.md and machine.txt and ask me to draft the design
doc from them. It will be much better than one written from memory,
because every ADR will have a measured reason.

---

## 13. Commands worth keeping

| Command | For |
|---|---|
| `wayland-info \| grep NAME` | what the compositor offers (protocols) |
| `strings PROGRAM \| grep NAME` | what a program knows about, without running it |
| `busctl --user introspect SERVICE OBJECT` / `get-property` | look at and read D-Bus services, like the portal |
| `wpctl status` / `wpctl inspect @DEFAULT_AUDIO_SINK@` | sound devices and their names |
| `wlr-randr` | screens, positions, scale |
| `apt-get install -s --no-install-recommends PKG` | what installing would really add (no sudo) |
| `apt-cache depends` / `rdepends --installed` | why a package comes in / who needs it |
| `apt-get download PKG; dpkg-deb -c/-x` | look inside a package / unpack it without installing |
| `ldd PROGRAM` with `LD_LIBRARY_PATH=…` | will it start, and which libraries is it missing |
| `grim -g "$(slurp)" FILE` | screenshot of a rectangle |
| `wf-recorder -g "$(slurp)" -f FILE` | record a rectangle |
| `gst-inspect-1.0 ELEMENT` / `gst-launch-1.0 -e …` | GStreamer element properties / try a pipeline |
| `kill -INT PID` vs `kill -KILL PID` | ask a program to finish / simulate a crash |
| `/proc/PID/stat` (fields 14–15), `/proc/PID/smaps_rollup` (Pss) | CPU and fair memory of a process (`measure.py`) |
| `cmd & pid=$!` … `kill $pid; wait $pid` | start in the background and stop exactly that process |
