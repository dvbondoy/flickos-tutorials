#!/bin/sh
# check-machine.sh: what this computer can do for the idea being spiked.
# It only reads; it changes nothing. Keep a copy with the results:
#
#   ./check-machine.sh | tee machine.txt
#
# Edit the three lists below for each spike; delete sections you don't need.

# 1. Packages the idea uses or might use (installed version, or "no").
PACKAGES="python3-gi gir1.2-gtk-3.0 gir1.2-gtksource-4 libgtksourceview-4-0 fonts-dejavu-core fonts-dejavu-extra libreoffice-writer-nogui libreoffice-writer flickos-phone adb"
# 2. Wayland protocols to look for (from `wayland-info`); empty to skip.
PROTOCOLS="zwlr_layer_shell_v1 zwlr_foreign_toplevel_manager_v1"
# 3. D-Bus properties to read: "service object interface property" per line.
DBUS_PROPERTIES="
org.freedesktop.portal.Desktop /org/freedesktop/portal/desktop org.freedesktop.portal.ScreenCast version
"

section() { printf '\n== %s\n' "$1"; }

section "FlickOS and Debian"
. /etc/os-release && echo "  $PRETTY_NAME"
dpkg-query -W -f='  ${Package} ${Version}\n' 'flickos-*' 2>/dev/null | grep -v '^  $'

section "Packages (installed version, or 'no')"
for p in $PACKAGES; do
    v=$(dpkg-query -W -f='${Status} ${Version}' "$p" 2>/dev/null | sed -n 's/^install ok installed //p')
    printf '  %-32s %s\n' "$p" "${v:-no}"
done

if [ -n "$PROTOCOLS" ]; then
    section "Wayland protocols the compositor offers"
    offered=$(wayland-info 2>/dev/null | grep -oE "interface: '[a-z0-9_]+'" | cut -d"'" -f2)
    for i in $PROTOCOLS; do
        if echo "$offered" | grep -qx "$i"; then r=yes; else r=no; fi
        printf '  %-52s %s\n' "$i" "$r"
    done
fi

if [ -n "$(echo $DBUS_PROPERTIES)" ]; then
    section "D-Bus properties (session bus)"
    echo "$DBUS_PROPERTIES" | while read -r service object interface property; do
        [ -n "$property" ] || continue
        value=$(busctl --user get-property "$service" "$object" "$interface" "$property" 2>&1)
        printf '  %s.%s = %s\n' "${interface##*.}" "$property" "$value"
    done
fi

section "Screens"
wlr-randr 2>/dev/null | awk '
    /^[^ ]/     { print "  " $1 }
    /Enabled:/  { print "    enabled:  " $2 }
    /current/   { print "    mode:     " $1 " " $2 " " $3 }
    /Position:/ { print "    position: " $2 }
    /Scale:/    { print "    scale:    " $2 }'

section "CPU, memory, graphics"
echo "  $(nproc) CPUs: $(sed -n 's/^model name[[:space:]]*: //p' /proc/cpuinfo | head -1)"
echo "  memory: $(awk '/MemTotal/ {printf "%.1f GB", $2/1048576}' /proc/meminfo)"
lspci 2>/dev/null | grep -iE 'vga|3d|display' | sed 's/^[^ ]* /  /'
