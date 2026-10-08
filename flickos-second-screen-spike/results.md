# Second screen spike: results

Date: 2026-10-07  Design doc: `docs/design/flickos-phone.md`, *Later* 23
(and `flickos-phone-screen.md`, *Later*)  Machine: i3 laptop, labwc 0.8.3,
wayvnc 0.9.1 (installed), HDMI-A-1 1920×1080 on, eDP-1 off

Part A was done by Claude in a headless labwc (pixman) and by reading the
sources in `src/`. Parts B and C are yours: write the prediction first.

## Questions

| # | Question | Prediction | Result | Evidence |
|---|---|---|---|---|
| Q1 | How can a program run `VirtualOutputAdd`? | Only a keybind; needs a trick | **Two ways, both work.** (a) A window rule on an app id runs it when that window first opens, `<action name="Close"/>` closes the window ~25 ms later (mapped 72 ms after start, closed at 90–105 ms). (b) A keybind on a key no keyboard has (`XF86Launch8`), pressed by a virtual keyboard (`wtype -k`): labwc matches virtual keyboards by keysym. Adding again is refused by name, so both are idempotent. | A1; `src/labwc-0.8.3/src/window-rules.c`, `input/keyboard.c` `match_keybinding` |
| Q2 | Does `kdeconnect.virtualmonitor` open the phone's VNC app? | Yes (design says so) | **No.** The Android app (1.35.17, master 2026-10-06) has no virtualmonitor plugin at all. The desktop plugin now speaks only RDP (`krdpserver`) between two desktops. It sends `kdeconnect.virtualmonitor.request {protocol, username, password, port}`, and the receiver opens `protocol://user:pass@SENDER_IP:port`. What does work: a `vnc://` link as `kdeconnect.share.request {"url"}`. The app opens it with `ACTION_VIEW`, or while in the background shows a high-priority notification **whose title is the whole link, password included**, "Tap to open". | A3; `src/vm-desktop.cpp`; `src/kdeconnect-android/…/share/SharePlugin.kt` `receiveUrl`, `helpers/IntentHelper.kt` |
| Q3 | Who decides the size? | labwc, fixed | labwc makes it 1920×1080. `wlr-randr --custom-mode` changes it, and so can **the VNC client** (RFB SetDesktopSize): wayvnc resizes the screen through wlr-output-management, **only if its name starts with `HEADLESS-`** (or `NOOP-`), so the name is `HEADLESS-PHONE`. AVNC has *Resize remote session to local window*, per saved server, off by default, not settable in a link. gtk-vnc dropped the connection over a 1920×1080 frame sent after the resize to 1280×800 (stale frame; check AVNC in C5). | A2; `src/wayvnc-0.9.1/src/output.c`, `output-management.c`; `src/avnc/…/ServerProfile.kt` |
| Q4 | How does the phone log in? | VNC password | wayvnc with `enable_auth` offers VeNCrypt (19; subtype X509Plain 262 only: TLS, then user + password), RSA-AES (5, 129), and Apple DH (30) only with `relax_encryption`. **Never plain VNC auth (2).** Tested: TLS 1.3, right password → in; wrong → `Invalid username or password`; pinned fingerprint catches a changed certificate. AVNC speaks VeNCrypt and asks once to trust an unsigned certificate. AVNC links take `VncUsername`, `VncPassword`, `SecurityType=19`, `ConnectionName`, `SaveConnection=true`. A saved server of the same `ConnectionName` is reused with the link's host and password and keeps its own settings (resize). | A4; `rfb-login.py`; `src/neatvnc-0.9.1+dfsg/src/server.c`, `auth/vencrypt.c`; `src/avnc/…/VncUri.kt`, `IntentReceiverActivity.kt` |
| Q5 | Screen removed while the phone watches? | wayvnc exits | **It shows the main screen.** wayvnc switches to the previous output (`switch_to_prev_output`). The connected client was resized to 1280×720 = HEADLESS-1 and kept getting updates. Afterwards wayvnc 0.9.1 died in 2 of 3 runs (once silently, once `malloc(): smallbin double linked list corrupted`, exit 134). **Rule: stop wayvnc first, then remove the screen.** wayvnc started with `-o` for a missing screen exits (`No such output`; read in the source, not run). | A5; `logs/client-remove.log`, `logs/wayvnc-remove.log`; `src/wayvnc-0.9.1/src/main.c` `registry_remove` |
| Q6 | Cost | small | see below | A6 |
| Q7 | What does the desktop do with it? | Nothing special | Treats it as a real screen: wallpaper, full panel, the pointer crosses onto it, new windows open there and are missing from the main taskbar; kanshi leaves things alone; Displays would save it. Off brings windows back. | Part B |
| Q8 | Real phone through ufw | | **Works** on the Lenovo Tab M11 with AVNC: 2 taps, smooth, sharp at 1920×1200 scale 1.5, survives the tablet sleeping. AVNC's own resize breaks the connection with neatvnc 0.9.1 (fixed in 1.0.0); touch shares the desktop's pointer. | Part C |

