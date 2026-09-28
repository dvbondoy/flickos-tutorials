#!/bin/sh
# local-repo.sh: a throwaway signed apt repository on this computer, for
# testing upgrades in a VM before anything is published. The same tools as
# FlickOS's real repo (repo/new-key.sh, repo/publish.sh): gpg + reprepro.
#
#   ./local-repo.sh init            a new key and an empty repo in ./local-repo/
#   ./local-repo.sh add FILE.deb …  add packages (a higher version replaces the old one)
#   ./local-repo.sh list            what the repo holds
#   ./local-repo.sh remove NAME     take a package out again
#   ./local-repo.sh serve           serve it at http://127.0.0.1:8000 until Ctrl+C
#                                   (the VM sees it as http://10.0.2.2:8000)
#   ./local-repo.sh clean           delete the repo and its key
#
# The key has no passphrase and lives only in ./local-repo/gnupg/, never in
# ~/.gnupg, so it can't be mixed up with FlickOS's real signing key.
# LOCAL_REPO=DIR and PORT=N change the folder and the port.

set -e
cd "$(dirname "$0")"
REPO=${LOCAL_REPO:-$PWD/local-repo}
PORT=${PORT:-8000}
export GNUPGHOME="$REPO/gnupg"

need_repo() {
    [ -f "$REPO/conf/distributions" ] || { echo "no repo yet: ./local-repo.sh init" >&2; exit 1; }
}

case "$1" in
init)
    [ ! -e "$REPO" ] || { echo "$REPO exists already (./local-repo.sh clean first)" >&2; exit 1; }
    mkdir -p "$REPO/conf" "$REPO/public"
    mkdir -m 700 "$GNUPGHOME"
    gpg --batch --quiet --passphrase '' \
        --quick-gen-key "FlickOS test repo (throwaway) <test@localhost>" ed25519 sign 1y
    fpr=$(gpg --list-secret-keys --with-colons | awk -F: '/^fpr/ { print $10; exit }')
    cat >"$REPO/conf/distributions" <<EOF
Origin: FlickOS-test
Label: FlickOS-test
Codename: trixie
Architectures: amd64
Components: main
Description: throwaway test repository
SignWith: $fpr
EOF
    printf 'outdir +b/public\ndbdir +b/db\n' >"$REPO/conf/options"
    gpg --armor --export "$fpr" >"$REPO/public/test-key.asc"
    echo "repo:   $REPO/public/"
    echo "key:    $fpr (public half: $REPO/public/test-key.asc)"
    ;;
add)
    need_repo
    shift
    [ $# -gt 0 ] || { echo "add which .deb files?" >&2; exit 2; }
    for deb in "$@"; do
        reprepro -b "$REPO" includedeb trixie "$deb"
    done
    reprepro -b "$REPO" list trixie
    ;;
list)
    need_repo
    reprepro -b "$REPO" list trixie
    ;;
remove)
    need_repo
    reprepro -b "$REPO" remove trixie "$2"
    reprepro -b "$REPO" list trixie
    ;;
serve)
    need_repo
    echo "serving $REPO/public at http://127.0.0.1:$PORT (in the VM: http://10.0.2.2:$PORT), Ctrl+C stops"
    exec python3 -m http.server --bind 127.0.0.1 --directory "$REPO/public" "$PORT"
    ;;
clean)
    rm -rf "$REPO"
    echo "deleted $REPO"
    ;;
*)
    sed -n '6,16p' "$0"
    exit 2
    ;;
esac
