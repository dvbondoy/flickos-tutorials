# Phone screen spike (scrcpy over Wi-Fi)

Phase 0 for a paid *Show Phone Screen* add-on to flickos-phone. One question
decides whether it is worth anything: **can FlickOS get a phone onto
wireless debugging without a cable and without the user typing adb
commands?** If the answer is "only with a cable and a terminal", the add-on
is plain scrcpy and nobody pays for it.

Nothing here is installed. adb, scrcpy and python3-qrcode are unpacked into
`unpacked/` (by `try-unpacked.sh` and `dpkg-deb -x`), the scrcpy server is in
`server/`, and `env.sh` points your shell at them. The kit's own files
(`check-machine.sh`, `run-measured.sh`, `try-unpacked.sh`) are explained in
`../flickos-spike-kit/README.md`.

```
env.sh       . ./env.sh: use the unpacked adb/scrcpy in this shell
mdns.py      ask the network for a phone's services (Debian's adb can't)
pair-qr.py   QR pairing like Android Studio, then adb connect
results.md   the answer sheet; the computer-only rows are already filled
flickos-phone-ping   flickos-phone with `ping TEXT` and `stop` added (step 7)
bench.sh     one measured, repeatable mirroring run (step 9)
fps-summary.py   sums up scrcpy's fps lines
debs/ unpacked/ server/ logs/   downloaded, unpacked, measured
```

## What was found before you started (no phone needed)

1. **Debian's scrcpy has no phone half.** The `scrcpy` package (contrib,
   trixie-backports 3.3.4) has only the computer program. Its postinst runs
   `/usr/libexec/scrcpy-update-server`, which downloads `scrcpy-server` from
   GitHub (or salsa.debian.org) and checks a sha256 written into the script.
   We did the same by hand:
   ```sh
   curl -fsSL -o server/scrcpy-server https://github.com/Genymobile/scrcpy/releases/download/v3.3.4/scrcpy-server-v3.3.4
   echo "8588238c…079e  server/scrcpy-server" | sha256sum -c
   ```
2. **Debian's adb has no mDNS.** `adb mdns check` prints nothing. Debian's
   build file (`debian/system/adb.mk` in android-platform-tools) leaves out
   `adb_mdns.cpp` and writes stubs instead
   (`std::string mdns_check() {return std::string("");}`). So adb can't find a
   phone by itself: no QR pairing, no automatic reconnect. `mdns.py` does that
   part instead (about 200 lines, stdlib).
