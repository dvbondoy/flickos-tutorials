#!/bin/sh
# check-layout.sh [PASSPHRASE]: what an install put on the disk, checked
# against design ADR-001. Runs as root in the live session, with the installed
# disk as /dev/vda (check-disk.py does all that). Mounts everything read-only
# and changes nothing.
PASS="$1"
FAILS=0
say() { printf '\n== %s\n' "$*"; }
ok()  { echo "PASS  $*"; }
bad() { echo "FAIL  $*"; FAILS=$((FAILS + 1)); }
note() { echo "NOTE  $*"; }

say "partitions"
lsblk -o NAME,SIZE,FSTYPE,FSVER,PARTLABEL /dev/vda

# The root filesystem: the biggest partition that is btrfs, ext4 or LUKS
# (an encrypted install has an encrypted swap partition too).
ROOTDEV=$(lsblk -blnpo NAME,SIZE,FSTYPE /dev/vda |
          awk '$3 ~ /^(btrfs|ext4|crypto_LUKS)$/ { print $2, $1 }' | sort -n | tail -n1 | cut -d' ' -f2)
[ -n "$ROOTDEV" ] || { echo "FAIL  no root partition found"; exit 1; }
ROOTTYPE=$(blkid -o value -s TYPE "$ROOTDEV")
SWAPDEV=$(lsblk -lnpo NAME,FSTYPE /dev/vda | awk '$2 == "swap" { print $1 }')

if [ "$ROOTTYPE" = crypto_LUKS ]; then
    say "encryption"
    cryptsetup luksDump "$ROOTDEV" | grep -E '^(Version|Cipher name|Hash spec)|PBKDF' | head -5
    [ -n "$PASS" ] || { echo "FAIL  encrypted: give the passphrase (check-disk.py --passphrase)"; exit 1; }
    printf %s "$PASS" | cryptsetup open --readonly --key-file - "$ROOTDEV" spikeroot ||
        { echo "FAIL  the passphrase doesn't open $ROOTDEV"; exit 1; }
    ok "opened $ROOTDEV with the passphrase"
    ROOTDEV=/dev/mapper/spikeroot
    ROOTTYPE=$(blkid -o value -s TYPE "$ROOTDEV")
    # The swap partition is encrypted too: open it to see what's inside.
    for p in $(lsblk -lnpo NAME,FSTYPE /dev/vda | awk '$2 == "crypto_LUKS" { print $1 }'); do
        [ "$p" = "$(cryptsetup status spikeroot | awk '/device:/ { print $2 }')" ] && continue
        printf %s "$PASS" | cryptsetup open --readonly --key-file - "$p" spikeswap 2>/dev/null &&
            SWAPDEV=/dev/mapper/spikeswap && note "encrypted swap partition $p"
    done
fi
echo "root: $ROOTDEV ($ROOTTYPE)  swap: ${SWAPDEV:-none}"

mkdir -p /mnt/top /mnt/sys
if [ "$ROOTTYPE" = btrfs ]; then
    mount -o ro,subvolid=5 "$ROOTDEV" /mnt/top
    say "subvolumes"
    btrfs subvolume list /mnt/top
    echo "default subvolume: $(btrfs subvolume get-default /mnt/top)"
    for s in @ @home @log @cache @snapshots; do
        if btrfs subvolume show "/mnt/top/$s" >/dev/null 2>&1; then ok "subvolume $s"; else bad "subvolume $s missing"; fi
    done
    SYS=/mnt/top/@
else
    mount -o ro "$ROOTDEV" /mnt/sys
    SYS=/mnt/sys
fi

say "/etc/fstab"
grep -v '^#' "$SYS/etc/fstab" | grep .
if [ "$ROOTTYPE" = btrfs ]; then
    for pair in /:/@ /home:/@home /var/log:/@log /var/cache:/@cache /.snapshots:/@snapshots; do
        mp=${pair%%:*}; sv=${pair#*:}
        line=$(awk -v mp="$mp" '$2 == mp && $3 == "btrfs"' "$SYS/etc/fstab")
        case "$line" in
            *"subvol=$sv,"*|*"subvol=$sv "*) ok "fstab $mp is subvol=$sv" ;;
            "") bad "fstab has no btrfs line for $mp" ;;
            *) bad "fstab $mp: $line" ;;
        esac
    done
    awk '$3 == "btrfs"' "$SYS/etc/fstab" | grep -qv 'noatime' && bad "a btrfs line without noatime" || ok "every btrfs line has noatime"
    awk '$3 == "btrfs"' "$SYS/etc/fstab" | grep -qv 'compress=zstd:1' && bad "a btrfs line without compress=zstd:1" || ok "every btrfs line has compress=zstd:1"
else
    awk '$2 == "/"' "$SYS/etc/fstab" | grep -q noatime && ok "/ has noatime (mountOptions are read)" || bad "/ has no noatime (mountOptions not read)"
fi
awk '$1 !~ /^#/ && $4 ~ /discard/' "$SYS/etc/fstab" | grep -q . && bad "a mount with discard" || ok "no discard in fstab"
awk '$3 == "vfat"' "$SYS/etc/fstab" | grep -q . && note "EFI line: $(awk '$3 == "vfat" { print $2, $4 }' "$SYS/etc/fstab")"

