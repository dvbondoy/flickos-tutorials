# Spike: the phone or tablet as a second screen

Phase 0 of flickos-phone's *Later* item 23 (`docs/design/flickos-phone.md`):
labwc adds a screen that doesn't exist (`VirtualOutputAdd`), wayvnc serves
that one screen, and the phone or tablet shows it in a VNC app. Started
2026-10-07. The answers go into `results.md`, then into the design doc.

```
README.md          this page: questions, predictions, steps
results.md         the answer sheet (part A filled in, B and C are yours)
headless.sh        a throwaway labwc with no screen (part A)
headless/labwc/    its rc.xml: two window rules and two keys
trigger.py         opens one tiny window with a given app id (window-rule trigger)
vnc-check.py       VNC client without a window (gtk-vnc): size, resize, updates
rfb-login.py       VeNCrypt X509Plain login with only Python's stdlib, as AVNC does it
vnc-pointer.py     logs in the same way, then puts the pointer on the VNC screen (a tap)
second-screen.sh   the whole thing on your own session: on / status / off / cleanup
live/              certificate, key and wayvnc config made by second-screen.sh
src/               labwc, wayvnc, neatvnc, KDE Connect and AVNC sources (read, not built)
logs/              everything the programs print
```

**Before each step, write your prediction in results.md.** Then run it. A
wrong prediction is the useful kind: it's where the design was wrong.

---

## The questions, riskiest first

| # | Question | Why it matters |
|---|---|---|
| Q1 | How can a **program** run `VirtualOutputAdd`? labwc has no IPC. | If only a keybind can, the product needs a trick, or the idea dies. |
| Q2 | Does KDE Connect's `kdeconnect.virtualmonitor` open the phone's VNC app? | The design says flickos-phone's free part is exactly that packet. |
| Q3 | Who decides the screen's size? | A 1920×1080 screen squeezed onto a phone is unreadable. |
| Q4 | How does the phone log in, safely? | wayvnc gives whoever logs in your keyboard and mouse. |
| Q5 | What happens when the screen goes away while the phone watches? | Turning it off must never show the main screen. |
| Q6 | What does it cost: disk, memory, CPU, wakeups? | HIG PERF-7. |
| Q7 | What does the desktop do with an extra screen? | Panel, dock, wallpaper, pointer, new windows, kanshi, flick-tiler. |
| Q8 | Does it work on a real phone or tablet through ufw? | The only proof that counts. |

Q1–Q6 are part A (done 2026-10-07, results.md, and you can repeat them).
Q7 is part B, on your own session. Q8 is part C, with the phone.

---

## Part A: in a labwc that has no screen (safe to repeat)

### A1. How a program can press labwc's buttons (Q1)

labwc runs actions from three places: keybinds, menus and **window rules**
(`man labwc-config`, *WINDOW RULES*). A window rule runs its actions when a
matching window opens for the first time (`src/window-rules.c`,
`LAB_WINDOW_RULE_EVENT_ON_FIRST_MAP`), and `VirtualOutputAdd` doesn't need a
window at all (`src/action.c`). Look at the rules:

```sh
cat headless/labwc/rc.xml
```

**Predict:** after `trigger.py flickos-second-screen-on`, how many screens?
Does the tiny window stay open? And after running it a second time?

```sh
./headless.sh start
./headless.sh run wlr-randr                  # one screen, HEADLESS-1
./headless.sh run ./trigger.py flickos-second-screen-on
./headless.sh run wlr-randr                  # ?
./headless.sh run ./trigger.py flickos-second-screen-on
./headless.sh run wlr-randr                  # ?
```

`<action name="Close"/>` closes the trigger window right after it opens.
A second add is refused because the name already exists
(`output_virtual_add` in `src/output-virtual.c`).

The second way is a key that no keyboard has, pressed by a **virtual
keyboard**: `wtype` is one, a Wayland client that makes its own keyboard.
labwc matches a virtual keyboard's keys by keysym (`match_keybinding`,
`src/input/keyboard.c`):

