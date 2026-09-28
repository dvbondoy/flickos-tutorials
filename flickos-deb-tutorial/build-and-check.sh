#!/bin/sh
# build-and-check.sh: build one package folder the way FlickOS's
# packages/build.sh does (from a copy, so the folder stays clean), then show
# what came out: the control fields, the file list and lintian's verdict.
#
#   ./build-and-check.sh work/flickos-hello          .deb into ./out/
#   ./build-and-check.sh PACKAGE_FOLDER OUT_FOLDER   .deb into OUT_FOLDER
#   DEB_BUILD_OPTIONS=nocheck ./build-and-check.sh …   skip the unit tests
#
# Works for any package folder with a debian/ inside, the repo's too:
#   ./build-and-check.sh $FLICKOS/packages/flickos-welcome

set -e
[ -d "$1/debian" ] || { sed -n '6,11p' "$0"; exit 2; }
src=$(cd "$1" && pwd)
out=$(mkdir -p "${2:-out}" && cd "${2:-out}" && pwd)
pkg=$(basename "$src")
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

echo "==> building $pkg from a copy in $work"
cp -r "$src" "$work/$pkg"
(cd "$work/$pkg" && dpkg-buildpackage -us -uc -b) >"$out/$pkg.build.log" 2>&1 || {
    tail -25 "$out/$pkg.build.log"
    echo "==> the build failed; the whole log is $out/$pkg.build.log" >&2
    exit 1
}
for deb in "$work"/*.deb; do
    cp "$deb" "$out/"
    name=$(basename "$deb")
    echo
    echo "==> $out/$name"
    dpkg-deb -f "$deb" Package Version Architecture Depends Recommends
    echo
    echo "--- files"
    dpkg-deb -c "$deb" | awk '$1 !~ /^d/ { print $1, $6 }'
    echo
    echo "--- lintian"
    # lintian exits 0 on warnings and 1 on errors: judge by what it prints.
    report=$(lintian "$deb" 2>&1) || true
    echo "${report:-(nothing to report)}"
done
echo
echo "==> log: $out/$pkg.build.log"
