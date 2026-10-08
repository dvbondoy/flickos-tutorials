# Phone screen spike: results

Date: 2026-10-02  Design doc: `docs/design/flickos-phone-screen.md` (Proposed 2026-10-02; untested items are its open questions)
Machine: i3-4030U, FlickOS on trixie, phone HMD CREST at 192.168.88.172 (KDE Connect paired)

Write the **prediction before** each test and the **result after**. Where
they differ, add one line on why.

## Questions

| # | Question | Why it matters | Prediction | Result | Evidence |
|---|---|---|---|---|---|
| Q1 | Can FlickOS pair the phone over Wi-Fi by QR, with Debian's adb? | No cable and no typed adb commands is the only thing worth paying for | Yes, with our own mDNS | **QR: no** (failed, what was shown not recorded). **Pairing code: yes**, `adb pair IP:PORT CODE` by hand; then mDNS found and connected the phone. Android 14's `AdbQrCode.java` accepts our QR text, so suspect the terminal scan or our search; QR re-test also did nothing (left for later, design Q12). Third try with `-v` listing records and a 4-module quiet zone: the phone announced only `_adb-tls-connect` (port 33875), never a pairing service, so it didn't read or rejected the code. `./pair-qr.py --code`: pairing service found at 3.0 s, paired 12.0 s, connected 12.3 s (Q13 yes) | maintainer, 2026-10-02 |
| Q2 | After Wireless debugging goes off (toggle, Wi-Fi, restart), what must the user do again? | Decides whether "one click from the panel" is real or a phone chore every time | Pairing stays; the user turns Wireless debugging on again; the port changes, mDNS finds it | **As predicted.** Pairing kept in all 3 cases. Toggle: reconnect at once. Wi-Fi off/on **and** restart: Android turns Wireless debugging off, the user must turn it on again. New port every time (33225, 33119, 39767, 40145); mDNS found it in 0.1–1.2 s, connected in ≤ 1.7 s. Old ports stay as `offline` in `adb devices` until disconnected | step 5 |
| Q3 | Can flickos-phone open the phone's developer settings? | Would save the user hunting for the switch | No (`intent:` isn't a scheme apps claim) | **No** (maintainer, 2026-10-02) | step 6 |
| Q4 | Is scrcpy over Wi-Fi usable on this machine, and what does it cost? | i3-4030U is the low end FlickOS targets | Usable; one core for H.264 decode | **Usable, not smooth.** 1080×2400, OpenGL (Mesa, HD 4400): average 15.5 fps, best 39, 45 of 147 s at ≥ 20 fps, 844 frames decoded but skipped (27%). CPU 71.6% average, 106% peak (of one core) | step 4 |
| Q5 | Does mDNS get through FlickOS's ufw? | Discovery is the base of Q1 and Q2 | Only multicast from 5353 | **Yes, only that way.** One-shot and unicast queries: no answer | `./mdns.py -v [--to IP] [--listen] kdeconnect`, 2026-10-02 |
| Q6 | How many steps on the phone before the first pairing? | What the add-on's first-run guide must cover | ~10 taps (Build number ×7 + PIN, then the switch) | **14 taps:** Developer options 10, Wireless debugging 4. No quick settings developer tiles on the HMD CREST, so the 4 taps repeat after every restart or Wi-Fi change | maintainer, 2026-10-02 |
| Q7 | Does Debian's adb do mDNS? | If not, we write discovery | Yes | **No**: stubbed in Debian's `adb.mk` | `adb mdns check` empty; sources.debian.org android-platform-tools 34.0.5-12 |
| Q8 | Is Debian's scrcpy complete? | What a package can depend on | Yes | **No**: server downloaded from GitHub by postinst, sha256 pinned | `debs/x/DEBIAN/postinst`, `scrcpy-update-server` |
| Q9 | Can a KDE Connect ping remind the user to turn Wireless debugging on? (design Q4) | The one step the add-on can't do for them, after every restart or Wi-Fi change | Yes: KDE Connect reconnects by itself, the ping shows as a notification with our text; tapping it opens the KDE Connect app, not the setting | **Shows, with Wireless debugging on:** a notification titled with the computer's KDE Connect name, the whole text shown (at first missed it: check it doesn't arrive quietly). Not yet: sound, tap, after restart / Wi-Fi change | step 7 |
| Q10 | Can our mDNS and avahi-daemon share UDP 5353? (design Q7) | A user who installs avahi must not lose Show Phone Screen | Yes, in either order: both set SO_REUSEADDR (avahi's socket.c); avahi logs "another mDNS stack" | **Yes, avahi first:** with avahi-daemon 0.8-16 running, `mdns.py --listen` found Wireless debugging (39891) and KDE Connect in 3 s. Ours first: avahi restarted without error, but the search's output, avahi's status and its log weren't read (journal needs sudo). avahi purged after; nothing left on 5353 | step 8 |
| Q11 | Which settings stop the dropped frames? (design Q9) | 27% skipped at full size; the default the product ships | `--max-size 1024` fixes most of it; mipmaps and the render driver matter less | | step 9, `bench.sh` |
| Q12 | Sound, typing, clipboard both ways, dropping a file (design Q9) | What the add-on can promise | All work; letters like é may need `--keyboard=uhid` | | step 9 |

## Cost (HIG PERF-7)

| What | Number | How measured |
|---|---|---|
| disk: adb | 3668 KB, 7 packages | `tools/package-cost.py adb` |
| disk: scrcpy (Debian, backports) | 57561 KB, 16 packages (libflite1 27.5 MB, libavfilter10 14 MB, libplacebo 9 MB) | `tools/package-cost.py debs/scrcpy_3.3.4-1~bpo13+1_amd64.deb` |
| disk: QR code | python3-qrcode 183 KB | `tools/package-cost.py python3-qrcode` |
| memory: scrcpy PSS / Private, mirroring | 88.7 MB / 76.4 MB (highest) | `run-measured.sh`, 150 s, 2026-10-02 10:52 |
| CPU while mirroring (scrolling), fps | 71.6% avg, 106.4% peak; 100244 wakeups/min; 15.5 fps avg, 27% frames skipped | same run; fps from `logs/20261002-105209-scrcpy.log` |
| memory: adb server idle, no phone | 5.8 MB PSS / 5.6 MB Private; CPU 0.1% avg; 314 wakeups/min | `tools/measure.py --for 30 PID`, 2026-10-02; again over 72 s: 5.8 MB, 247 wakeups/min |
| memory: adb server idle, phone connected, mirror closed | 6.9 MB PSS / 6.7 MB Private; CPU about 0.1%; 276–360 wakeups/min (phone still `device`) | `tools/measure.py --for 120 PID` after `bench.sh idle-before`, 2026-10-02 |
| time: pairing screen opened → connected | 12.3 s, six digits typed included | `pair-qr.py --code` |

## Runs

| Run | Command | Prediction | Result | Notes |
|---|---|---|---|---|
| 1 | `run-measured.sh --int -- scrcpy -s 192.168.88.172:33225 --print-fps` | one core, smooth | 72% CPU, 89 MB PSS, 15.5 fps avg, 27% skipped | icon error: Debian's icon path isn't in unpacked/ (harmless) |
| 2 | `pair-qr.py --connect-only` after toggle / Wi-Fi / restart | reconnects after the user turns it on | yes, 0.1–1.7 s; Wi-Fi and restart turn it off | stale `offline` entries |
| 3 | `bench.sh full` | | | same scrolling every run (adb `input swipe`) |
| 4 | `bench.sh m1024 --max-size 1024` (run as `idle-before`) | | 52.9 fps avg over 53 s, best 86, 44 s at ≥ 20 fps; 48% skipped; CPU 53.7% avg, 92% peak; PSS 70 MB; 98487 wakeups/min | more frames than the screen can show, so skipped no longer means too slow; compare shown fps with `full` (run 3) |
| 5 | `bench.sh nomip --no-mipmaps` | | | |
| 6 | `bench.sh m1024-nomip --max-size 1024 --no-mipmaps` | | | |
| 7 | `bench.sh m1024-gles --max-size 1024 --render-driver=opengles2` | | | |

## New questions found on the way

- A FlickOS-built scrcpy with `-Dv4l2=false` would drop libavdevice and ~55 MB. Would that build still need the downloaded server (yes), and is shipping that prebuilt file in a paid package fine (Apache-2.0: yes, with LICENSE/NOTICE)?
- Port 5353: our mDNS must share it if a user installs avahi-daemon (SO_REUSEPORT on our side; does avahi allow sharing?).
- Skipped frames: is the renderer (scaling 1080×2400 with trilinear filtering on HD 4400) the limit? Try `-m 1024` and `--render-driver=opengles2`.
- The product must `adb disconnect` the old address when the port changes.

## Cleanup done

- [ ] `adb disconnect; adb kill-server`; `rm -rf ~/.android`
- [ ] phone: forget the computer, Wireless debugging off
- [ ] `debs/`, `unpacked/`, `server/`, `logs/`, `qr.png` deleted
- [x] results written into a design doc