3. **Which mDNS works through FlickOS's firewall.** The control was the
   phone's KDE Connect service, which is always advertised:
   ```sh
   ./mdns.py -v kdeconnect                     # one-shot query: nothing
   ./mdns.py -v --to 192.168.88.172 kdeconnect # ask the phone directly: nothing
   ./mdns.py -v --listen kdeconnect            # from port 5353: found
   ```
   Only real mDNS works: send from port 5353 and listen to the group
   224.0.0.251. ufw's `before.rules` lets that group in. A one-shot query
   gets its answer by unicast, which ufw drops (or the phone never sends it;
   telling which needs `sudo tcpdump`, and it doesn't change the design).
   Binding 5353 works because nothing else uses it. avahi-daemon would, and
   it isn't in the image.
4. **Disk cost** (`tools/package-cost.py`, compared with the image):
   adb 3.7 MB (7 packages), scrcpy **57 MB** (16 packages). Most of the
   scrcpy cost isn't scrcpy: `libavdevice61` pulls `libavfilter10`, which
   pulls `libflite1` (speech synthesis, 27 MB) and `libplacebo` (9 MB).
   scrcpy uses libavdevice only for its V4L2 output (`--v4l2-sink`), so a
   scrcpy built with `-Dv4l2=false` would need SDL2 + scrcpy, about 2.3 MB.
   python3-qrcode: 183 KB.

## Your part (needs the phone, about 20 minutes)

Write each prediction in `results.md` **before** you run its step.

### 0. A terminal in this folder

```sh
cd ~/Documents/flickos-tutorials/flickos-mirror-spike
. ./env.sh
```
The `.` runs `env.sh` *in* your shell (not in a child shell), so the
variables it sets stay. It prints which adb and scrcpy you now get.

### 1. Turn on wireless debugging on the phone (count the taps)

- Settings → About phone → tap *Build number* seven times (Developer options
  appear; Android asks for your PIN).
- Settings → System → Developer options → *Wireless debugging* → on → allow
  on this network.

Count how many taps and screens this took: in the product, this is what a
user must do before anything we build can help. Write it in Q6.

### 2. Can we see it? (Q1, first half)

```sh
./mdns.py --listen connect kdeconnect
```
`connect` is the phone's `_adb-tls-connect._tcp` service, advertised while
Wireless debugging is on. Expect two services: KDE Connect (the control) and
`adb-SERIAL-xxxx` with a port in the 30000–45000 range. Without the control
you couldn't tell "wireless debugging is not advertised" from "mDNS is
broken".

### 3. Pair by QR (Q1)

```sh
./pair-qr.py
```
On the phone: Wireless debugging → *Pair device with QR code* → scan the
code in the terminal (or `xdg-open qr.png`). The script waits for the phone
to advertise `_adb-tls-pairing._tcp` under the name in the code, runs
`adb pair ADDR:PORT PASSWORD`, then finds the connect port and runs
`adb connect`. Each line has the seconds since start. At the end
`adb devices -l` should list the phone as `device` (not `unauthorized`).

If the QR fails, the control is the code method: *Pair device with pairing
code* shows `IP:PORT` and six digits; run `adb pair IP:PORT 123456`.

### 4. Mirror and measure (Q4)

```sh
adb devices                       # copy the ADDR:PORT of the phone
./run-measured.sh --int -- scrcpy -s ADDR:PORT --print-fps
```
`run-measured.sh` starts scrcpy, measures its CPU and memory with the repo's
`tools/measure.py`, and stops it with SIGINT (like Ctrl+C) when you press
Enter in the terminal. While it runs, try and note in results.md:

- scroll a web page: smooth? (fps lines in `logs/…-scrcpy.log`)
- type on the computer's keyboard into a phone text field
- copy text on the computer, Ctrl+V in the phone window, and the other way
- drag a photo onto the window (scrcpy pushes files to `/sdcard/Download`)
- play a video: does the sound come out of the computer? (Android 11+)

Then measure the adb server that stays running between uses:
```sh
~/Documents/Projects/FlickOS/tools/measure.py $(pgrep -u "$USER" -x adb)
```
(Ctrl+C after about 30 seconds; it prints the summary.)

### 5. Does it come back by itself? (Q2, the second deciding question)

Each case: do it, then run `./pair-qr.py --connect-only` and note whether it
connects, with which port, and whether the phone asked anything.

a. Wireless debugging off and on again on the phone.
b. Phone's Wi-Fi off and on.
c. Phone restarted.

Android turns Wireless debugging off after a restart (prediction: after b
too). Check whether *Developer options → Quick settings developer tiles →
Wireless debugging* gives a one-tap tile; that would be the step we tell
users to use.

### 6. Can flickos-phone open the setting for them? (Q3)

```sh
flickos-phone send 'intent:#Intent;action=android.settings.APPLICATION_DEVELOPMENT_SETTINGS;end'
```
flickos-phone sends it as a web address; the phone shows a notification and
tapping it asks Android to open the address. `market://` worked that way
on 2026-10-02. Prediction: nothing opens, because `intent:` is a link format
only browsers understand, not a scheme an app claims.

### 7. A reminder on the phone (design doc Q4)

When the computer can't find the phone's Wireless debugging, the add-on
could send a KDE Connect *ping* with a text, so the reminder shows up on the
phone where the switch is. flickos-phone can't send one yet, so
`flickos-phone-ping` is a copy of the repo's `flickos-phone` with two spike
commands added: `ping [TEXT]` and `stop` (stops the daemon but keeps the
pairing; `set enabled no` would delete the state, so don't use that).

Swap the installed daemon for the copy (it uses the same pairing):
```sh
./flickos-phone-ping stop            # stops the installed daemon
./flickos-phone-ping daemon &        # the copy, in this terminal
./flickos-phone-ping status          # wait until the phone shows as connected
```
Then, with Wireless debugging **on** (the phone is awake and connected):
```sh
./flickos-phone-ping ping
./flickos-phone-ping ping "Turn on Wireless debugging: Settings > System > Developer options"
```
Note for each: did a notification show, what were its title and text, was
the long text cut, did it make a sound, and what happens when you tap it.

Then the case the reminder is for. Restart the phone, unlock it, and **do
not open the KDE Connect app**:
```sh
./flickos-phone-ping status          # did the phone reconnect by itself?
./pair-qr.py --connect-only          # expect: no connect service (debugging is off)
./flickos-phone-ping ping "Turn on Wireless debugging"
```
Repeat with the phone's Wi-Fi off and on instead of a restart. Prediction:
the ping arrives in both cases, because KDE Connect reconnects on its own.

Put the installed daemon back:
```sh
./flickos-phone-ping stop            # stops the copy (its `&` job ends)
setsid -f flickos-phone daemon       # the installed one, detached from this terminal
flickos-phone status
```
(Logging out and in again does the same.)

### 8. Sharing port 5353 with avahi-daemon (design doc Q7)

Our mDNS binds UDP port 5353, the port of the computer's own mDNS service.
FlickOS has none, but a user may install avahi-daemon (it comes with
printer and file sharing tools). Can both have the port?

avahi's `avahi-core/socket.c` (Debian 0.8-16) sets `SO_REUSEADDR` and
`SO_REUSEPORT` before binding, as `mdns.py` does. Linux lets UDP sockets share
a port when all of them set `SO_REUSEADDR`, whoever owns them
(`SO_REUSEPORT` alone would need the same user, and avahi's socket is
root's). Every socket in the group gets a copy of each multicast packet.
Prediction: both work, in either order, and avahi logs a warning about
"another mDNS stack" on this computer.

**a. Without installing anything:** a stand-in socket owned by root, with
avahi's options, holds the port while you search.
```sh
# terminal 1: hold 5353 the way avahi does (Ctrl+C to stop)
sudo python3 -c 'import socket, time
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
s.bind(("", 5353))
s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
             socket.inet_aton("224.0.0.251") + socket.inet_aton("0.0.0.0"))
print("holding 5353 as root"); time.sleep(600)'

# terminal 2
ss -ulnp 'sport = :5353'                # the stand-in's socket
./mdns.py --listen connect kdeconnect   # still finds the phone?
```

**b. With the real avahi-daemon** (the deciding test; undo at the end):
```sh
sudo apt install --no-install-recommends avahi-daemon   # starts it too
ss -ulnp 'sport = :5353'                # avahi's socket
./mdns.py --listen connect kdeconnect   # avahi first: still finds the phone?
./mdns.py --listen --seconds 30 connect kdeconnect &
sudo systemctl restart avahi-daemon     # ours first: does avahi start?
systemctl status avahi-daemon --no-pager
journalctl -u avahi-daemon -b --no-pager | tail -20   # the warning?
sudo apt purge avahi-daemon && sudo apt autoremove --purge
```
In both tests, keep Wireless debugging on so `connect` has something to
find. KDE Connect is the control, as in step 2.

### 9. Mirroring settings (design doc Q9)

Run 1 (step 4) dropped 27% of the frames at full size (1080×2400) with
scrolling by hand, which no other run can repeat. `bench.sh` makes each run
the same: scrcpy for 70 s, and after 6 s adb scrolls the phone down and up
for 60 s (`adb shell input swipe`). It measures scrcpy with
`tools/measure.py` and sums up the fps lines with `fps-summary.py`
(average over the seconds that had frames, frames skipped, seconds at 20 fps
or more). Compare the shown fps: skipped frames mean "too slow" only while
it is low, since a phone that sends more frames than the screen shows has
some skipped anyway.

Three settings might help the HD 4400:
- `--max-size 1024`: the phone sends 1024 pixels high instead of 2400, so
  there is about a fifth as much picture to decode and draw.
- `--no-mipmaps`: scrcpy builds smaller copies of every frame for a sharper
  scaled-down picture ("Trilinear filtering enabled" in the log); this turns
  that off.
- `--render-driver=opengles2`: SDL draws with OpenGL ES instead of OpenGL.

Before each run: Wireless debugging on, the phone connected
(`./pair-qr.py --connect-only`), unlocked, showing *Settings → Apps → See
all apps*, and nothing moved on the computer. Write your prediction for
each in results.md, then:
```sh
./bench.sh full                      # scrcpy's defaults, the baseline
./bench.sh m1024 --max-size 1024
./bench.sh nomip --no-mipmaps
./bench.sh m1024-nomip --max-size 1024 --no-mipmaps
./bench.sh m1024-gles --max-size 1024 --render-driver=opengles2
./fps-summary.py logs/bench-*-scrcpy.log   # all of them together
```
Each run prints its fps line and measure.py's summary (CPU, memory). Also
note whether the picture looked smooth, and whether it got blurry or the
text hard to read: the smaller the picture, the less sharp it is on the
computer.

Then, in one run with the best settings (`./bench.sh check OPTIONS`, or
`scrcpy -s ADDR:PORT OPTIONS` without a time limit), check by hand:
- **Sound:** play a video on the phone. Does the sound come out of the
  computer? Does the phone still play it too (it shouldn't, without
  `--audio-dup`)? Is it in sync with the picture?
- **Typing:** click a text field in the phone window and type on the
  computer's keyboard, including `é` and `ñ`. If some letters don't
  arrive, try again with `--keyboard=uhid` (the phone then sees a real
  keyboard; its keyboard layout is set on the phone).
- **Clipboard:** copy text on the computer, click a text field in the
  phone window, press Ctrl+V. Then copy text on the phone and paste it on
  the computer.
- **Dropping a file:** drag a photo from Thunar onto the window. It should
  appear in the phone's *Download* folder.

### 10. The adb server while idle (design doc Q10)

adb keeps a server running after scrcpy closes, until `adb kill-server`.
The add-on would stop it after a while, so what it costs in between
decides how long "a while" can be. With no phone connected (measured
2026-10-02): 5.8 MB PSS, 0.1% CPU, about 314 wakeups/min. The case that
matters is with the phone still connected, right after a mirror closed:

Wireless debugging must be on first (Android turns it off after a restart
or a Wi-Fi change); `bench.sh` stops at once without a phone.
```sh
./pair-qr.py --connect-only                # the phone must be listed as device
./bench.sh idle-before --max-size 1024     # any short mirror, then it closes
~/Documents/Projects/FlickOS/tools/measure.py --for 120 $(pgrep -u "$USER" -x adb)
"$ADB" devices                             # still connected?
```
Prediction: a little more memory than without a phone, and more wakeups
(adb keeps the TLS connection to the phone alive).

## Cleanup (when done)

```sh
adb disconnect; adb kill-server
rm -rf ~/.android          # created by the first adb run on 2026-10-02 02:25
```
On the phone: Wireless debugging → forget the paired computer, turn
Wireless debugging off. Developer options can stay or go (*Developer
options* switch at the top). Then the spike folder's `debs/`, `unpacked/`,
`server/`, `logs/` can be deleted; nothing was installed.
