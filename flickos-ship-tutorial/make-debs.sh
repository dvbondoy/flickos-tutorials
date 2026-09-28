#!/bin/sh
# make-debs.sh: build the example package's three versions into debs/.
#
#   ./make-debs.sh
#
#   versions/flickos-hello-1.0   the package from the .deb tutorial
#   versions/flickos-hello-1.1   the greeting is Mabuhay (a changed conffile)
#   versions/flickos-hello-1.2   --big, which needs figlet (a new dependency)
#
# See what changed between two versions: diff -ru versions/flickos-hello-1.1 versions/flickos-hello-1.2
# Each is built from a copy (like FlickOS's packages/build.sh), so versions/
# stays clean.

set -e
cd "$(dirname "$0")"
mkdir -p debs
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
for src in versions/flickos-hello-*; do
    cp -r "$src" "$work/flickos-hello"
    (cd "$work/flickos-hello" && dpkg-buildpackage -us -uc -b) >"$work/build.log" 2>&1 || {
        tail -20 "$work/build.log"
        echo "building $src failed" >&2
        exit 1
    }
    rm -rf "$work/flickos-hello"
done
mv "$work"/*.deb debs/
ls -1 debs/
