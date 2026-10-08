#!/bin/sh
# setup-live.sh: run INSIDE the live VM, before starting the installer:
#
#   curl -fsS http://10.0.2.2:8000/setup-live.sh | sh
#
# 10.0.2.2 is this spike's computer as QEMU's user network shows it; serve.sh
# answers there. The live session keeps every change in memory, so a restart
# of the live VM undoes all of this.
set -e
BASE=http://10.0.2.2:8000

echo "1/3  btrfs-progs (Calamares needs mkfs.btrfs; the image doesn't have it yet)"
sudo apt-get update -qq            # the image has no package lists
sudo apt-get install -y -qq btrfs-progs >/dev/null
command -v mkfs.btrfs

echo "2/3  the spike's Calamares configs"
for f in partition mount fstab; do
    sudo curl -fsS -o "/etc/calamares/modules/$f.conf" "$BASE/calamares/$f.conf"
    echo "     /etc/calamares/modules/$f.conf"
done

echo "3/3  done. Now start the installer (Install FlickOS)."
