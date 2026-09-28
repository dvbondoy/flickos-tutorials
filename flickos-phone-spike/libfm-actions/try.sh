#!/bin/sh
# Put one round of test actions where PCManFM looks, or take them away.
#   ./try.sh round-2     install that round (replaces any earlier round)
#   ./try.sh remove      remove them all
# Then close and reopen PCManFM and right-click a file. Needs libfm-modules.
set -e
cd "$(dirname "$0")"
dest="$HOME/.local/share/file-manager/actions"
rm -f "$dest"/flickos-spike-*.desktop
if [ "$1" = remove ]; then
    rmdir "$dest" "$HOME/.local/share/file-manager" 2>/dev/null || true
    echo "removed"
    exit 0
fi
[ -d "$1" ] || { echo "usage: $0 round-1|round-2|round-3|round-4|remove"; exit 1; }
mkdir -p "$dest"
cp "$1"/*.desktop "$dest/"
dpkg -s libfm-modules >/dev/null 2>&1 || echo "note: libfm-modules isn't installed, so PCManFM shows no actions at all"
echo "installed $1:"; ls "$dest"
