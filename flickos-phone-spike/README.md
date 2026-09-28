# The flickos-phone spike (phase 0), 2026-09-27

> Set `TUTORIALS` to the root of the [tutorials repository](https://github.com/dvbondoy/flickos-tutorials) and `FLICKOS` to your clone of [FlickOS](https://github.com/dvbondoy/FlickOS). Paths below use those two variables. Scripts read the FlickOS checkout from `FLICKOS_REPO` or `FLICKOS`.

This folder has the scripts from phase 0 of
`docs/design/flickos-phone.md` (in the FlickOS repo) and the file manager
tests. This guide goes through what we did, in order, and the ideas behind
each step, so you can do the same for the next design. The spike's private
key, the paired-phone certificate, the session log, the photos, and the
kdeconnect-kde sources we read are not in this repository.

The results themselves are in the design doc, under *Phase 0 results*. This
guide is about **how** we got them.

```
README.md              this guide
phone-spike.py         the spike: a KDE Connect peer in stdlib Python
fake-phone.py          a pretend phone, for testing the spike without one
test-loopback.sh       runs the two together on 127.0.0.1
libfm-actions/         the file manager tests (see step 7)
```

Left on the machine where the spike was run, and not published: `phone-state/`
(identity and private key), `run-2026-09-27/` (the log and the photos), and
`kdeconnect-source/` (the kdeconnect-kde files read in step 1).

---

## 0. What a spike is, and why FlickOS designs start with one

A **spike** is a small, throwaway program that answers the questions a
design can't answer on paper, **before** anything is built. It's phase 0 in
every FlickOS design doc (flickos-menu, flick-tiler and flickos-control had
one too).

The rules we followed:

1. **List the questions first.** The design's phase 0 had a list: does the
   app find us without mDNS? does Python's `ssl` do what we need? what does
   the phone send? can the file manager hide an action? what does it cost?
   Each step below answers one.
2. **Go for the riskiest question first.** If Python's `ssl` couldn't do the
   encryption, the whole "stdlib only, no new library" idea would fall. So
   that was checked first, and the file manager last.
3. **As little code as possible.** One file, threads instead of a proper
   event loop, `input()` for commands. It only has to answer the questions,
   not be the product. The real daemon will be written fresh.
4. **Test the spike before the real thing.** A fake phone on loopback found
   my bugs before your time was spent on them (step 3).
5. **Log everything with timestamps.** The log was how we found the one real
   bug of the session (step 4).
6. **Write the results into the design** and change the decisions they
   contradict. A spike whose results only live in a chat is lost.

---

## 1. Read the source, not only the documentation

The design doc was written from memory and documentation. Before writing
code, we checked the facts against the real source:

- **Valent's protocol page** (valent.andyholmes.ca) describes the packets
  but *not* who is TLS server and client, the certificate fields or how the
  verification key is made. Those were exactly the things we needed.
- **kdeconnect-kde's source** has all of them (master on 2026-09-27,
  probably commit `f6d952b`, from
  `https://invent.kde.org/network/kdeconnect-kde/-/raw/master/<path>`).
  Download the files named in the table below if you want to read them
  again. Those copies are not in this repository.

What to look at in each file:

| File | What it told us |
|---|---|
| `lanlinkprovider.h` | the ports: `UDP_PORT = 1716`, TCP `1716–1764` |
| `lanlinkprovider.cpp` | `udpBroadcastReceived` → `deviceDiscovered` (whoever hears a broadcast connects), `tcpSocketConnected` (the connector calls `startServerEncryption()`: the comment says *"I'm the client TCP socket"*), `tcpPacketReceived` (the acceptor calls `startClientEncryption()`), `encrypted` (both send their identity again inside TLS, 1 s timeout), `recoverConnectionError` (the "reverse connection": answer with UDP so the other side connects), `MAX_IDENTITY_PACKET_SIZE = 8192`, protocol < 8 refused |
| `pairinghandler.cpp` | the `pair`/`timestamp` packets, the 30 s timeout, and `verificationKey()`: SHA-256 of the bigger public key, the smaller one, and the timestamp, first 8 hex digits |
| `sslhelper.cpp` | the certificate: EC P-256, `O=KDE, OU=KDE Connect, CN=<device id>`, SHA-512, valid 1 year back to 10 years ahead |
| `kdeconnectconfig.cpp` | the device id is a UUID without dashes (32 hex digits) |
| `networkpacket.cpp` | a packet is JSON with `id` (milliseconds), `type`, `body`, and a newline |
| `landevicelink.cpp` | receiving a file: connect to the given port with `connectToHostEncrypted`, a normal TLS client |
| `shareplugin.cpp` | what a file packet carries: `filename`, `creationTime`, `lastModified`, `open` |

