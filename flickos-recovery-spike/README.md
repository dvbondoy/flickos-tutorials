# The restore points spike (phase 0), item 1: the btrfs install

> Set `TUTORIALS` to the root of the [tutorials repository](https://github.com/dvbondoy/flickos-tutorials) and `FLICKOS` to your clone of [FlickOS](https://github.com/dvbondoy/FlickOS). Scripts read the FlickOS checkout from `FLICKOS_REPO` or `FLICKOS`.

Phase 0 of `docs/design/flickos-recovery.md` has seven items. This folder does
them **one at a time**. Item 1 is the part only you can do: clicking through
the installer. Claude does items 2–6 and adds a guide only for the parts worth
learning (snapshots, and how a start works).

**Item 1 asks one thing:** if Calamares gets the configs from design ADR-001,
does it make the btrfs layout the rest of the design depends on, and does the
result start, hibernate and unlock? Everything is tried in virtual machines.
Your own computer and the repo don't change.

Plan on about an hour: four installs of 10–15 minutes each, plus a few minutes
looking at each one.

```
README.md          this guide
results.md         the answer sheet: predictions first, results after
calamares/         the three proposed Calamares configs (partition, mount, fstab)
serve.sh           gives the live VM setup-live.sh and calamares/ over 10.0.2.2:8000
setup-live.sh      runs inside the live VM: btrfs-progs + the configs, before installing
vm.sh              a QEMU window per named test disk (vm/NAME.qcow2)
check-disk.py      checks an installed disk without a window (layout + start)
check-layout.sh    what check-disk.py runs on the disk, as root, read-only
```

Created while you work: `vm/` (the disks, about 5–7 GB each), `results/`.

---

## 1. What you're about to see, in five minutes

**btrfs** is a filesystem, like ext4, with one extra idea: inside one
partition it can hold several **subvolumes**. A subvolume looks like a
folder, but it can be mounted on its own and, most importantly, **snapshotted
on its own**. A snapshot is an instant copy of a subvolume that takes no space
at first. It shares every file with the original, and only the files that
change afterwards take space (*copy-on-write*).

That's why the layout matters. Putting back a restore point means swapping the
system's subvolume `@` for an older snapshot of it. Everything that must *not*
go back in time has to live in a **different** subvolume:

| Subvolume | Mounted at | Why it's separate |
|---|---|---|
| `@` | `/` | the system: this is what a restore point holds |
| `@home` | `/home` | your files never go back |
| `@log` | `/var/log` | the logs of what went wrong survive a restore |
| `@cache` | `/var/cache` | apt's downloaded packages aren't kept in every restore point |
| `@snapshots` | `/.snapshots` | restore points aren't inside the system they restore |

The partition itself has a hidden top level (subvolume id 5). All five sit
side by side there, a *flat* layout. The system only sees them through
`/etc/fstab`, which mounts each one with `subvol=/@log` and so on.
`check-layout.sh` mounts that top level read-only to look.

**What the three configs change** (open them in `calamares/`, they're short):

- `partition.conf`: btrfs is the default, ext4 stays in the drop-down. A swap
  *partition* only (no swap file), because hibernation needs a known place on
  disk.
- `mount.conf`: the five subvolumes, and the mount options **moved here**.
  FlickOS keeps them in `fstab.conf` today, where Calamares 3.3 never reads
  them, so today's installs don't get `noatime`.
- `fstab.conf`: only the crypttab line is left.

**How they get into the installer without building an ISO:** the live session
keeps its files in memory, so `setup-live.sh` can install `btrfs-progs`
(Calamares needs `mkfs.btrfs`, and the image doesn't have it yet) and copy the
configs over `/etc/calamares/modules/` before you start the installer. It's
gone again when the live VM stops.

## 2. Write your predictions

Open `results.md` and fill in the **Your prediction** column for Q1–Q8 before
installing anything. A guess is fine. The point is to notice where the system
surprises you.

## 3. Start the server (keep it running)

In a terminal in this folder:

```sh
./serve.sh
```

It answers only on `127.0.0.1`. QEMU's user network shows your computer to
the VM as `10.0.2.2`, so the VM can reach `http://10.0.2.2:8000` and nobody
else can. Every request shows up here, which is how you know the VM got the
files.

## 4. The four installs

Do them in any order, one window at a time. For each one:

1. **Start it** with the command in the table. A QEMU window opens with the
   live session.
2. **Prepare the installer.** Open a terminal in the VM (Super+Enter) and run:

   ```sh
   curl -fsS http://10.0.2.2:8000/setup-live.sh | sh
   ```

   It ends with `3/3 done`. Don't start the installer before that, because
   Calamares reads its configs once, at start.
3. **Install** with *Install FlickOS*:
   - *Users*: name `spike`, password `spike`, **untick** *Log in
     automatically* (you want to see the login screen).
   - *Partitions*: *Erase disk*, then the choices in the table.
   - **Note while you go:** is the filesystem drop-down there with btrfs
     already picked? Which swap choices are offered? Any warning? How long
     did *Install* take?
4. **Restart** at the end (*Restart now*). The VM starts from the new disk.
   Check that you reach the **login screen**, then log in once as
   `spike`/`spike`.
5. **Close the window** (that's pulling the plug, which is fine here).

| Name | Command | On the Partitions page | Extra check |
|---|---|---|---|
| `uefi-btrfs` | `./vm.sh install uefi-btrfs --size 15G --mem 2G` | btrfs, *Swap (no Hibernate)*, no encryption | the smallest disk the installer allows, and a 2 GB computer |
| `bios-btrfs` | `./vm.sh install bios-btrfs --bios` | btrfs, ***Swap (with Hibernate)***, no encryption | hibernation, below |
| `uefi-luks` | `./vm.sh install uefi-luks` | btrfs, *Swap (no Hibernate)*, tick ***Encrypt system***, passphrase `spikepass` | count the passphrase questions at start |
| `uefi-ext4` | `./vm.sh install uefi-ext4` | pick **ext4** in the drop-down, *Swap (no Hibernate)* | none: this checks the mount option fix without btrfs |

Calamares may warn that `spike` and `spikepass` are weak. Accept it, they're
throwaway disks.

**Hibernation (only `bios-btrfs`, 3 minutes):** after logging in, open a
terminal and run `systemctl hibernate`. The window goes black and QEMU stops.
Start it again with `./vm.sh boot bios-btrfs`. If the desktop comes back as
you left it (the terminal still open), resuming works. If you get the login
screen instead, it didn't. Write down which.

**Encryption (only `uefi-luks`):** when it starts, GRUB asks for the
passphrase *before* the boot menu. Note how many seconds it thinks after
Enter (GRUB unlocks LUKS slowly), and whether a second question comes later
during the start. The design hopes for exactly one.

**If something goes wrong** (the installer fails, or the start hangs), take a
screenshot or note the message, and keep the disk. It's a result too.

`./vm.sh list` shows the disks, `./vm.sh boot NAME` starts one again, and
`./vm.sh delete NAME` removes it.

## 5. The checks (Claude runs these, or you can)

When the four installs are done, stop `serve.sh` (Ctrl+C) and tell Claude.
Each disk is then checked without a window:

```sh
./check-disk.py uefi-btrfs
./check-disk.py bios-btrfs
./check-disk.py uefi-luks --passphrase spikepass
./check-disk.py uefi-ext4
```

What it does, and why it can't harm the installs:

- **layout:** boots the live ISO (straight from its kernel, the way
  `tools/boot-test.py` does), logs in on the **serial console** (a text line
  QEMU connects to the script, no screen needed), downloads
  `check-layout.sh` from a small web server the script starts itself, and runs
  it as root. That mounts the disk **read-only**, lists the subvolumes,
  checks `/etc/fstab`, the kernel line in `grub.cfg`, swap and `resume=`, the
  boot image (initramfs), and space. Every line starts with `PASS`, `FAIL` or
  `NOTE`. Saved as `results/NAME-layout.txt`.
- **boot:** starts the installed disk itself without a window, types the
  passphrase through QEMU's control socket (**QMP**: a JSON line protocol for
  driving QEMU from a script; `send-key` presses keys, `screendump` saves a
  picture), and saves a screenshot every 15 s as `results/NAME-boot-*.png`.
- Both attach the disk with **`snapshot=on`**: QEMU writes every change into
  a temporary file that is thrown away. The UEFI variables are a copy too. A
  check never changes the install.

## 6. Results

Fill in **Result** and **Evidence** in `results.md` from your notes and the
`results/` files (or let Claude do it). Then the results go into the design
doc's phase 0 section. Keep the disks for now: items 2–6 start from
`uefi-btrfs`. The others can go once item 1's results are written down
(`./vm.sh delete NAME`).

## Commands worth keeping

| Command | For |
|---|---|
| `btrfs subvolume list /mnt` | the subvolumes of a mounted btrfs |
| `mount -o ro,subvolid=5 DEV /mnt` | the top level, where flat subvolumes sit |
| `btrfs filesystem usage -T /mnt` | real space use (`df` is vague on btrfs) |
| `cryptsetup luksDump DEV` | an encrypted partition's header: version, KDF |
| `lsinitramfs /boot/initrd.img-*` | what's in the boot image |
| `qemu-img create -f qcow2 F 20G` | a disk that grows as it's written |
| `-drive file=F,if=virtio,snapshot=on` | use a disk without ever changing it |
| `-qmp unix:SOCK,server=on,wait=off` | drive QEMU from a script (keys, screenshots) |
| `python3 -m http.server --bind 127.0.0.1` | hand files to a VM on `10.0.2.2` |
