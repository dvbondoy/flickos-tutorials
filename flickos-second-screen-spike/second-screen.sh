#!/bin/bash
# The phone or tablet as a second screen, by hand, on your own FlickOS
# session (spike only: nothing here is how the product will do it).
#
#   ./second-screen.sh on [WIDTHxHEIGHT] [--send [--to ID]] [--view-only]
#   ./second-screen.sh status
#   ./second-screen.sh off
#   ./second-screen.sh cleanup        off + remove the spike's add-on
#
# on:  1. puts an add-on with two keys into ~/.config/flickos/addons/
#         (XF86Launch8 adds the screen, XF86Launch9 removes it) and runs
#         `flickos-layout reconfigure` (only the first time)
#      2. presses XF86Launch8 with wtype (a virtual keyboard): labwc runs
#         VirtualOutputAdd and a screen called HEADLESS-PHONE appears
#      3. gives it the size asked for (default 1280x800) and puts it right
#         of your other screens
#      4. starts wayvnc on it only, with TLS and a new password each time
#      5. prints the vnc:// link for AVNC (--send: sends it to the phone
#         with flickos-phone, so a tap opens AVNC)
# off: stops wayvnc FIRST, then presses XF86Launch9. The other order shows
#      your main screen to the phone (wayvnc switches to the screen before)
#      and crashes wayvnc 0.9.1 (found in the headless test).
set -eu

SPIKE=$(cd "$(dirname "$0")" && pwd)
NAME=HEADLESS-PHONE                 # wayvnc resizes only HEADLESS-* screens
ADDON=$HOME/.config/flickos/addons/second-screen-spike
LIVE=$SPIKE/live                    # cert, key, config, pid, log
PORT=5900
CTL=$XDG_RUNTIME_DIR/second-screen-spike.wayvncctl
mkdir -p "$LIVE" "$SPIKE/logs"

say() { printf '%s  %s\n' "$(date +%T)" "$*"; }