```sh
./headless.sh run wtype -k XF86Launch9       # rule in rc.xml: remove
./headless.sh run wlr-randr
./headless.sh run wtype -k XF86Launch8       # add
```

Which one would you put in a product? (The window flashes for ~25 ms and
lands in the panel's window list unless a rule hides it. The key needs a
virtual keyboard in flickos-phone.)

### A2. Who decides the size (Q3)

**Predict:** the new screen's size, and whether the client can change it.

```sh
./headless.sh run wayvnc -o HEADLESS-PHONE -S "$PWD/logs/a2.ctl" 127.0.0.1 5959 &   # no password: only on 127.0.0.1
sleep 1
./headless.sh run ./vnc-check.py 127.0.0.1 5959 --size 1280x800
./headless.sh run wlr-randr
```

labwc always makes it 1920×1080 (`wlr_headless_add_output(…, 1920, 1080)`).
A VNC client may *ask* for its own size (RFB `SetDesktopSize`), and wayvnc
then changes the screen with wlr-output-management, but **only for a screen
whose name starts with `HEADLESS-`** (`src/output.c`, `is_headless`). That's
why the screen is called `HEADLESS-PHONE`, not `PHONE`.

### A3. The KDE Connect packet (Q2), by reading

```sh
less src/vm-desktop.cpp            # kdeconnect-kde's plugins/virtualmonitor
ls src/kdeconnect-android/src/main/java/org/kde/kdeconnect/plugins/
grep -rl virtualmonitor src/kdeconnect-android/src || echo none
```

**Predict before the `grep`.** Then read `receiveUrl` in
`plugins/share/SharePlugin.kt` and `startActivityFromBackgroundOrCreateNotification`
in `helpers/IntentHelper.kt`: what does the phone show when the computer
sends a `vnc://` link as a share?

### A4. Logging in (Q4)

wayvnc's `enable_auth=true` offers only **VeNCrypt** (TLS with a
certificate, then a username and password), **RSA-AES**, and with
`relax_encryption` Apple DH. Never the old VNC password (`neatvnc
src/server.c`, `ADD_SECURITY_TYPE`). Its VeNCrypt has one subtype, X509Plain
(`src/auth/vencrypt.c`). AVNC on the phone speaks VeNCrypt and, for a
certificate no authority signed, asks once "trust this certificate?"
(`src/avnc/…/VncViewModel.kt`). `rfb-login.py` does the same login in 90
lines of stdlib Python, so you can see every step: read it first.

```sh
cat auth/config                                      # the headless test's config
./headless.sh run wayvnc -C "$PWD/auth/config" -o HEADLESS-PHONE -S "$PWD/logs/a4.ctl" &
sleep 1
./rfb-login.py 127.0.0.1 5960 phone test-secret-1234
./rfb-login.py 127.0.0.1 5960 phone wrong            # predict
./rfb-login.py 127.0.0.1 5960 phone test-secret-1234 --pin 00   # predict
```

### A5. Turning it off in the wrong order (Q5)

**Predict:** a phone is connected and the screen is removed. What does the
phone see next? Does wayvnc keep running?

```sh
./headless.sh run wayvnc -v -o HEADLESS-PHONE -S "$PWD/logs/a5.ctl" 127.0.0.1 5961 > logs/a5.log 2>&1 &
sleep 1
./headless.sh run ./vnc-check.py 127.0.0.1 5961 --seconds 6 &
sleep 2; ./headless.sh run wtype -k XF86Launch9
wait; cat logs/a5.log
```

Then read `registry_remove` in `src/wayvnc-0.9.1/src/main.c`. The size the
client is resized to tells you which screen it now sees.

### A6. Cost (Q6)