## Cost (HIG PERF-7)

| What | Number | How measured |
|---|---|---|
| disk, Debian's wayvnc | **13 packages, 54.3 MB** (libavfilter 14 MB, libflite 27.6 MB, libplacebo 9 MB…): libneatvnc0 links libav* only for its H.264 encoding | `tools/package-cost.py wayvnc`; `meson.build` `h264` |
| disk, own neatvnc `-Dh264=disabled` | estimate < 1 MB (libneatvnc 190 KB + wayvnc 238 KB + libaml 48 KB + libturbojpeg 802 KB) — not built | same list without libav* |
| disk, wtype (trigger b, if not done in Python) | 36 KB | `tools/package-cost.py wtype` |
| labwc, virtual screen idle, nobody watching | 0 % CPU, 0 wakeups/min; +7.9 MB PSS (one 1920×1080 buffer, pixman; GPU memory on the real session) | `tools/measure.py --for 10`, headless |
| wayvnc waiting, no client | 0 % CPU, 0 wakeups; PSS 27.4 MB, Private 24.1 MB (libav mapped) | headless |
| wayvnc, logged-in client, still screen | 0 % CPU; PSS 35.8 MB | headless; wakeups were the test client's own polling |
| wayvnc, moving content, real phone | *(C6)* | |
| time: add the screen | ~100 ms (window rule or key) | `second-screen.sh on` |

## Part B: your session (Q7), done by Claude 2026-10-07 15:30–15:34

Redmond layout, tiling off, kanshi running with one kept arrangement (HDMI on
at 1538,0, eDP-1 off). `./second-screen.sh on 1280x800`, then `off`, `cleanup`.

