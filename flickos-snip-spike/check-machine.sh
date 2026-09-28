#!/bin/sh
# check-machine.sh: what this computer and its compositor can do for
# screenshots and recording. It only reads; it changes nothing.
#
#   ./check-machine.sh            print everything
#   ./check-machine.sh > machine.txt   keep a copy for the results

section() { printf '\n== %s\n' "$1"; }
yesno() { if "$@" >/dev/null 2>&1; then echo yes; else echo no; fi; }

section "Packages (installed version, or 'no')"
for p in labwc grim slurp wl-clipboard libnotify-bin swappy wf-recorder \
         xdg-desktop-portal xdg-desktop-portal-wlr pipewire-pulse wireplumber \
         gstreamer1.0-pipewire gstreamer1.0-tools gstreamer1.0-plugins-good vlc; do
    v=$(dpkg-query -W -f='${Status} ${Version}' "$p" 2>/dev/null | sed -n 's/^install ok installed //p')
    printf '  %-26s %s\n' "$p" "${v:-no}"
done

section "Screens (wlr-randr)"
wlr-randr | awk '
    /^[^ ]/     { print "  " $1 }
    /Enabled:/  { print "    enabled:  " $2 }
    /current/   { print "    mode:     " $1 " " $2 " " $3 }
    /Position:/ { print "    position: " $2 }
    /Scale:/    { print "    scale:    " $2 }'

section "Capture protocols the compositor offers (wayland-info)"
protocols=$(wayland-info 2>/dev/null | grep -oE "interface: '[a-z0-9_]+'" | cut -d"'" -f2)
for i in zwlr_screencopy_manager_v1 ext_image_copy_capture_manager_v1 \
         ext_output_image_capture_source_manager_v1 \
         ext_foreign_toplevel_image_capture_source_manager_v1 \
         ext_foreign_toplevel_list_v1 zwlr_foreign_toplevel_manager_v1; do
    printf '  %-54s %s\n' "$i" "$(yesno sh -c "echo '$protocols' | grep -qx $i")"
done

section "Can grim capture one window? (needs 'grim -T')"
printf '  grim -T: %s\n' "$(yesno sh -c "grim -h 2>&1 | grep -q -- '-T '")"

section "Screen-cast portal (busctl)"
get() {
    busctl --user get-property org.freedesktop.portal.Desktop \
        /org/freedesktop/portal/desktop org.freedesktop.portal.ScreenCast "$1" 2>/dev/null | cut -d' ' -f2
}
types=$(get AvailableSourceTypes)
cursor=$(get AvailableCursorModes)
if [ -z "$types" ]; then
    echo "  no answer: is xdg-desktop-portal running?"
else
    echo "  AvailableSourceTypes = $types (1 screens, 2 windows, 4 virtual)"
    echo "    screens: $([ $((types & 1)) -ne 0 ] && echo yes || echo no)"
    echo "    windows: $([ $((types & 2)) -ne 0 ] && echo yes || echo no)"
    echo "  AvailableCursorModes = $cursor (1 hidden, 2 drawn in, 4 as metadata)"
fi

section "Sound (wpctl)"
node() { wpctl inspect "$1" 2>/dev/null | sed -n 's/.*node\.name = "\(.*\)"/\1/p'; }
sink=$(node @DEFAULT_AUDIO_SINK@)
mic=$(node @DEFAULT_AUDIO_SOURCE@)
echo "  speakers:           ${sink:-none}"
echo "  desktop sound from: ${sink:+$sink.monitor}"
echo "  microphone:         ${mic:-none}"

section "CPU, memory, video encoding hardware"
echo "  $(nproc) CPUs: $(sed -n 's/^model name[[:space:]]*: //p' /proc/cpuinfo | head -1)"
echo "  memory: $(awk '/MemTotal/ {printf "%.1f GB", $2/1048576}' /proc/meminfo)"
echo "  render nodes: $(echo $(ls /dev/dri/renderD* 2>/dev/null) | grep . || echo none)"
printf '  VA-API driver installed: '
if ls /usr/lib/x86_64-linux-gnu/dri/*_drv_video.so >/dev/null 2>&1; then
    ls /usr/lib/x86_64-linux-gnu/dri/*_drv_video.so | xargs -n1 basename | tr '\n' ' '; echo
else
    echo no
fi

section "Print keys labwc has now"
for f in "$XDG_RUNTIME_DIR/flickos/xdg/labwc/rc.xml" "$HOME/.config/labwc/rc.xml" /etc/xdg/labwc/rc.xml; do
    if [ -f "$f" ]; then
        echo "  from $f"
        grep -o 'key="[^"]*Print"' "$f" | sed 's/^/    /'
        break
    fi
done