A tip for finding things fast: download the files and `grep` them yourself
(`grep -n "Encryption" *.cpp`) rather than asking a web tool to summarize
them. Summaries leave out the exact line you need.

---

## 2. The idea everything rests on: who is the TLS server

KDE Connect's handshake looks like this:

```
 computer (spike)                           phone (KDE Connect app)
 ────────────────                           ───────────────────────
 UDP broadcast to :1716  ───────────────▶   "a computer is here, TCP port 1716"
                                            (whoever hears a broadcast connects)
 accept on TCP 1716      ◀───────────────   TCP connect
                         ◀───────────────   plain identity line (JSON + \n)
 TLS CLIENT              ◀══════════════▶   TLS SERVER   ← the swap: the TCP
 (sends its cert too)                                       connector is the TLS server
 full identity           ◀══════════════▶   full identity (inside TLS, within 1 s)
 ... packets, one JSON per line, both ways ...
```

**Why it matters.** Python's `ssl` module can't "ask for a certificate but
accept any certificate" (Qt calls that `QueryPeer`). As a TLS *server*
it either doesn't ask for the other side's certificate or rejects one it
doesn't already trust. For pairing we must see an **unknown** phone's
certificate. So the plan was: **never be the one who connects**, then we're
always the TLS *client*, and a client can connect with `CERT_NONE`, get the
phone's certificate with `getpeercert(binary_form=True)` and check it
itself (against the one saved at pairing).

The one place we must be a TLS server is when *we* send a file (the phone
connects to fetch it). But by then the phone is paired, so we know its
certificate and can make it the only one we trust:

```python
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.verify_mode = ssl.CERT_REQUIRED
ctx.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN   # a self-signed cert may be the anchor
ctx.load_verify_locations(cadata=phone_cert_pem)
```

Both halves worked with your phone. That was the biggest risk of the
design, and it's why no extra library (pyOpenSSL, 4 MB) is needed.

---

## 3. Check the machine, then test on loopback first

**Check what's already there** before running anything on the network:

```sh
ss -lnup | grep 1716; ss -lntp | grep 1716   # is KDE Connect or anything else on the port?
grep ENABLED /etc/ufw/ufw.conf               # is the firewall on?
grep DEFAULT_INPUT_POLICY /etc/default/ufw   # what does it do with incoming? (DROP)
nmcli -t -f NAME,UUID,TYPE,DEVICE connection show --active
python3 -c "import ssl; print(ssl.OPENSSL_VERSION, hasattr(ssl,'VERIFY_X509_PARTIAL_CHAIN'))"
```

That found the first real fact: **ufw is on and drops incoming
connections**, so the phone couldn't reach the computer at all without a
rule. That became part of the design (the firewall row on the Phone page).

**Then test the spike against a fake phone** on 127.0.0.1, before involving
you and your phone:

```sh
./test-loopback.sh
```

`fake-phone.py` does what the app does, in the same order: connect, plain
identity, TLS as server, identities, a page **before** pairing (must be
dropped), a pair request, a page after, and a file called `../.evil.txt`
(must be saved as `evil.txt`, not outside the folder). It checks the
handshake, the security rules and the file name cleaning, with no network,
no firewall change and no phone. It uses a throwaway identity in a temp
folder, so `phone-state/` isn't touched.

---

## 4. The real phone, and the bug the log showed

You opened one firewall port and started the spike:

```sh
sudo ufw allow proto tcp from 192.168.88.0/24 to any port 1716 comment 'flickos-phone spike'
python3 phone-spike.py
```

Only TCP 1716 on purpose: if that's enough, the firewall rule in the design
can be smaller. It was enough. The phone connected **10 seconds** later,
from our broadcast alone, without mDNS and without incoming UDP.

**The bug.** Then the log showed this, over and over:

```
[   15.2s] LINK up: HMD CREST (not paired)
[   15.2s] LINK down: HMD CREST
[   20.2s] LINK up: HMD CREST (not paired)
[   20.2s] LINK down: HMD CREST
[   25.2s] ...
```