| Check | Prediction | Result |
|---|---|---|
| B0 adding it live | ~100 ms | 221 ms from the key to the screen; writing the add-on and `flickos-layout reconfigure` before it took ~2 s (first time only) |
| B1 panel / wallpaper on HEADLESS-PHONE | maybe | **The whole desktop:** swaybg's wallpaper and a full Redmond panel (start button, taskbar, tray, clock, Show Desktop strip), first 1920 then 1280 wide (`panel.log`: *Bar configured … for output: HEADLESS-PHONE*). waybar has no `output` setting, so it puts a bar on every screen. `logs/b1-phone.png` |
| B2 pointer | crosses at the right edge | The screen sits right of HDMI (x 3458), so the mouse crosses onto it. Moved there with `vnc-pointer.py` (wayvnc's virtual pointer, what a tap does) |
| B3 new window with the pointer there | opens there | **Opens on the invisible screen** (labwc places it on the pointer's screen), and **the main panel's taskbar doesn't list it**: waybar's `wlr/taskbar` shows only its own screen's windows. `logs/b3-phone.png`, `logs/b3-main-taskbar.png` |
| B4 flick-tiler | | Not toggled (it would rearrange your windows). Its docstring: one arrangement for all outputs, regions in percent of the window's own output; it doesn't know screens apart. Show Desktop minimizes the phone screen's windows too |
| B5 kanshi | nothing | **Nothing**: HDMI stayed at 1538,0 on add and on remove (no profile matches while HEADLESS-PHONE exists) |
| B6 Displays | lists it | **Would keep it:** `screens_profile(read_screens())` gives `output HEADLESS-PHONE enable mode 1280x800 position 3458,0 …` in the profile. kanshi would then apply that profile whenever the phone screen appears, fighting AVNC's resize |
| B7 labwc idle (30 s, your apps running) | +8 MB, no wakeups | PSS 59.2 MB before → **68.9 MB on** → 60.5 MB after off. CPU and wakeups follow your own activity (2.6 % / 4,701 per min before, 1.8 % / 3,379 on, 0.9 % / 1,273 after), no visible cost of its own. waybar's second bar: 33.2 → 33.5 MB. wayvnc waiting: 24.1 MB PSS, 0 % CPU, 0 wakeups |
| B8 off | windows come back | wayvnc stopped, screen removed; the foot window came back to HDMI (behind VS Code, in the main taskbar again); the bar was removed (`panel.log`). No crash |

**What this means for the design**
- The phone's screen is a full desktop with its own panel: good for a
  tablet, but a window that lands there is lost from the main screen's
  taskbar. Either the product keeps the pointer and new windows off it
  (hard: labwc places by pointer) or the main taskbar lists every screen's
  windows while it's on (`"all-outputs": true` on `wlr/taskbar` in the
  generated panel), or both.
- While it is on and nobody watches (phone asleep), the pointer can wander
  onto it. Turning it off when the last VNC client leaves (wayvnc's
  `client-disconnected` event on `wayvncctl event-receive`) would fix that.
- Displays must leave out `HEADLESS-*` (confirmed).

## Part C: Lenovo Tab M11 with AVNC (Q8), 2026-10-07 15:38–15:55

ufw: `allow from 192.168.88.175 to any port 5900 proto tcp`. Link sent with
`flickos-phone send --to ID` (two devices connected). Events from
`wayvncctl -j event-receive` (`logs/c-events.log`), sizes `logs/c-sizes.log`.

| Check | Result |
|---|---|
| C3 the notification | KDE Connect showed it; the maintainer saw **no password** in it (probably because Android cuts a long title and `VncPassword` is at the end of the link; not checked, and the whole link is still in the notification's data) |
| C4 taps | **2** (notification, trust the certificate). Logged in 71 s after the link was sent, reading included. VeNCrypt, user `phone` |
| C5 AVNC's *Resize remote session to local window* | **Breaks the connection.** On every layout change (rotation) AVNC sends SetDesktopSize; neatvnc 0.9.1 logs `Got uninterpretable (qemu) message` and drops the client, which reconnects and is dropped again (connections 3–6 lasted 46 ms–2.5 s). Cause: libvncclient writes the message in two parts (`SendExtDesktopSize`: header, then the screen), so over TLS they come as two records, and neatvnc 0.9.1 reads the screen part without checking it has arrived, then is out of step. **Fixed in neatvnc 1.0.0** (544342f, 2024-12-07). The screen never changed size |
| C5b size set on the computer instead | `wlr-randr --output HEADLESS-PHONE --custom-mode 1920x1200 --scale 1.5` (the Tab M11's own pixels): AVNC followed at once and stayed connected; **fills the tablet, sharp text** |
| C6 a window on it, moving and scrolling | **Smooth.** wayvnc up to 8 % CPU and ~2,500 wakeups/min while moving, 0 % idle; PSS 59–64 MB with the tablet connected at 1920×1200 (24 MB with no client). labwc up to 8.4 % while moving. `logs/c6-*.txt` |
| C7 touch | Works, but **a tap moves the desktop's one pointer** to the tablet screen and clicks there, and keys go to the focused window wherever it is: labwc 0.8.3 has no `ext-transient-seat`, so wayvnc's `--transient-seat` (a pointer per client) can't work |
| C8 tablet screen off ~30 s, then on | AVNC **disconnected** (15:53:56) and **reconnected by itself** (15:54:30); to the user it looked as if it never left |
| C9 `off` while connected | wayvnc stopped, then the screen removed; no crash, the main screen never shown. AVNC showed **Disconnected** (no main screen, no error beyond that) |

**What this means for the design**
- Size: the computer sets it (the user picks the device's size once, or a
  list of common tablet sizes) unless neatvnc ≥ 1.0 is used; with an own
  neatvnc 1.0 build, AVNC's resize can be tried again.
- Turning off when the last client leaves needs a grace period (a sleeping
  tablet disconnects and comes back).
- Input is shared with the desktop's pointer: view-only by default, or a
  clear warning, is a maintainer decision.
- The password was not visible in this notification, but it is in the
  notification's data; a per-session password limits what it's worth.

## Options compared

| | Trigger: window rule | Trigger: virtual-keyboard key |
|---|---|---|
| seen by the user | a window for ~25 ms; in the panel's window list unless a rule sets `skipTaskbar` (check in B) | nothing |
| code | any GTK program (flickos-phone's daemon has no GTK) | a stdlib Wayland client with a keymap (memfd), like flick-tiler's; or wtype (36 KB) |
| rc.xml overlay | two `<windowRule>`s | two keybinds (XF86 keys: flickos-shortcuts already leaves them out) |

| | Debian's wayvnc | Own neatvnc build, no H.264 |
|---|---|---|
| disk | 54.3 MB | < 1 MB (estimate) |
| work | none | a vendored package like sfwbar, or inside the sold add-on |

**Decision (proposed):** keybind on a virtual keyboard for the trigger,
screen named `HEADLESS-PHONE`, VeNCrypt with one certificate per computer,
the link sent with flickos-phone's existing share (not
`kdeconnect.virtualmonitor`, which Android ignores), wayvnc stopped before
the screen is removed. The 54 MB stays out of the image unless neatvnc is
built without H.264.

## New questions found on the way

- The password shows in the phone's notification. Options: a new password
  each session (it's useless once the screen is off), or a password per
  phone kept in AVNC and a link without it. Maintainer's choice.
- wayvnc gives the phone keyboard and mouse over the whole session (keys go
  to the focused window, even on the main screen). Should input be on by
  default, or `--disable-input` (view only)?
- Without the virtualmonitor packet the computer never learns the phone's
  size: AVNC's resize (one switch the user turns on once) or a size picked
  on the computer?
- Displays: `read_screens()` in flickos-control would keep HEADLESS-PHONE in
  a saved arrangement (no make/model/serial, so its name is used). Leave
  out `HEADLESS-*`. kanshi: no profile matches while it exists (a profile
  needs exactly the connected screens), so kanshi does nothing; check in B5.
- The pointer and new windows can land on a screen nobody looks at
  (B2, B3).
- Port 5900 needs ufw (like `firewall.phones`); a ufw app profile would do.

## Cleanup done

- [x] headless labwc and its wayvncs stopped, runtime folders deleted
- [x] `./second-screen.sh cleanup` (add-on in `~/.config/flickos/addons/`), 15:34; the spike's foot window closed
- [x] `sudo ufw delete allow from 192.168.88.175 to any port 5900 proto tcp` (maintainer, 2026-10-07)
- [ ] AVNC's *FlickOS Second Screen* server deleted (if wanted)
- [ ] `src/` (21 MB of sources) deleted when done reading
- [ ] results written into the design doc