```sh
python3 $FLICKOS/tools/package-cost.py wayvnc
apt-cache show libneatvnc0 | grep ^Depends
grep -n h264 src/neatvnc-0.9.1+dfsg/meson.build
./headless.sh run wtype -k XF86Launch9      # first without the screen
python3 $FLICKOS/tools/measure.py --for 10 $(./headless.sh pid labwc)
./headless.sh run wtype -k XF86Launch8
python3 $FLICKOS/tools/measure.py --for 10 $(./headless.sh pid labwc)   # never pgrep labwc: yours runs too
./headless.sh stop
```

---

## Part B: your own session (Q7)

**What you'll see:** a screen you can't see appears to the right of your
monitor. The pointer can go there and get lost: move it back left. Windows
may open there. `./second-screen.sh off` removes it, and labwc moves its
windows back.

Nothing here needs sudo. It writes one add-on folder,
`~/.config/flickos/addons/second-screen-spike/` (two keys), which
`./second-screen.sh cleanup` deletes.

```sh
./second-screen.sh on            # 1280x800, see the printed link
./second-screen.sh status
```

Predict, then check each, and write it in results.md:

1. Does the panel (waybar) appear on the new screen? The dock (Cupertino)?
   The wallpaper? (`grim -o HEADLESS-PHONE logs/phone.png` shows what the
   phone would see.)
2. Move the pointer to the right edge. Where does it go?
3. Open a new window (Super+Enter) while the pointer is on the new screen.
4. Super+T tiling on, then a window on the new screen: does flick-tiler
   tile it there?
5. kanshi: `pgrep -a kanshi`. If a kept arrangement runs, does it move
   anything when the screen appears or goes away?
6. *Settings → Displays*: is HEADLESS-PHONE listed? (Don't save.)
7. Measure labwc with the screen on and nobody watching:
   `python3 $FLICKOS/tools/measure.py --for 30 $(pgrep -u $USER -x labwc)`.
   Compare with the same after `./second-screen.sh off`.

```sh
./second-screen.sh off
```

---

## Part C: the phone or tablet (Q8)

1. Install **AVNC** on the phone (F-Droid or Play; GPL-3, open source).
2. Open the port to your network only (ufw drops it otherwise):
   ```sh
   sudo ufw allow from 192.168.0.0/16 to any port 5900 proto tcp
   ```
3. `./second-screen.sh on 1280x800 --send`. The link goes to the phone
   through flickos-phone. **Predict:** what the notification says.
4. Tap it. AVNC asks to trust the certificate: compare its fingerprint
   with the one printed. Write down how many taps it took.
5. In AVNC: long-press the server → Edit → *Resize remote session to local
   window* on. Disconnect, `./second-screen.sh off`, then `on --send` again:
   does the screen now take the phone's size? (`./second-screen.sh status`)
   And does AVNC survive the resize? (gtk-vnc broke on a 1920×1080 frame
   sent after it.)
6. Drag a window onto the new screen. Scroll a web page in it. Note:
   delay, smoothness, and wayvnc's CPU:
   `python3 $FLICKOS/tools/measure.py --for 30 $(cat live/wayvnc.pid)`.
7. Touch: can you click and type on the phone? Then try `on --view-only`.
8. Turn the phone's screen off for a minute, then on: still connected?
9. `./second-screen.sh off` while AVNC is connected: what does AVNC show?
   (The script stops wayvnc first.)

Clean up:

```sh
./second-screen.sh cleanup
sudo ufw delete allow from 192.168.0.0/16 to any port 5900 proto tcp
```

and in AVNC delete the *FlickOS Second Screen* server if you don't want it.

---

## From results to the design

Each answer becomes a sentence in `docs/design/flickos-phone.md` item 23
(or a design doc of its own), and each choice an ADR with the measured
reason: the trigger (window rule or key), the size (AVNC's resize, or a
size the user picks), the login (VeNCrypt, one certificate per computer, a
new password per session or one per phone), the off order, and the cost
(Debian's neatvnc with libav, or an own build without H.264).
