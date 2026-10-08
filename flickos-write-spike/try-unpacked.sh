#!/bin/sh
# try-unpacked.sh: download packages and unpack them into ./unpacked/ so a
# program can be tried without installing it (no sudo, nothing in /usr).
# Then lists, for each program, the libraries it can't find.
#
#   ./try-unpacked.sh swappy wf-recorder
#   LD_LIBRARY_PATH=unpacked/usr/lib/x86_64-linux-gnu unpacked/usr/bin/swappy --help

cd "$(dirname "$0")" || exit 1
[ $# -gt 0 ] || { echo "usage: $0 PACKAGE..." >&2; exit 2; }
mkdir -p debs unpacked

for p in "$@"; do
    # One name per call: one unknown name would fail the whole download.
    (cd debs && apt-get download "$p" >/dev/null) || { echo "could not download $p"; continue; }
    for deb in debs/"$p"_*.deb; do
        dpkg-deb -x "$deb" unpacked
        echo "unpacked $(basename "$deb")"
    done
done

libs=unpacked/usr/lib/x86_64-linux-gnu
echo
for prog in unpacked/usr/bin/*; do
    missing=$(LD_LIBRARY_PATH=$libs ldd "$prog" 2>/dev/null | awk '/not found/ {print $1}')
    if [ -n "$missing" ]; then
        echo "$(basename "$prog"): can't run here, missing: $(echo $missing)"
    else
        echo "$(basename "$prog"): all libraries found"
    fi
done