**How it was diagnosed.** The timestamps are exactly 5 seconds apart, and 5
seconds was the spike's `ANNOUNCE_SECONDS`. The spike announced "until a
phone is *paired*", and the phone answers **every** broadcast with a new
connection, even while it's already connected. The spike replaced the old
link with the new one, and the pair request you'd sent was on the old link,
so it was lost (`pair request … timed out`). The fix was one line: announce
only while **no phone is connected**. The design took two lessons from it:
the announce rule, and "a pair request belongs to the phone, not to one
connection".

(The fix needed the spike restarted: a running Python program doesn't pick
up changes to its file.)

**Pairing.** You tapped *Request pairing* on the phone, the spike printed a
verification key, and `y` accepted it:

```
[    9.0s] PAIR REQUEST from HMD CREST: timestamp 1790489975 (clock skew -1s), verification key D23106FC
[   14.4s] PAIRED with HMD CREST (we accepted)
```

The key is how the two people (or one person with two screens) know no one
is in the middle. **Not recorded:** whether your phone showed the same
D23106FC. Check that next time you pair: if the phone shows something else,
`verification_key()` in the spike is wrong.

---

## 5. Phone → computer: what the app really sends

Each test was one thing from the phone. The session log and the photos
are not in this repository. This is what arrived:

| You did | The packet | What the design took from it |
|---|---|---|
| Share a page | `kdeconnect.share.request` `{"url": …}` | From Facebook's browser the address came with `&amp;` instead of `&`, and full of `utm_*`/`fbclid` tracking. Undo `&amp;`; maybe strip tracking (Q6) |
| Share selected text | `{"text": "\"…\"\n https://…#:~:text=…"}` | Chrome adds a link to the spot on the page, so text notifications get an *Open* button too |
| Share a photo | `{"filename", "lastModified": 0, "numberOfFiles", "totalPayloadSize"}` + `payloadSize`, `payloadTransferInfo.port` | We connect to the phone's port 1739 as a normal TLS client. Same certificate as the link. The date can't be kept (0). Sent twice: the second became `… (2).jpg` |
| Send clipboard | `kdeconnect.clipboard` `{"content": …}` | as expected |
| Ping | `kdeconnect.ping` `{}` | as expected |

---

## 6. Computer → phone, and a second firewall finding

Commands typed into the spike: `url …`, `text …`, `clip …`,
`file /usr/share/backgrounds/flickos/redmond.jpg`.

- Page and text: a **notification on the phone**, opened when you tapped it.
  Nothing opened by itself, the same rule the design has for the computer.
- Clipboard: set on the phone.
- The file **failed** at first, as predicted: the phone has to connect
  **back** to a port 1739–1764 on the computer to fetch it, and the
  firewall only allowed 1716. After

  ```sh
  sudo ufw allow proto tcp from 192.168.88.0/24 to any port 1739:1764 comment 'flickos-phone spike'
  ```

  it worked (1.2 MB in 0.7 s), with the spike as TLS server checking the
  phone's pinned certificate (step 2). One attempt broke off after TLS
  (`BrokenPipeError`) and the next worked; the cause is unknown (Q7).

A small thing about predicting: I said the file would fail *before* you
tried it, and why. When it did, that confirmed the explanation, not just the
symptom. Write your prediction down before each test.

---

## 7. The file manager: finding a missing piece by elimination

The question: can PCManFM show *Send to Phone* only while the feature is on?
The FreeDesktop "file manager actions" spec has `ShowIfTrue` (run a command,
show if it prints `true`), `ShowIfRunning` and `TryExec`.

**Round 1: nothing showed at all**, not even the action that should show.
When *everything* fails, the problem is before your test, so:

1. Add a **control**: an action with no conditions at all. Still nothing.
   So libfm isn't reading the folder, whatever the conditions say.
2. Check the library knows about actions at all:
   `strings /usr/lib/x86_64-linux-gnu/libfm.so.4 | grep ShowIfTrue` → yes.
3. Check who *uses* that code: `nm -D --undefined-only libfm-gtk3.so.4`
   showed that the GTK menu library never calls the action functions. They
   come from a loadable module.
4. `apt-get download libfm-modules; dpkg -c libfm-modules_*.deb` →
   `gtk-menu-actions.so` is in it, and it isn't installed.
5. `apt-cache show libfm4t64 | grep Recommends` → `libfm-modules`. FlickOS's
   image leaves out Recommends (`--apt-recommends false`), so it's missing
   on every FlickOS system. That's a finding on its own (Q8): PCManFM's
   search and `menu://` view are probably missing too.

After `sudo apt install libfm-modules`, the rounds in `libfm-actions/`:

