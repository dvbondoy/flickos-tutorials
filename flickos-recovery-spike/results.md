# Restore points spike, item 1: results

Date: ____  Design doc: `docs/design/flickos-recovery.md`  ISO: `FlickOS-64bit-v2.1.iso`

Write the **prediction before** installing and the **result after**. Where they
differ, add one line on why.

## Questions

| # | Question | Why it matters | Your prediction | Result | Evidence |
|---|---|---|---|---|---|
| Q1 | Does the installer offer btrfs already picked, with ext4 in the drop-down? | ADR-001: btrfs by default, ext4 still possible | | | your notes |
| Q2 | Are all five subvolumes made, with `/var/log`, `/var/cache` and `/home`'s files in their own (empty inside `@`)? | A restore must never put back logs or your files | | | `NAME-layout.txt`: subvolumes, where the files went |
| Q3 | Does fstab get `subvol=`, `noatime`, `compress=zstd:1` and no `discard`? Does ext4 now get `noatime`? | The mount option bug fix (phase 1a), and ADR-001's options | | | `NAME-layout.txt`: /etc/fstab |
| Q4 | Does the install start to the login screen on UEFI **and** BIOS, with `rootflags=subvol=@` on the kernel line? | Debian's GRUB on btrfs, untouched (ADR-003 relies on that line) | | | your notes, `NAME-boot-*.png`, boot loader section |
| Q5 | With *Swap (with Hibernate)*: is `resume=` set, and does hibernating and resuming work on btrfs? | ADR-001 keeps a swap partition for exactly this | | | your notes (bios-btrfs), swap section |
| Q6 | Encrypted: does GRUB unlock LUKS1 with `/boot` inside `@`? How many passphrase questions, and how long does GRUB take? | The risk "Encrypted installs" in the design | | | your notes (uefi-luks), encryption section |
| Q7 | How much of the disk does a new install use, btrfs (compressed) vs ext4? What's left on a 15 GB disk? | The 15 GB minimum, and room for restore points | | | space sections |
| Q8 | Without `btrfs-progs` in the image, what's missing in the installed system, and does it matter? | Phase 1a must add it to the image *and* make sure installs keep it | | | packages and initramfs sections |

## Installs

| Name | Install time | Warnings in the installer | Login screen after restart? | Notes |
|---|---|---|---|---|
| uefi-btrfs (15 GB, 2 GB RAM) | | | | |
| bios-btrfs (hibernate) | | | | resumed? |
| uefi-luks | | | | prompts: ___, GRUB unlock: ___ s |
| uefi-ext4 | | | | |

## Checks

| Disk | `check-disk.py` result | FAILs |
|---|---|---|
| uefi-btrfs | | |
| bios-btrfs | | |
| uefi-luks | | |
| uefi-ext4 | | |

## Space (Q7)

| Disk | Used after install | Free | How measured |
|---|---|---|---|
| uefi-btrfs | | | `btrfs filesystem usage` |
| uefi-ext4 | | | `df` |

## Decision, in one sentence

## New questions found on the way

-

## Cleanup done

- [ ] `serve.sh` stopped
- [ ] results written into the design doc
- [ ] `bios-btrfs`, `uefi-luks`, `uefi-ext4` deleted (`./vm.sh delete NAME`); `uefi-btrfs` kept for items 2–6
