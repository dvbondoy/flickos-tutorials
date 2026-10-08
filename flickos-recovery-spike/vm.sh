#!/bin/bash
# vm.sh: a QEMU window for one named test disk of this spike.
#
#   ./vm.sh install NAME [--bios] [--size 20G] [--mem 4G]   boot the ISO, disk attached
#   ./vm.sh boot NAME                                       boot the installed disk
#   ./vm.sh list                                            the disks and their size on this computer
#   ./vm.sh delete NAME                                     delete a disk
#
# The same as the repo's tools/test-iso.sh, but each install gets its own disk
# (vm/NAME.qcow2), its own UEFI variables (vm/NAME.vars) and remembers its
# firmware (vm/NAME.firmware), so several installs can be kept side by side
# and the repo's .test-vm/ disk is never touched.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="${FLICKOS_REPO:-${FLICKOS:-$HOME/Documents/Projects/FlickOS}}"
VM="$HERE/vm"
OVMF_CODE=/usr/share/OVMF/OVMF_CODE_4M.fd
OVMF_VARS=/usr/share/OVMF/OVMF_VARS_4M.fd

die() { echo "$*" >&2; exit 2; }

action="${1:-}"; name="${2:-}"
[ -n "$action" ] || die "usage: ./vm.sh install|boot|list|delete NAME (see the top of this file)"
shift || true; shift || true

firmware=uefi size=20G mem=4G
while [ $# -gt 0 ]; do
    case "$1" in
        --bios) firmware=bios ;;
        --uefi) firmware=uefi ;;
        --size) size="${2:?}"; shift ;;
        --mem) mem="${2:?}"; shift ;;
        *) die "unknown option: $1" ;;
    esac
    shift
done

case "$action" in
    list)
        mkdir -p "$VM"
        for disk in "$VM"/*.qcow2; do
            [ -e "$disk" ] || { echo "no disks yet"; exit 0; }
            n="$(basename "$disk" .qcow2)"
            echo "$n  $(cat "$VM/$n.firmware" 2>/dev/null)  $(du -h "$disk" | cut -f1) used on this computer"
        done
        exit 0 ;;
    delete)
        [ -n "$name" ] || die "delete which disk?"
        rm -f "$VM/$name.qcow2" "$VM/$name.vars" "$VM/$name.firmware"
        echo "deleted $name"
        exit 0 ;;
    install|boot) [ -n "$name" ] || die "$action needs a NAME" ;;
    *) die "unknown action: $action" ;;
esac

disk="$VM/$name.qcow2"
mkdir -p "$VM"
if [ "$action" = install ]; then
    [ -e "$disk" ] && die "$name exists already: ./vm.sh delete $name first, or ./vm.sh boot $name"
    iso="$(ls -1t "$REPO"/FlickOS-64bit-v*.iso 2>/dev/null | head -n1 || true)"
    [ -n "$iso" ] || die "no ISO in $REPO"
    qemu-img create -q -f qcow2 "$disk" "$size"
    echo "$firmware" > "$VM/$name.firmware"
    echo "created $disk ($size, $firmware), ISO $(basename "$iso")"
else
    [ -e "$disk" ] || die "no disk $name: ./vm.sh install $name first"
    firmware="$(cat "$VM/$name.firmware")"
fi

args=(-name "recovery spike - $name - $firmware" -m "$mem" -smp 2
      -device virtio-vga -nic user,model=virtio-net-pci -usb -device usb-tablet
      -drive "file=$disk,if=virtio")
[ -w /dev/kvm ] && args+=(-enable-kvm -cpu host)
if [ "$firmware" = uefi ]; then
    [ -e "$VM/$name.vars" ] || cp "$OVMF_VARS" "$VM/$name.vars"
    args+=(-drive "if=pflash,format=raw,readonly=on,file=$OVMF_CODE"
           -drive "if=pflash,format=raw,file=$VM/$name.vars")
fi
if [ "$action" = install ]; then
    # Boot the ISO once; the restart at the end of the install starts the disk.
    args+=(-cdrom "$iso" -boot once=d)
fi
exec qemu-system-x86_64 "${args[@]}"
