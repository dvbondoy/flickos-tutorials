# Shipping a package: VM tests, upgrade tests and publishing

> Set `TUTORIALS` to the root of the [tutorials repository](https://github.com/dvbondoy/flickos-tutorials) and `FLICKOS` to your clone of [FlickOS](https://github.com/dvbondoy/FlickOS). Paths below use those two variables. Scripts read the FlickOS checkout from `FLICKOS_REPO` or `FLICKOS`.

This continues where `$TUTORIALS/flickos-deb-tutorial` stopped. There you
built **flickos-hello** and installed it on your own computer. Here it goes
the rest of the way:
- into a clean FlickOS in a virtual machine;
- through FlickOS's automatic boot test;
- into a signed apt repository, the same kind that FlickOS's updates come from;
- and from version 1.0 to 1.1 to 1.2 the way an installed FlickOS would
  receive them, with `apt`.

Then it maps every step onto publishing a real FlickOS package and releasing
an ISO.

Every command here was run while writing this guide, and the outputs shown are
the real ones (shortened where marked `…`).

- **Time:** 2 to 3 hours. The VMs do most of the waiting.
- **What it touches:** nothing is published, nothing is installed on your
  computer, and the FlickOS repo isn't changed. The test repository is served
  only to your own computer, and its key is a throwaway one.

## Where this fits

The whole path of a FlickOS feature, and where each part is taught:

| # | Stage | Tutorial |
|---|---|---|
| 1–2 | Idea, questions, spike | `flickos-snip-spike`, `flickos-spike-kit` |
| 3–4 | Design doc, HIG review | `flickos-repo-tutorial` |
| 5 | Code + unit tests | `flickos-code-tutorial` |
| 6 | The .deb | `flickos-deb-tutorial` |
| 7 | Tests: own desktop, headless labwc | `flickos-headless-labwc` |
| 8–10 | Wire it into the repo, document it, commit it | `flickos-repo-tutorial` |
| **7** | **Tests: QEMU and the boot test** | **here, steps 1–3** |
| **12** | **Upgrade test** | **here, steps 4–12** |
| **11** | **Publishing to installed systems** | **here, step 13** |
| **13** | **Releasing an ISO** | **here, step 14** |

## What's in this folder

| Path | What it is |
|---|---|
| `README.md` | This guide |
| `versions/flickos-hello-1.0/`, `-1.1/`, `-1.2/` | The example package in three versions, as full package folders. `diff -ru versions/flickos-hello-1.1 versions/flickos-hello-1.2` shows exactly what a version changed |
| `make-debs.sh` | Builds the three versions into `debs/` |
| `local-repo.sh` | A throwaway **signed apt repository** on your computer (`init`, `add`, `list`, `remove`, `serve`, `clean`). The same tools as FlickOS's real one |
| `vm-run.py` | Boots the FlickOS ISO **without a window**, logs in and runs your commands in it. It borrows the repo's `tools/boot-test.py` code |
| `upgrade-test.txt` | A complete upgrade test (1.0 → 1.1 → 1.2) for `vm-run.py` |

## Contents

0. [Before you start](#0-before-you-start)
1. [The words](#1-the-words)
2. [FlickOS in a window: tools/test-iso.sh](#2-flickos-in-a-window-toolstest-isosh)
3. [The boot test: tools/boot-test.py](#3-the-boot-test-toolsboot-testpy)
4. [How apt trusts a repository](#4-how-apt-trusts-a-repository)
5. [Your own signed repository, by hand](#5-your-own-signed-repository-by-hand)
6. [Check it from this computer](#6-check-it-from-this-computer)
7. [Serve it to a VM](#7-serve-it-to-a-vm)
8. [An upgrade test by hand, in a window](#8-an-upgrade-test-by-hand-in-a-window)
9. [The same test without a window](#9-the-same-test-without-a-window)
10. [What the test found in FlickOS itself](#10-what-the-test-found-in-flickos-itself)
11. [Installed systems and snapshots](#11-installed-systems-and-snapshots)
12. [Testing a real FlickOS change before publishing](#12-testing-a-real-flickos-change-before-publishing)
13. [Publishing for real](#13-publishing-for-real)
14. [Releasing an ISO](#14-releasing-an-iso)
15. [Traps](#15-traps)
16. [Cheat sheet](#16-cheat-sheet)
17. [Clean up](#17-clean-up)

---

## 0. Before you start

```sh
ls $FLICKOS/FlickOS-64bit-v*.iso    # an ISO to boot
id | grep -o kvm                                         # you may use KVM
ls -l /dev/kvm                                           # crw-rw----+ root kvm
cd $TUTORIALS/flickos-ship-tutorial
./make-debs.sh
```

```
flickos-hello_1.0_all.deb
flickos-hello_1.1_all.deb
flickos-hello_1.2_all.deb
```

- **The ISO:** this guide used `FlickOS-64bit-v2.1.iso` from 26 September.
  Any FlickOS ISO works. A newer one only changes some of the outputs.
- **KVM:** without it, VMs still run, but about ten times slower.
  `sudo adduser $USER kvm`, then log out and in.

The three versions of the package:

| Version | What changed | What it teaches |
|---|---|---|
| 1.0 | the package from the deb tutorial | a first install |
| 1.1 | `hello.conf` says `Greeting=Mabuhay` | a changed **conffile** that the administrator also edited |
| 1.2 | a new `--big` option, which needs `figlet` | a **new dependency** |

## 1. The words

| Word | What it is |
|---|---|
| **QEMU** | the program that pretends to be a whole computer: CPU, memory, disk, screen, network card. `qemu-system-x86_64` |
| **KVM** | the Linux kernel's support for running a VM's code directly on your CPU (`/dev/kvm`). QEMU uses it with `-enable-kvm`, and without it QEMU has to imitate every instruction |
| **OVMF / SeaBIOS** | the pretend computer's firmware: OVMF is UEFI, SeaBIOS is the old BIOS. FlickOS boots from both, with different boot loaders (GRUB for UEFI, syslinux for BIOS), so a release is tested on both |
| **qcow2** | QEMU's disk file format. A "20 GB" disk only takes the space actually written, and it can hold **snapshots** (step 11) |
| **user networking** | QEMU's built-in network (`-nic user`). The VM gets internet through QEMU, and **reaches your computer as `10.0.2.2`** (step 7). Nothing from outside can reach the VM |
| **serial console** | a text-only terminal on the VM's pretend serial port. The boot test logs in there instead of looking at the screen |
| **QMP** | QEMU's control socket. The boot test uses it to take screenshots |
| **live session** | FlickOS booted from the ISO without installing. Everything runs from RAM, and **nothing survives a reboot**: every boot is a clean system |

## 2. FlickOS in a window: tools/test-iso.sh

```sh
cd $FLICKOS
tools/test-iso.sh              # the live session, UEFI
tools/test-iso.sh --bios       # the same with the old BIOS (syslinux menu)
```

A QEMU window opens with FlickOS's boot menu, then the live desktop.

- Clicking into the window captures the mouse. **Ctrl+Alt+G** lets it go.
- Closing the window pulls the plug. In a live session nothing is lost.

The script builds a `qemu-system-x86_64` command (the `args` part of
`tools/test-iso.sh`):
- `-m 4G -smp 2`: 4 GB of RAM, 2 CPUs.
- `-device virtio-vga`: a screen.
- `-nic user,model=virtio-net-pci`: the network.
- `-usb -device usb-tablet`: a mouse that follows your pointer exactly.
- `-enable-kvm -cpu host`: when `/dev/kvm` is usable.
- For UEFI, two `-drive if=pflash` lines: the firmware (read-only), and a
  copy of its variables. The live session gets a throwaway copy of those
  variables, so it never disturbs a test install's boot entries.
- `-cdrom FlickOS-…iso`: the ISO as a CD.

docs/02 ("What to check in the live session") has the full checklist for a
release. For a single package, check what it touches.

The other modes (`--install`, `--disk`, `--reset`) are for an installed
system, in step 11.

## 3. The boot test: tools/boot-test.py

Clicking through a VM by hand is slow and never quite the same twice. The boot
test does the checks that can be automated, **without a window**, and CI runs
it after every ISO build.

```sh
cd $FLICKOS
tools/boot-test.py                 # results in boot-test/ (git-ignored)
tools/boot-test.py -v              # also show everything the VM prints
```

**How it works**, step by step (the code is `main()` at the bottom of the
script):
1. **It takes the kernel, the initrd and the kernel command line out of the
   ISO** with `xorriso`, and boots them directly with QEMU's `-kernel`. The
   boot menu is skipped, because it waits for a key.
2. **It adds `console=ttyS0,115200`**, so Linux puts a login prompt on the
   serial port. QEMU connects that port to the script's stdin/stdout
   (`-serial chardev:ser0`).
3. **It waits for `login:`**, types `user`, then `live` (the live session's
   password). The graphical desktop starts on its own on the pretend screen,
   as on a real computer.
4. **It runs every entry of `CHECKS`** (line ~168). Each one is a shell
   command that must exit 0, and may retry for some seconds while the desktop
   starts. It wraps each command in markers (`@@BEGIN@@ … @@RC=0@@`) so it can
   find the output and the exit code in the stream of text.
5. It takes screenshots through QMP, reports memory use, and exits:
   - 0: everything passed;
   - 1: a check failed;
   - 2: a setup problem;
   - 3: it never got to log in.

**A real run**, on the 2.1 ISO from 26 September, with today's repo:

```
ISO: $FLICKOS/FlickOS-64bit-v2.1.iso
Kernel command line: boot=live components username=user hostname=flickos console=tty0 console=ttyS0,115200
Login prompt after 37s
PASS logged in on serial console
PASS systemd: running
PASS hostname is flickos
PASS flickos-desktop installed
…
FAIL no first-login window in the live session (exit 2): usage: flickos-welcome [-h] COMMAND ...
flickos-welcome: error: argument COMMAND: invalid choice: 'startup' (choose from show, first-run, list)
FAIL phone connection off in the live session, nothing listening (exit 2): -bash: flickos-phone: command not found
…
MEM  679 MB in use of 3921 MB (details: …/memory.txt)

131/144 checks passed in 437s. Serial log: …/serial.log
```

**Read the failures before believing them.** `flickos-phone: command not
found` means the ISO has no flickos-phone at all. The ISO was built two days
before the checks were written: its flickos-layouts is 1.25 while the repo's
is 1.31, and flickos-phone didn't exist yet. The boot test checks what the
**current code** expects, so it only means something for an ISO built from
the same commit. That is how CI runs it (build, then test, in one job). Before
trusting a local run, compare the dates of the ISO and of your last commit.

The files it leaves in `boot-test/`:
- `serial.log`: everything the VM printed. The first place to look when a
  check fails.
- `screen.png`: the desktop at the end.
- Named screenshots: for example `layout-cupertino.png`.
- `memory.txt`: memory in use, and the biggest processes.

**Adding a check** for your feature: add one line to `CHECKS`:

```python
    ("flickos-hello says hello", "flickos-hello | grep -q '^Hello, user!$'", 0),
#    description                 shell command, exit 0 = pass               seconds to retry
```

The rules:
- Checks run as the live user `user`, and `sudo -n` works without a password.
- Use `0` seconds for things that are true as soon as you log in (installed
  files). Use a retry time for things the desktop starts in the background:
  `("waybar running", "pgrep -u user -x waybar", 60)`.
- A fourth field names a screenshot to take after the check passes.
- CLAUDE.md asks for a check with every user-visible feature. This line is
  what stops a later change from quietly breaking your feature.

A check for flickos-hello only makes sense once it is in the ISO: in
flickos-desktop's Depends, and so in the image.

## 4. How apt trusts a repository

A repository is only a folder of static files, served by any web server.
FlickOS's is on GitHub Pages. Everything that makes it trustworthy is in those
files. Look at the real one:

```sh
curl -fsSL https://dvbondoy.github.io/flickos-apt/dists/trixie/InRelease | head -16
```

```
-----BEGIN PGP SIGNED MESSAGE-----
Hash: SHA512

Origin: FlickOS
Label: FlickOS
Codename: trixie
Date: Sun, 27 Sep 2026 10:29:20 UTC
Architectures: amd64
Components: main
Description: FlickOS package repository
MD5Sum:
 bdadf5dd54f20363e6b49185c89eb6aa 19596 main/binary-amd64/Packages
 53660223bc7103e8e75b885b9d328d8d 7598 main/binary-amd64/Packages.gz
 …
SHA256:
 …
-----BEGIN PGP SIGNATURE-----
```

**It's a chain, and each link checks the next:**

```
the key on the computer           /usr/share/keyrings/flickos-archive-keyring.asc
        │ checks the signature of                   (from flickos-archive-keyring)
        ▼
dists/trixie/InRelease            the list of index files, each with its SHA256
        │ checks the hash of
        ▼
dists/trixie/main/binary-amd64/Packages(.gz)
        │                         one entry per package: Version, Depends,
        │ checks the hash of      Filename: pool/…, SHA256: …
        ▼
pool/main/f/flickos-hello/flickos-hello_1.1_all.deb
```

Only `InRelease` is signed. Everything else is trusted because its hash is in
something already trusted. Change one byte of a `.deb`, and its hash no longer
matches `Packages`; change `Packages`, and its hash no longer matches
`InRelease`; change `InRelease`, and the signature breaks. apt then refuses
the repository, which is why the web server itself doesn't need to be trusted.

**Which key?** The source file says so. FlickOS ships one in
flickos-archive-keyring:

```sh
cat /etc/apt/sources.list.d/flickos.sources
```

```
Types: deb
URIs: https://dvbondoy.github.io/flickos-apt
Suites: trixie
Components: main
Signed-By: /usr/share/keyrings/flickos-archive-keyring.asc
```

`Signed-By:` ties this repository to this key and no other. Without it, any
key apt trusts would do.

**`Origin:` and `Label:` matter too.** Automatic updates (unattended-upgrades)
choose repositories by these fields. flickos-control's *Updates* page writes
`origin=FlickOS,codename=trixie,label=FlickOS` into the list of allowed
origins, but only in its "all" scope. They come from `repo/conf/distributions`.
Rename them there, and every installed system silently stops taking FlickOS
packages automatically.

## 5. Your own signed repository, by hand

Now build the same thing yourself. These steps do what FlickOS's
`repo/new-key.sh` (once) and `repo/publish.sh` (every time) do, with a
throwaway key.

```sh
cd $TUTORIALS/flickos-ship-tutorial
mkdir -p byhand/conf && cd byhand
```

**The key.** gpg normally keeps keys in `~/.gnupg`, where FlickOS's real
signing key lives. `GNUPGHOME` points gpg at another folder, so the test key
can never be confused with the real one:

```sh
export GNUPGHOME=$PWD/gnupg
mkdir -m 700 $GNUPGHOME
gpg --batch --passphrase '' --quick-gen-key "FlickOS test repo (throwaway) <test@localhost>" ed25519 sign 1y
FPR=$(gpg --list-secret-keys --with-colons | awk -F: '/^fpr/ {print $10; exit}')
echo $FPR
gpg --armor --export $FPR > test-key.asc      # the public half, for apt
```

- `--passphrase ''` means no passphrase: fine for a test key, never for the
  real one. The real key asks for its passphrase every time reprepro signs.
- `ed25519 sign 1y`: a modern key type, for signing only, and it expires in a
  year, so a forgotten test key dies by itself.
- `mkdir -m 700`: gpg refuses a folder that others can read.

**The repository's description.** reprepro reads `conf/distributions`. Put
your key's fingerprint where FlickOS's has its own (`repo/conf/distributions`):

```sh
cat > conf/distributions <<EOF
Origin: FlickOS-test
Label: FlickOS-test
Codename: trixie
Architectures: amd64
Components: main
Description: throwaway test repository
SignWith: $FPR
EOF
printf 'outdir +b/public\ndbdir +b/db\n' > conf/options
```

`conf/options` is copied from the repo: `+b/` means "relative to the base
folder". The finished repository goes to `public/`, and reprepro's own
database to `db/`.

**Add a package:**

```sh
reprepro -b . includedeb trixie ../debs/flickos-hello_1.0_all.deb
reprepro -b . list trixie
find public | sort
```

```
Exporting indices...
trixie|main|amd64: flickos-hello 1.0
public
public/dists
public/dists/trixie
public/dists/trixie/InRelease
public/dists/trixie/main
public/dists/trixie/main/binary-amd64
public/dists/trixie/main/binary-amd64/Packages
public/dists/trixie/main/binary-amd64/Packages.gz
public/dists/trixie/main/binary-amd64/Release
public/dists/trixie/Release
public/dists/trixie/Release.gpg
public/pool
public/pool/main
public/pool/main/f
public/pool/main/f/flickos-hello
public/pool/main/f/flickos-hello/flickos-hello_1.0_all.deb
```

- `pool/main/f/flickos-hello/`: the `.deb` files, sorted by the package's
  first letter.
- `dists/trixie/`: the indexes.
  - `InRelease` is the signed list.
  - `Release` + `Release.gpg` are the same thing in the older two-file form.

**Follow the chain yourself:**

```sh
cat public/dists/trixie/main/binary-amd64/Packages     # Filename: and SHA256: of the .deb
sha256sum public/pool/main/f/flickos-hello/*.deb        # the same number
gpg --dearmor < test-key.asc > test-key.gpg
gpgv --keyring ./test-key.gpg public/dists/trixie/InRelease
```

```
gpgv:                using EDDSA key 9685C2F6D3284831A3C9F34C71E6D3895B5DBD87
gpgv: Good signature from "FlickOS test repo (throwaway) <test@localhost>"
```

apt does the same with `sqv` (in trixie), from the key named in `Signed-By:`.

**Try to publish different content under the same version.** Change a file,
rebuild 1.0 and add it:

```sh
cp -r ../versions/flickos-hello-1.0 /tmp/same && sed -i 's/^Greeting=Hello/Greeting=Hi/' /tmp/same/etc/xdg/flickos/hello.conf
(cd /tmp/same && DEB_BUILD_OPTIONS=nocheck dpkg-buildpackage -us -uc -b >/dev/null 2>&1)
reprepro -b . includedeb trixie /tmp/flickos-hello_1.0_all.deb
```

```
ERROR: '/tmp/flickos-hello_1.0_all.deb' cannot be included as 'pool/main/f/flickos-hello/flickos-hello_1.0_all.deb'.
Already existing files can only be included again, if they are the same, but:
md5 expected: 6f609acd9a5aa042c3a1334c32db0253, got: d186f30775c9f532812f960699b17e72
…
There have been errors!
```

This is reprepro protecting everyone who already downloaded 1.0: **a published
version never changes.** The identical file again is fine ("Skipping
inclusion … as it has already '1.0'"). Hence `dch -i` before every change.

```sh
rm -rf /tmp/same /tmp/flickos-hello_1.0_all.* /tmp/flickos-hello_1.0_amd64.*
```

**Add 1.1, and 1.0 disappears:**

```sh
reprepro -b . includedeb trixie ../debs/flickos-hello_1.1_all.deb
ls public/pool/main/f/flickos-hello/
```

```
Exporting indices...
Deleting files no longer referenced...
flickos-hello_1.1_all.deb
```

A reprepro distribution holds **one version per package**. That's all apt
needs, because it only ever wants the newest. But it means you can't publish
1.1 and still install 1.0 from the repo afterwards. The upgrade tests below
put 1.0 in, install it, and only then add 1.1.

**From now on, use the helper.** `local-repo.sh` is these same commands in one
script, kept in `local-repo/`:

```sh
cd .. && rm -rf byhand && unset GNUPGHOME
./local-repo.sh init
./local-repo.sh add debs/flickos-hello_1.0_all.deb
```

## 6. Check it from this computer

Before starting a VM, you can check that apt accepts the repository, without
root and without touching your system's apt. The trick is to give apt private
folders for everything:

```sh
./local-repo.sh serve          # in a second terminal; leave it running
```

```sh
A=/tmp/aptcheck; mkdir -p $A/lists/partial $A/cache/archives/partial $A/etc/sources.list.d $A/etc/preferences.d $A/etc/apt.conf.d; touch $A/status
cat > $A/etc/sources.list.d/test.sources <<EOF
Types: deb
URIs: http://127.0.0.1:8000
Suites: trixie
Components: main
Signed-By: $PWD/local-repo/public/test-key.asc
EOF
OPTS="-o Dir::Etc=$A/etc -o Dir::Etc::sourcelist=- -o Dir::State::Lists=$A/lists -o Dir::Cache=$A/cache -o Dir::State::status=$A/status"
apt-get $OPTS -o Debug::NoLocking=1 -o APT::Sandbox::User=$(id -un) update
apt-cache $OPTS policy flickos-hello
```

```
Get:1 http://127.0.0.1:8000 trixie InRelease [1,181 B]
Get:2 http://127.0.0.1:8000 trixie/main amd64 Packages [467 B]
Fetched 1,648 B in 0s (27.7 kB/s)
Reading package lists...
flickos-hello:
  Installed: (none)
  Candidate: 1.0
  Version table:
     1.0 500
        500 http://127.0.0.1:8000 trixie/main amd64 Packages
```

| Option | Why |
|---|---|
| `Dir::Etc=…`, `Dir::Etc::sourcelist=-` | read sources only from the private `etc/`, not `/etc/apt` |
| `Dir::State::Lists`, `Dir::Cache` | download the indexes into private folders |
| `Dir::State::status=…` | a private, empty "installed packages" list |
| `Debug::NoLocking=1` | don't take apt's system-wide locks (which need root) |
| `APT::Sandbox::User=$(id -un)` | download as you. The default user `_apt` exists only for root's apt |

The same trick is what `tools/package-cost.py` uses to simulate installs
against the image's package list.

**See what a wrong key looks like.** Point `Signed-By:` at FlickOS's real key
instead, and update again:

```
Err:1 http://127.0.0.1:8000 trixie InRelease
  Sub-process /usr/bin/sqv returned an error code (1), error message is: Missing key 9685C2F6D3284831A3C9F34C71E6D3895B5DBD87, which is needed to verify signature.
W: OpenPGP signature verification failed: http://127.0.0.1:8000 trixie InRelease: …
E: The repository 'http://127.0.0.1:8000 trixie InRelease' is not signed.
```

"Missing key …" means the repository was signed with a key other than the one
named in `Signed-By:`. You'll see exactly this if FlickOS's signing key is ever
replaced without a new flickos-archive-keyring reaching users first
(docs/05, "Key rotation").

```sh
rm -rf /tmp/aptcheck
```

## 7. Serve it to a VM

`./local-repo.sh serve` runs Python's built-in web server:

```sh
python3 -m http.server --bind 127.0.0.1 --directory local-repo/public 8000
```

- `--bind 127.0.0.1`: listen only on this computer's loopback address. Nobody
  on your Wi-Fi can reach it, and the firewall isn't involved.
- **A VM still reaches it**, because of how QEMU's user networking works. When
  the VM connects to `10.0.2.2`, QEMU, running on your computer, opens the
  connection to **your 127.0.0.1**. To the web server it looks like a local
  program. So in the VM the repo is `http://10.0.2.2:8000`.
- The server prints one line per request. When the VM runs `apt update`,
  you'll see `GET /dists/trixie/InRelease`, which is a quick way to confirm
  the VM reached it.

This is also how docs/09's faster loop works:
`python3 -m http.server` in `config/packages.chroot/`, then download the `.deb`
from `http://10.0.2.2:8000/` in the VM.

## 8. An upgrade test by hand, in a window

The repository holds 1.0 and `serve` is running (steps 5–6). Start a live
session:

```sh
cd $FLICKOS && tools/test-iso.sh
```

In the VM, open a terminal (**Super+Enter**) and do what an installed
FlickOS would do with a new repository.

**Trust the test repo.** Fetch its key, then write a source that names that
key:

```sh
curl -fsS http://10.0.2.2:8000/test-key.asc | sudo tee /etc/apt/keyrings/flickos-test.asc >/dev/null
printf 'Types: deb\nURIs: http://10.0.2.2:8000\nSuites: trixie\nComponents: main\nSigned-By: /etc/apt/keyrings/flickos-test.asc\n' | sudo tee /etc/apt/sources.list.d/flickos-test.sources
```

- `/etc/apt/keyrings/` is Debian's place for keys an administrator adds by
  hand.
- `/usr/share/keyrings/` is for keys that packages install (like
  flickos-archive-keyring).

**Install 1.0:**

```sh
sudo apt update
apt policy flickos-hello
sudo apt install flickos-hello
flickos-hello                                          # Hello, user!
```

The live ISO has **no package lists**, so this first `apt update` downloads
Debian's, FlickOS's and yours: about 28 MB.

**Be the administrator:** change the conffile.

```sh
sudo sed -i 's/^Greeting=.*/Greeting=Hi/' /etc/xdg/flickos/hello.conf
flickos-hello                                          # Hi, user!
```

**Publish 1.1**, on your computer, in a third terminal:

```sh
cd $TUTORIALS/flickos-ship-tutorial && ./local-repo.sh add debs/flickos-hello_1.1_all.deb
```

**Upgrade**, in the VM:

```sh
sudo apt update
apt list --upgradable                   # flickos-hello … 1.1 … [upgradable from: 1.0], and others
sudo apt install --only-upgrade flickos-hello
```

Why `install --only-upgrade flickos-hello` and not `apt upgrade`? The live
ISO is older than what's published, so `apt upgrade` would also bring 8
other packages up to date. That's what a user
would do, but it's noise here. `--only-upgrade` means "upgrade this package
if it's installed, never newly install it".

dpkg asks the conffile question from the deb tutorial. Press `D` to see the
difference, then `N` to keep yours:

```sh
flickos-hello                                          # Hi, user!  (kept)
ls /etc/xdg/flickos/ | grep hello                      # hello.conf  hello.conf.dpkg-dist
```

**Publish 1.2**, which needs figlet:

```sh
./local-repo.sh add debs/flickos-hello_1.2_all.deb      # on your computer
```

In the VM:

```sh
sudo apt update
apt-get -s upgrade | grep -A1 'kept back'
```

```
The following packages have been kept back:
  flickos-desktop flickos-hello
```

`-s` only simulates. **`apt-get upgrade` never installs a package that isn't
installed yet**, and 1.2 needs figlet, so it holds flickos-hello back
(flickos-desktop too: that's step 10). The four upgrade commands differ in
exactly this:

| Command | Upgrades | Installs new packages? | Removes packages? |
|---|---|---|---|
| `apt-get upgrade` | everything upgradable | **no**: holds those back | no |
| `apt upgrade` | everything upgradable | **yes**, new dependencies | no |
| `apt full-upgrade` / `apt-get dist-upgrade` | everything | yes | **yes**, if a Conflicts/Breaks needs it |
| `apt install PKG` / `--only-upgrade PKG` | that package | yes, its dependencies | only if needed, and it asks |

```sh
sudo apt install --only-upgrade flickos-hello           # The following NEW packages will be installed: figlet
flickos-hello --big
```

Close the window when you're done. Nothing of this session is kept.

## 9. The same test without a window

Clicking and typing through that takes 15 minutes, and it's easy to skip a
step. `vm-run.py` does it the boot test's way, headless, and `upgrade-test.txt`
is the whole of step 8 as a script.

```sh
./local-repo.sh serve                          # second terminal, if it isn't running
./vm-run.py --script upgrade-test.txt
```

The real output, shortened:

```
booting FlickOS-64bit-v2.1.iso …
logged in after 31 s

host$ ./local-repo.sh remove flickos-hello >/dev/null 2>&1; ./local-repo.sh add debs/flickos-hello_1.0_all.deb
trixie|main|amd64: flickos-hello 1.0

vm$ curl -fsS http://10.0.2.2:8000/test-key.asc | sudo tee /etc/apt/keyrings/flickos-test.asc >/dev/null
…
vm$ sudo apt-get update -q
Get:1 http://10.0.2.2:8000 trixie InRelease [1,181 B]
…
Fetched 28.0 MB in 8s (3,590 kB/s)

vm$ apt-cache policy flickos-hello
flickos-hello:
  Installed: (none)
  Candidate: 1.0
…
vm$ flickos-hello
Hello, user!
…
vm$ sudo apt-get install -q --only-upgrade -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold flickos-hello
…
Configuration file '/etc/xdg/flickos/hello.conf'
 ==> Modified (by you or by a script) since installation.
 ==> Package distributor has shipped an updated version.
 ==> Keeping old config file as default.

vm$ flickos-hello
Hi, user!

vm$ ls /etc/xdg/flickos/ | grep hello
hello.conf
hello.conf.dpkg-dist
…
vm$ apt-get -s upgrade | grep -A1 'kept back'
The following packages have been kept back:
  flickos-desktop flickos-hello

vm$ sudo apt-get install -q --only-upgrade -y flickos-hello
The following NEW packages will be installed:
  figlet
The following packages will be upgraded:
  flickos-hello
…
vm$ flickos-hello --big
_   _ _                         _
| | | (_)    _   _ ___  ___ _ __| |
| |_| | |   | | | / __|/ _ \ '__| |
|  _  | |_  | |_| \__ \  __/ |  |_|
|_| |_|_( )  \__,_|___/\___|_|  (_)
        |/

all commands succeeded
```

The whole run takes about three minutes. (figlet's first line lost its
leading space: the boot test's `Console` strips each command's output.)

**How `vm-run.py` works.** It is short (about 150 lines), so read it. It loads
`tools/boot-test.py` from the repo as a module, and reuses three parts:
- `extract_boot_files()` gets the kernel, initrd and command line from the ISO.
- `Console` reads and writes the serial port and finds each command's exit
  code.
- The login sequence.

It then runs your lines instead of `CHECKS`. The whole serial console goes to
`vm-run.log`.

**Writing your own test script:**
- One command per line. Empty lines and lines starting with `#` are skipped.
- Each line runs in its **own subshell** with no terminal input. Chain steps
  that belong together with `&&`, since a `cd` doesn't carry over to the next
  line.
- Give apt `-y`: nobody can press Y.
- A line starting with `host:` runs **on your computer**, in this folder. That
  is how the script publishes 1.1 in the middle of the test.
- It stops at the first failing line (`--keep-going` doesn't). A line that
  should fail is written `! command`.
- `--shot end.png` saves the VM's screen at the end. `-v` shows the serial
  console live, which is useful when a command hangs.
- Quick one-off questions work too:
  `./vm-run.py 'grep PRETTY /etc/os-release' 'apt list --installed 2>/dev/null | grep flickos'`.

**Noise you can ignore** in its output:
- `debconf: unable to initialize frontend: Dialog …`: package scripts look for
  a terminal to ask questions on, and a serial script has none.
- `Reading package lists... 0%…`: apt's progress, which `-q` hides.

**The conffile options.** With nobody to answer dpkg's conffile question,
dpkg fails:

```
*** hello.conf (Y/I/N/O/D/Z) [default=N] ? dpkg: error processing package flickos-hello (--install):
 end of file on stdin at conffile prompt
```

`--force-confdef --force-confold` answer it in advance:
- if the administrator didn't change the file, take the new one (`confdef`);
- otherwise keep theirs (`confold`), and put the new one next to it as
  `.dpkg-dist`.

unattended-upgrades (automatic updates) is more careful still. It checks
beforehand whether an upgrade would ask the question, and if so it **skips
that package**, logging "Package … has conffile prompt and needs to be
upgraded manually". So a user who edited a FlickOS conffile stops getting
that package automatically, until they upgrade it by hand.

## 10. What the test found in FlickOS itself

`apt-get -s upgrade` said `kept back: flickos-desktop`, and that isn't the
example's fault. Ask why:

```sh
./vm-run.py 'sudo apt-get update -qq' 'apt-cache policy flickos-desktop | head -3' \
            'apt-get -s -q install flickos-desktop | grep -E "^Inst|NEW"'
```

```
vm$ apt-cache policy flickos-desktop | head -3
flickos-desktop:
  Installed: 1.20
  Candidate: 1.21

vm$ apt-get -s -q install flickos-desktop | grep -E "^Inst|NEW"
The following NEW packages will be installed:
Inst libfm-modules (1.4.0-2 Debian:13.7/stable [amd64])
Inst flickos-phone (1.3 FlickOS:dvbondoy.github.io [all])
Inst flickos-desktop [1.20] (1.21 FlickOS:dvbondoy.github.io [all])
```

flickos-desktop 1.21 added `Depends: flickos-phone`, and flickos-phone depends
on libfm-modules. A FlickOS 2.1 system has neither, so:
- **`apt upgrade`** gets flickos-phone and the new flickos-desktop (what the
  Software app does wasn't tested here);
- **`apt-get upgrade`** holds flickos-desktop back, for as long as the person
  keeps using `apt-get upgrade`;
- **automatic updates** by default use flickos-control's "debian" scope, which
  doesn't include the FlickOS repository at all:

```
vm$ sudo unattended-upgrade --dry-run -v 2>&1 | grep "Allowed origins"
Allowed origins are: origin=Debian,codename=trixie,label=Debian, origin=Debian,codename=trixie,label=Debian-Security, origin=Debian,codename=trixie-security,label=Debian-Security
```

This is exactly what an upgrade test is for. Nothing in the package, the ISO
or the boot test was wrong: each is fine on its own. The only problem is on
the path **from last month's system to today's packages**, and only an
upgrade test walks that path.

The lesson for new work: **adding a Depends to an existing package is an
upgrade event.** Before publishing one, run an upgrade test from the last
ISO, and decide how the new package reaches existing systems.

## 11. Installed systems and snapshots

The live session is ideal for package tests: every boot is clean. But some
things only exist on an installed system:
- the login screen (flickos-greeter);
- a first login with a new account (flickos-welcome);
- settings that must survive a reboot;
- anything Calamares changes (it removes flickos-installer and the live
  packages);
- and the real "months later" upgrade.

**Install once:**

```sh
cd $FLICKOS
tools/test-iso.sh --install         # a 20 GB test disk in .test-vm/, then run Install FlickOS
tools/test-iso.sh --disk            # boot the installed disk, no ISO
```

`.test-vm/` holds `disk.qcow2` (the installed system), `OVMF_VARS.fd` (its
UEFI boot entry) and `firmware` (which firmware it was installed with).
`--reset` throws them away.

**Snapshots let you do the same upgrade test again and again.** qcow2 disks
can keep named states. With the VM **switched off**:

```sh
qemu-img snapshot -c fresh-2.1 .test-vm/disk.qcow2        # -c: create
qemu-img snapshot -l .test-vm/disk.qcow2                  # -l: list
```

```
Snapshot list:
ID      TAG               VM_SIZE                DATE        VM_CLOCK     ICOUNT
1       fresh-2.1             0 B 2026-09-28 00:35:35  0000:00:00.000          0
```

Then:
1. Boot it (`--disk`).
2. Add the test repo exactly as in step 8.
3. Upgrade, and look.
4. Switch it off, and go back:

```sh
qemu-img snapshot -a fresh-2.1 .test-vm/disk.qcow2        # -a: apply (back to that moment)
qemu-img snapshot -d fresh-2.1 .test-vm/disk.qcow2        # -d: delete it when you no longer need it
```

A good habit is one snapshot per released ISO (`fresh-2.1`, `fresh-2.2`, …).
The question "does today's repo upgrade a 2.1 install cleanly?" is then two
commands away.

**Never snapshot or apply while the VM is running:** the disk would be
corrupted. qemu-img refuses when it can (`Failed to get "write" lock`).

A snapshot covers the disk only, not `OVMF_VARS.fd`. That's fine, because an
upgrade doesn't change the boot entry.

## 12. Testing a real FlickOS change before publishing

Everything above, applied to a real change. Say you changed flickos-welcome:

```sh
cd $FLICKOS/packages/flickos-welcome
dch -i -D trixie "What changed."             # a NEW version, above the published one
cd ../.. && sh packages/build.sh             # all .debs into config/packages.chroot/

cd $TUTORIALS/flickos-ship-tutorial
./local-repo.sh add $FLICKOS/config/packages.chroot/flickos-welcome_*.deb
./local-repo.sh serve                         # second terminal
```

Then:
1. **Start from what users have.** In a VM (the live ISO, or the snapshot of
   an installed system), run `sudo apt update && sudo apt upgrade` with only
   FlickOS's real repository. That is the state of a user who kept their
   system updated.
2. **Add the test repo** (step 8's two lines). `apt policy flickos-welcome`
   should show your new version as the candidate, coming from `10.0.2.2`.
3. `sudo apt upgrade`, and check what the change was meant to do. Also read
   the upgrade's own output: new packages, anything kept back, conffile
   questions.
4. For a change you'll test again, write it as a script for `vm-run.py`.

**Only add the packages you changed.** The test repo takes precedence only
through higher versions. A package at the **same version** as the published
one is seen as "already installed", and apt ignores it, which is one more
reason to `dch -i` first.

For a quick look on your own desktop, `sudo apt install
./config/packages.chroot/flickos-welcome_*.deb` is still fine (the deb
tutorial, step 13). The VM is for what your desktop can't tell you:
- "does it install on a system that has only what the image has?";
- "does the upgrade from the published version work?".

## 13. Publishing for real

Only after the tests. FlickOS's two scripts do what you did in step 5, plus
the upload:

**`repo/publish.sh`** (29 lines, read it):
1. It stops if `SignWith:` in `repo/conf/distributions` isn't set.
2. It runs `packages/build.sh`: **every** package is rebuilt from the working
   tree.
3. It runs `reprepro -b repo includedeb trixie` for every `.deb`:
   - an unchanged package (same version, same file) is skipped;
   - a new version replaces the old one;
   - **same version with a different file stops with the error from step 5.**
     If you see it, a package was changed without `dch -i`.
4. gpg asks for the real key's passphrase to sign `InRelease`.
5. It copies the public key to `repo/public/` for people who add the repo by
   hand, and lists what the repo holds.

**`repo/upload.sh`** (45 lines):
1. It keeps a clone of the `gh-pages` branch of `dvbondoy/flickos-apt` in
   `repo/.gh-pages/`, and resets it to what GitHub has.
2. `rsync --delete` makes it an exact copy of `repo/public/`, and adds
   `.nojekyll` so GitHub Pages serves the files as they are.
3. It commits and pushes. GitHub Pages then publishes it at
   `https://dvbondoy.github.io/flickos-apt/`.

**Check that it's online:**

```sh
curl -fsSI https://dvbondoy.github.io/flickos-apt/dists/trixie/InRelease | grep -iE "^HTTP|last-modified|cache-control"
```

```
HTTP/2 200
last-modified: Sun, 27 Sep 2026 10:29:52 GMT
cache-control: max-age=600
```

`max-age=600` is why docs/05 says that GitHub's CDN may serve the old files
for up to **10 minutes**. A "Hash Sum mismatch" in a VM right after an upload
usually fixes itself. `tools/release.sh` waits for the new `InRelease` for
this reason.

**Once published, it's frozen:**
- that version can't change (step 5);
- someone may have installed it already.

This is when the pool check from your own notes applies: before reusing a
version with `dch -a`, look in `repo/public/pool/` to see whether it was
already published.

**The two things only your computer has:**
- the **secret signing key**, in `~/.gnupg`;
- **`repo/db/`**, reprepro's record of what's published.

Losing the key means installed systems can never trust a new upload
(docs/05: back it up offline). Losing `repo/db/` loses only older versions:
`publish.sh` rebuilds the current ones.

## 14. Releasing an ISO

A release is a new snapshot for **new** installs. Installed systems already
get everything through the repo. docs/06 has the full checklist. Here is what
each part is for:

| Step | Command | Why |
|---|---|---|
| Bump the FlickOS version | `tools/release.sh X.Y`, or by hand: `FLICKOS_VERSION` in flickos-branding's `flickos-release`, plus the installer's `branding.desc` | the ISO name, os-release, SourceForge folder and boot test all read it. `build-iso.sh` stops if the two copies differ |
| Publish the packages first | `release.sh` runs `repo/publish.sh` + `upload.sh` and waits for `InRelease` | the ISO build's last step runs `apt update` against the published repo, which must be online, and a new install should find at least the ISO's versions in the repo it updates from |
| Build clean | `tools/build-iso.sh --purge` | `--purge` also empties live-build's download cache, so nothing stale gets in |
| Automatic test | `tools/boot-test.py --strict` | `--strict` also fails on a failed systemd unit |
| By hand | `tools/test-iso.sh --bios` and `--uefi`, `--reset --install`, then `--disk` with `apt update && apt upgrade` | the boot menus (syslinux, GRUB) and the installer can't be tested automatically |
| Upgrade path | the snapshot of the **previous** release (step 11), upgraded from the repo | people with the old ISO are the users you already have |
| Tag and push | `git tag -a vX.Y -m "FlickOS X.Y"`, `git push origin vX.Y` | CI builds again on a clean machine, checks the tag against `FLICKOS_VERSION`, and uploads the ISO to SourceForge |

`release.sh` commits nothing, and running it again with the same version
resumes it. A broken release is never fixed in place: it becomes `X.Y.1`
(docs/06, "If a release is broken"), for the same reason a published package
version is frozen.

## 15. Traps

1. **The boot test fails on an old ISO.** The checks follow the code, not the
   ISO (step 3). Build first, or read the failures with the ISO's date in
   mind.
2. **`dch` with a message that starts with `-`.** `dch -i -D trixie "--big
   does X"` fails with `Unknown option: big does X`. When the command's output
   is hidden, the version silently isn't bumped. Write
   `"New option --big: …"`, or put `--` before the message.
3. **Same version, different content.** reprepro refuses it ("Already
   existing files can only be included again, if they are the same"), and
   apt would never offer it anyway.
4. **The repo holds only the newest version.** Put 1.0 in, install it, then
   add 1.1. The other order leaves nothing to upgrade from.
5. **"Missing key …" / "is not signed".** The `Signed-By:` key isn't the one
   that signed `InRelease` (step 6).
6. **A new Depends is held back.** `apt-get upgrade` never installs new
   packages. Test the upgrade path, not only the fresh install (step 10).
7. **dpkg stops at "end of file on stdin at conffile prompt".** It ran without
   a terminal. Scripts need `--force-confdef --force-confold`. Automatic
   updates don't fail here: they quietly skip that package (step 9).
8. **A test in the live session upgrades everything.** The ISO is older than
   the repo. Use `--only-upgrade PKG`, or accept the noise.
9. **`Hash Sum mismatch` right after an upload.** GitHub's CDN is still
   serving old files. Wait up to 10 minutes.
10. **A snapshot taken while the VM ran.** It corrupts the disk. Snapshot only
    a switched-off VM.
11. **Renaming `Origin:`/`Label:` in `repo/conf/distributions`.** It silently
    stops automatic updates of FlickOS packages (step 4).
12. **`pkill -f PATTERN` in a script.** It also matches the shell running the
    script, whose command line contains the pattern, so it kills itself. Stop
    a server by its PID (`ss -ltnp 'sport = :8000'` shows it), or with Ctrl+C
    in its own terminal.

## 16. Cheat sheet

```sh
# VMs (in the FlickOS repo)
tools/test-iso.sh [--bios]                  # live session in a window
tools/test-iso.sh --install | --disk | --reset
tools/boot-test.py [-v] [--strict] [--out DIR]
qemu-img snapshot -c NAME|-l|-a NAME|-d NAME .test-vm/disk.qcow2   # VM switched off!

# the throwaway repo (this folder)
./make-debs.sh
./local-repo.sh init | add FILE.deb… | list | remove NAME | serve | clean
./vm-run.py [--script FILE] [--shot PNG] [-v] ['command' …]

# in a VM: trust the test repo
curl -fsS http://10.0.2.2:8000/test-key.asc | sudo tee /etc/apt/keyrings/flickos-test.asc >/dev/null
printf 'Types: deb\nURIs: http://10.0.2.2:8000\nSuites: trixie\nComponents: main\nSigned-By: /etc/apt/keyrings/flickos-test.asc\n' | sudo tee /etc/apt/sources.list.d/flickos-test.sources

# apt: asking and upgrading
apt policy PKG                              # installed, candidate, from where
apt list --upgradable
apt-get -s upgrade                          # simulate; shows what's kept back
sudo apt install --only-upgrade PKG         # just this package (+ its new dependencies)
sudo apt upgrade                            # everything, with new dependencies
sudo apt-get install -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold PKG   # scripts

# repository internals
reprepro -b DIR includedeb trixie FILE.deb | list trixie | remove trixie PKG
gpgv --keyring KEY.gpg dists/trixie/InRelease
curl -fsSL https://dvbondoy.github.io/flickos-apt/dists/trixie/InRelease | head

# the real thing (FlickOS repo)
repo/publish.sh && repo/upload.sh
tools/release.sh X.Y
```

## 17. Clean up

```sh
cd $TUTORIALS/flickos-ship-tutorial
./local-repo.sh clean                       # the repo and its throwaway key
rm -rf debs vm-run.log
```

Stop `serve` with Ctrl+C in its terminal. Your QEMU test disk
(`$FLICKOS/.test-vm/`, git-ignored) stays until you run
`tools/test-iso.sh --reset`.
