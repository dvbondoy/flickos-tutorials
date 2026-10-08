#!/bin/sh
# Run real account tools (adduser, userdel, usermod, gpasswd) as a fake root
# against a COPY of /etc, without sudo and without touching your system.
#
#   tools/userns-lab.sh run 'adduser --quiet --system --comment x labsys; getent passwd labsys'
#   tools/userns-lab.sh reset          # throw the copy away; the next run makes a fresh one
#
# How: unshare(1) makes a user namespace where your own uid is mapped to 0
# ("root" that is only root over things you own) and a mount namespace where
# the copy is bind-mounted over /etc, /home, /var/log and a tmpfs over /run.
# Only your uid is mapped, so:
#   * creating a REGULAR account fails at "chown 1001:1001 /home/x" (that uid
#     doesn't exist in here). Use --system accounts, or a VM, for those;
#   * chpasswd fails (PAM can't open its session in here);
#   * nothing outside the lab folder can change: the real /etc is read-only
#     to you, inside the namespace too.
set -e

LAB="${LAB:-$(dirname "$0")/../work/lab}"

setup() {
    mkdir -p "$LAB/etc" "$LAB/home" "$LAB/log"
    for f in passwd group login.defs adduser.conf deluser.conf nsswitch.conf shells ld.so.cache \
             ld.so.conf environment; do
        [ -r "/etc/$f" ] && cp "/etc/$f" "$LAB/etc/"
    done
    for d in skel default ld.so.conf.d alternatives pam.d security; do
        [ -d "/etc/$d" ] && cp -a "/etc/$d" "$LAB/etc/" 2>/dev/null || true
    done
    # The real shadow files aren't readable: make locked entries for every name.
    awk -F: '{print $1":*:19000:0:99999:7:::"}' "$LAB/etc/passwd" > "$LAB/etc/shadow"
    awk -F: '{print $1":*::"}' "$LAB/etc/group" > "$LAB/etc/gshadow"
    chmod 640 "$LAB/etc/shadow" "$LAB/etc/gshadow"
    echo "userns-lab: new lab in $LAB" >&2
}

case "$1" in
    run)
        shift
        [ -f "$LAB/etc/passwd" ] || setup
        LAB="$(cd "$LAB" && pwd)"
        exec unshare --user --map-root-user --mount sh -c '
            set -e
            lab="$1"; shift
            mount --bind "$lab/etc" /etc
            mount --bind "$lab/log" /var/log
            mount -t tmpfs tmpfs /run
            # Last: the lab itself may live under /home.
            mount --bind "$lab/home" /home
            export PATH=/usr/sbin:/usr/bin:/sbin:/bin
            sh -c "$1"
        ' lab "$LAB" "$*" 2>&1 | grep -v "^logger: send message failed"
        ;;
    reset)
        rm -rf "$LAB"
        echo "userns-lab: removed $LAB" >&2
        ;;
    *)
        echo "usage: $0 run 'COMMANDS' | reset" >&2
        exit 2
        ;;
esac