| Round | Action | Shown? | Means |
|---|---|---|---|
| 1 | `control` (no condition) | yes | actions work now |
| 1 | `ShowIfTrue=sh -c "echo false"` | **yes** | ShowIfTrue ignored… |
| 1 | `TryExec=/nonexistent/…` | no | TryExec works |
| 2 | `ShowIfTrue=/usr/bin/echo false`, in the action and in the profile | **yes** | …not a quoting problem: ignored everywhere |
| 3 | `ShowIfRunning=flickos-nothere` | **yes** | ignored too |
| 4 | `TryExec=labwc` / `TryExec=flickos-nothere` | yes / no | TryExec searches `PATH` |

So the design uses the one thing that works: `TryExec=flickos-phone-on`, and
a link with that name in a folder on the session's `PATH` that exists only
while the feature is on.

To repeat a round: `libfm-actions/try.sh round-3`, reopen PCManFM,
right-click a file. `try.sh remove` cleans up.

The pattern to remember: **one variable per test, and a control that must
pass.** Without the control, round 1 would have "shown" that ShowIfTrue and
TryExec both work (nothing appeared, so everything was "hidden").

---

## 8. Measuring what it costs

FlickOS's HIG asks every feature to state its cost (PERF-7). Two numbers:

**Memory**: the spike's `mem` command reads `/proc/self/smaps_rollup`.
**PSS** (proportional set size) is the fair number: shared libraries count
only by the share this process uses. RSS counts them in full and overstates.
Result: 13.6 MB PSS with the phone connected.

**Wakeups**: how often the process runs while it should be idle. Count
context switches over a minute, across all threads:

```sh
pid=$(pgrep -f phone-spike.py)
sum() { cat /proc/$pid/task/*/status | awk '/voluntary_ctxt_switches/ {s+=$2} END {print s}'; }
a=$(sum); sleep 60; b=$(sum); echo $((b-a))
```

Result: 13 a minute, nearly all from the spike's own 5-second timer. The
phone sends nothing while idle. So the daemon's wakeups will come from
FlickOS's own code, not the phone.

---

## 9. Where the results went

Into `docs/design/flickos-phone.md`:
- ADR-001: the protocol, now from the source and checked with the phone.
- ADR-003: the TLS roles confirmed, no pyOpenSSL, the announce rule, the pair
  request per phone.
- ADR-004: memory and wakeups.
- ADR-006: what phones send (`&amp;`, links in text, `lastModified: 0`).
- ADR-007: the file manager (`libfm-modules`, `TryExec` + `PATH`), what the
  phone does with what it gets.
- ADR-009: the firewall ports (TCP 1716 and 1739:1764, no UDP).
- *Phase 0 results*: the table. Q4 answered; new Q6–Q8.

Still open: the verification key comparison, the app's version, the broken
file send (Q7).

---

## 10. Running it again, and cleaning up

```sh
cd "$TUTORIALS/flickos-phone-spike"
./test-loopback.sh                    # no phone needed
python3 phone-spike.py                # with the phone; type "help"
```

This repository does not include an identity. Running the spike creates
`phone-state/`, including a private key. That folder is gitignored: leave it
on your machine. To start over, delete `phone-state/` and unpair **FlickOS
spike** in the app. Do not reuse the key.

Cleanup after the session:

```sh
sudo ufw delete allow proto tcp from 192.168.88.0/24 to any port 1716
sudo ufw delete allow proto tcp from 192.168.88.0/24 to any port 1739:1764
sudo ufw status                       # check they're gone
libfm-actions/try.sh remove           # if you tried a round again
sudo apt remove libfm-modules         # only if you don't want it (Q8)
```

And on the phone: open **FlickOS spike** in KDE Connect and unpair it.

## Commands worth keeping

| Command | For |
|---|---|
| `ss -lntup` | who listens on which port |
| `openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -noenc -subj …` | a self-signed certificate in one line |
| `openssl x509 -noout -subject -dates -text` | read a certificate |
| `strings LIB \| grep NAME` | does a library know a word (a key, a setting)? |
| `nm -D --undefined-only LIB` | which functions a library calls from others |
| `apt-get download PKG; dpkg -c PKG.deb` | what's in a package, without installing it |
| `apt-cache show PKG \| grep Recommends` | what the image may be missing because of `--apt-recommends false` |
| `/proc/PID/smaps_rollup` (Pss) | fair memory of a process |
| `/proc/PID/task/*/status` (voluntary_ctxt_switches) | wakeups |
| `tail -F LOG \| grep --line-buffered -v NOISE` | watch a log without the noise |