has_screen() { wlr-randr --json | python3 -c "
import json, sys
sys.exit(0 if any(s['name'] == '$NAME' for s in json.load(sys.stdin)) else 1)"; }

wayvnc_pid() {
    # Only the wayvnc this script started: its PID file and its command line.
    [ -f "$LIVE/wayvnc.pid" ] || return 1
    pid=$(cat "$LIVE/wayvnc.pid")
    tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null | grep -q "^wayvnc .*$LIVE/config" || return 1
    echo "$pid"
}

install_addon() {
    [ -f "$ADDON/labwc.xml" ] && return
    mkdir -p "$ADDON"
    cat > "$ADDON/labwc.xml" <<EOF
<labwc_config>
  <keyboard>
    <keybind key="XF86Launch8"><action name="VirtualOutputAdd" output_name="$NAME"/></keybind>
    <keybind key="XF86Launch9"><action name="VirtualOutputRemove" output_name="$NAME"/></keybind>
  </keyboard>
</labwc_config>
EOF
    say "add-on written to $ADDON; flickos-layout reconfigure"
    flickos-layout reconfigure
    sleep 0.5
}

make_cert() {
    # One certificate per computer: AVNC asks "trust this certificate?" once.
    [ -f "$LIVE/tls_cert.pem" ] && return
    ( umask 077; openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes \
        -keyout "$LIVE/tls_key.pem" -out "$LIVE/tls_cert.pem" -days 3650 \
        -subj "/CN=$(hostname) second screen" 2>/dev/null )
    say "certificate made: $LIVE/tls_cert.pem"
}

place_right() {
    # x = right edge of the rightmost other screen that is on.
    wlr-randr --json | python3 -c "
import json, sys
right = 0
for s in json.load(sys.stdin):
    if s['name'] != '$NAME' and s.get('enabled') and s.get('position'):
        mode = next((m for m in s['modes'] if m.get('current')), None)
        if mode:
            w = mode['width'] / (s.get('scale') or 1)
            if s.get('transform') in ('90', '270', 'flipped-90', 'flipped-270'):
                w = mode['height'] / (s.get('scale') or 1)
            right = max(right, s['position']['x'] + int(w))
print(right)"
}

lan_address() { ip -4 route get 1.1.1.1 2>/dev/null | sed -n 's/.* src \([0-9.]*\).*/\1/p'; }

cmd_on() {
    size=1280x800 send=no input="" to=""
    while [ $# -gt 0 ]; do
        arg=$1; shift
        case $arg in
            --send) send=yes ;;
            --to) to=$1; shift ;;
            --view-only) input=--disable-input ;;
            *x*) size=$arg ;;
            *) echo "unknown: $arg" >&2; exit 2 ;;
        esac
    done
    if wayvnc_pid >/dev/null; then echo "already on (./second-screen.sh status)"; exit 1; fi
    install_addon
    make_cert
    start=$(date +%s%N)
    wtype -k XF86Launch8
    for _ in $(seq 20); do has_screen && break; sleep 0.1; done
    has_screen || { say "no $NAME after XF86Launch8 (is the add-on merged? flickos-layout addons)"; exit 1; }
    say "$NAME added in $(( ($(date +%s%N) - start) / 1000000 )) ms"
    wlr-randr --output "$NAME" --custom-mode "$size" --pos "$(place_right),0"
    say "$NAME: $size at x=$(place_right)… (wlr-randr shows it)"
    password=$(python3 -c "import secrets; print(secrets.token_urlsafe(12))")
    ( umask 077; cat > "$LIVE/config" <<EOF
use_relative_paths=true
address=0.0.0.0
port=$PORT
enable_auth=true
username=phone
password=$password
private_key_file=tls_key.pem
certificate_file=tls_cert.pem
EOF
    )
    setsid wayvnc $input -C "$LIVE/config" -o "$NAME" -S "$CTL" \
        > "$SPIKE/logs/wayvnc-live.log" 2>&1 < /dev/null &
    echo $! > "$LIVE/wayvnc.pid"
    sleep 1
    wayvnc_pid >/dev/null || { say "wayvnc didn't start:"; cat "$SPIKE/logs/wayvnc-live.log"; wtype -k XF86Launch9; exit 1; }
    ip=$(lan_address)
    pin=$(openssl x509 -in "$LIVE/tls_cert.pem" -outform der | sha256sum | cut -c1-64)
    url="vnc://$ip:$PORT?ConnectionName=FlickOS%20Second%20Screen&SaveConnection=true&SecurityType=19&VncUsername=phone&VncPassword=$password"
    echo "$url" > "$LIVE/url"
    say "wayvnc $(cat "$LIVE/wayvnc.pid") on $ip:$PORT ${input:+(view only)}"
    echo
    echo "  AVNC link:   $url"
    echo "  certificate: sha256 $pin"
    echo "  by hand:     address $ip, port $PORT, security VeNCrypt, user phone, password $password"
    echo
    if [ $send = yes ]; then
        flickos-phone send ${to:+--to "$to"} "$url" && say "link sent to the phone (tap the notification)"
    fi
}

cmd_off() {
    if pid=$(wayvnc_pid); then
        kill "$pid"
        for _ in $(seq 30); do kill -0 "$pid" 2>/dev/null || break; sleep 0.1; done
        say "wayvnc $pid stopped"
    fi
    rm -f "$LIVE/wayvnc.pid" "$LIVE/url"
    if has_screen; then
        wtype -k XF86Launch9
        sleep 0.3
        has_screen && say "$NAME is still there!" || say "$NAME removed"
    fi
}

cmd_status() {
    wlr-randr | sed -n "/^$NAME/,/Adaptive/p" | grep -E "^$NAME|current|Position|Enabled" || echo "no $NAME"
    if pid=$(wayvnc_pid); then
        echo "wayvnc $pid; clients:"; wayvncctl -S "$CTL" client-list 2>&1 | sed 's/^/  /'
    else
        echo "wayvnc not running"
    fi
}

cmd_cleanup() {
    cmd_off
    if [ -d "$ADDON" ]; then
        rm -r "$ADDON"
        flickos-layout reconfigure
        say "add-on removed, labwc reconfigured"
    fi
    echo "If you opened the port: sudo ufw delete allow from 192.168.0.0/16 to any port $PORT proto tcp"
}

case "${1:-}" in
    on) shift; cmd_on "$@" ;;
    off) cmd_off ;;
    status) cmd_status ;;
    cleanup) cmd_cleanup ;;
    *) sed -n '2,10p' "$0"; exit 2 ;;
esac
