#!/bin/sh
# get-input-tools.sh: download wtype (a keyboard) and wlrctl (a mouse) and
# unpack them into ./tools/, without installing anything. Run it once.
#
# The harness has no real keyboard or mouse. These make virtual ones through
# the zwp_virtual_keyboard and zwlr_virtual_pointer protocols labwc offers.

cd "$(dirname "$0")" || exit 1
mkdir -p tools/debs
for p in wtype wlrctl; do
    if command -v "$p" >/dev/null; then
        echo "$p is installed; nothing to do"
        continue
    fi
    (cd tools/debs && apt-get download "$p" >/dev/null) || { echo "could not download $p"; exit 1; }
    dpkg-deb -x tools/debs/"$p"_*.deb tools
    echo "unpacked $p into tools/usr/bin"
done
for p in tools/usr/bin/*; do
    [ -e "$p" ] || continue
    if ldd "$p" | grep -q "not found"; then
        echo "$(basename "$p"): missing libraries:"; ldd "$p" | grep "not found"
    else
        echo "$(basename "$p"): ready"
    fi
done