if [ -e "$SYS/etc/crypttab" ]; then
    say "/etc/crypttab"
    grep -v '^#' "$SYS/etc/crypttab" | grep .
fi

say "where the files went"
if [ "$ROOTTYPE" = btrfs ]; then
    for pair in var/log:@log var/cache:@cache home:@home; do
        dir=${pair%%:*}; sv=${pair#*:}
        in_sys=$(find "$SYS/$dir" -mindepth 1 2>/dev/null | wc -l)
        in_sv=$(find "/mnt/top/$sv" -mindepth 1 2>/dev/null | wc -l)
        echo "/$dir: $in_sys entries inside @, $in_sv inside $sv"
        [ "$in_sys" -eq 0 ] && ok "/$dir is empty inside @ (its files are in $sv)" || bad "/$dir has files inside @"
    done
    [ -n "$(ls "$SYS"/boot/vmlinuz-* 2>/dev/null)" ] && ok "kernels are inside @ (/boot is in the snapshots)" || bad "no kernel in @/boot"
fi

say "boot loader"
grep -E '^GRUB_(CMDLINE_LINUX|DISTRIBUTOR|TIMEOUT|DEFAULT|SAVEDEFAULT)' "$SYS/etc/default/grub"
ls "$SYS"/etc/default/grub.d/ 2>/dev/null | sed 's/^/grub.d: /'
LINUX=$(grep -m1 -E '^\s*linux\s' "$SYS/boot/grub/grub.cfg" | sed 's/^\s*//')
echo "first entry: $LINUX"
if [ "$ROOTTYPE" = btrfs ]; then
    case "$LINUX" in *rootflags=subvol=@*) ok "rootflags=subvol=@ on the kernel line (Debian's 10_linux)" ;; *) bad "no rootflags=subvol=@" ;; esac
fi
echo "submenus: $(grep -c '^submenu' "$SYS/boot/grub/grub.cfg"), entries: $(grep -c 'menuentry ' "$SYS/boot/grub/grub.cfg")"
grep -q 'recordfail' "$SYS/boot/grub/grub.cfg" && note "grub.cfg mentions recordfail" || note "no recordfail in grub.cfg (quick_boot=0, as expected)"
[ -e "$SYS/boot/grub/grubenv" ] && note "grubenv exists ($(stat -c %s "$SYS/boot/grub/grubenv") bytes)"
[ -d "$SYS/boot/efi" ] && ls "$SYS/boot/efi" >/dev/null 2>&1 && note "EFI partition not mounted here (it's separate)"

say "swap and hibernation"
if [ -n "$SWAPDEV" ]; then
    SWAPUUID=$(blkid -o value -s UUID "$SWAPDEV")
    echo "swap UUID: $SWAPUUID, size $(lsblk -bndo SIZE "$SWAPDEV" | awk '{ printf "%.1f GiB", $1 / 1073741824 }')"
    case "$LINUX" in
        *resume=*) ok "resume= on the kernel line: $(echo "$LINUX" | grep -o 'resume=[^ ]*')" ;;
        *) note "no resume= on the kernel line" ;;
    esac
    cat "$SYS"/etc/initramfs-tools/conf.d/resume 2>/dev/null | sed 's/^/initramfs resume: /'
else
    note "no swap partition"
fi

say "boot image (initramfs)"
INITRD=$(ls -1 "$SYS"/boot/initrd.img-* 2>/dev/null | tail -n1)
if [ -n "$INITRD" ] && command -v lsinitramfs >/dev/null; then
    lsinitramfs "$INITRD" > /tmp/initrd.list
    grep -q 'btrfs.ko' /tmp/initrd.list && ok "btrfs module in the initramfs" || note "no btrfs.ko in the initramfs (built in, or missing)"
    grep -qE 'sbin/btrfs$' /tmp/initrd.list && note "btrfs tool in the initramfs" || note "no btrfs tool in the initramfs"
    grep -q 'cryptroot' /tmp/initrd.list && note "cryptroot in the initramfs"
    grep -q 'crypto_keyfile' /tmp/initrd.list && note "a LUKS key file in the initramfs (no second passphrase)"
fi

say "packages in the installed system"
for p in btrfs-progs cryptsetup-initramfs snapper; do
    if grep -q "^Package: $p$" "$SYS/var/lib/dpkg/status" &&
       awk -v p="$p" '$0 == "Package: " p { f = 1 } f && /^Status:/ { print; exit }' "$SYS/var/lib/dpkg/status" | grep -q 'install ok installed'; then
        note "$p installed"
    else
        note "$p NOT installed"
    fi
done

say "space"
if [ "$ROOTTYPE" = btrfs ]; then
    btrfs filesystem usage -T /mnt/top 2>/dev/null | sed -n '1,12p'
    for s in @ @home @log @cache; do
        printf '%-8s ' "$s"; du -sh --apparent-size "/mnt/top/$s" 2>/dev/null | cut -f1 | tr -d '\n'; echo " apparent"
    done
else
    df -h /mnt/sys
fi

umount /mnt/top 2>/dev/null; umount /mnt/sys 2>/dev/null
cryptsetup close spikeswap 2>/dev/null; cryptsetup close spikeroot 2>/dev/null
say "result"
[ "$FAILS" -eq 0 ] && echo "all checks passed" || echo "$FAILS check(s) failed"
exit $(( FAILS > 0 ))
