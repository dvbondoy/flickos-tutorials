#!/bin/sh
# package-cost.sh: what installing packages would really add to this
# system, the way the FlickOS image installs them (without Recommends).
# Asks apt to simulate (-s); nothing is installed and no sudo is needed.
#
#   ./package-cost.sh swappy
#   ./package-cost.sh wf-recorder
#   ./package-cost.sh gstreamer1.0-pipewire gstreamer1.0-tools

[ $# -gt 0 ] || { echo "usage: $0 PACKAGE..." >&2; exit 2; }

# "Inst NAME (VERSION ...)" is one line per package apt would install.
new=$(LC_ALL=C apt-get install -s --no-install-recommends "$@" 2>&1 | awk '/^Inst / {print $2}')
if [ -z "$new" ]; then
    echo "nothing new: already installed, or apt could not do it:"
    LC_ALL=C apt-get install -s --no-install-recommends "$@" 2>&1 | tail -3
    exit 0
fi

# Installed-Size is in KB, Size (the download) in bytes.
echo "$new" | xargs apt-cache show --no-all-versions 2>/dev/null | awk '
    /^Package:/        { p = $2 }
    /^Installed-Size:/ { i = $2 }
    /^Size:/           { printf "  %-28s %8d KB on disk %8d KB download\n", p, i, $2 / 1024
                         ti += i; td += $2 / 1024; n++ }
    END                { printf "  %-28s %8d KB on disk %8d KB download\n", n " packages", ti, td }'
