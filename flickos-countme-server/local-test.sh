#!/bin/sh
# local-test.sh: the whole count path on your own computer, no Cloudflare
# account needed.
#
#  1. copies the FlickOS repo's server/countme into a temporary folder
#     (so the repo gets no .wrangler/ state),
#  2. creates the local D1 database from schema.sql,
#  3. starts the Worker with `wrangler dev` on http://127.0.0.1:8787,
#  4. runs check-server.sh against it,
#  5. runs the real flickos-countme client against it (client-run.py),
#  6. shows what the database holds, and stops the Worker.
#
# FLICKOS: the FlickOS checkout (default ~/Documents/Projects/FlickOS).
set -e

HERE=$(cd "$(dirname "$0")" && pwd)
FLICKOS=${FLICKOS:-$HOME/Documents/Projects/FlickOS}
export FLICKOS WRANGLER_SEND_METRICS=false
WORK=$(mktemp -d)
PORT=8787
DEV=

cleanup() {
    # wrangler dev runs in its own process group (setsid), so one kill
    # stops it and the workerd runtime it started.
    if [ -n "$DEV" ]; then
        kill -s TERM -- "-$DEV" 2>/dev/null || true
        wait "$DEV" 2>/dev/null || true
    fi
    rm -rf "$WORK"
}
trap cleanup EXIT INT TERM

echo "== 1. A copy of server/countme in $WORK"
cp -a "$FLICKOS/server/countme" "$WORK/server"

echo "== 2. The local database"
(cd "$WORK/server" && npx wrangler d1 execute flickos-countme --local --file schema.sql >/dev/null)
echo "created from schema.sql"

echo "== 3. The Worker on http://127.0.0.1:$PORT"
(cd "$WORK/server" && exec setsid npx wrangler dev --ip 127.0.0.1 --port "$PORT" >"$WORK/dev.log" 2>&1) &
DEV=$!
tries=0
until curl -s -o /dev/null "http://127.0.0.1:$PORT/"; do
    tries=$((tries + 1))
    if [ "$tries" -gt 60 ]; then
        echo "wrangler dev didn't start; its log:"; cat "$WORK/dev.log"; exit 1
    fi
    sleep 1
done
echo "ready"

echo "== 4. check-server.sh"
COUNTME_DIR="$WORK/server" sh "$HERE/check-server.sh" "http://127.0.0.1:$PORT" --local

echo "== 5. The real client"
CLIENT="$WORK/client"
mkdir -p "$CLIENT/proc" "$CLIENT/state"
printf 'Enabled=yes\nInstalled=%s\nUrl=http://127.0.0.1:%s/v1/countme\n' "$(date -u +%F)" "$PORT" \
    >"$CLIENT/countme.conf"
sed -n 's/^FLICKOS_VERSION=.*/&/p' "$FLICKOS/packages/flickos-branding/usr/lib/flickos-release" \
    >"$CLIENT/flickos-release"
echo "BOOT_IMAGE=/vmlinuz quiet" >"$CLIENT/proc/cmdline"
for command in show "run --dry-run" run run; do
    echo "\$ flickos-countme $command"
    # shellcheck disable=SC2086  # $command is two words on purpose
    python3 "$HERE/client-run.py" "$CLIENT" $command
done

echo "== 6. What the server keeps"
curl -s "http://127.0.0.1:$PORT/v1/stats"
echo
echo "== The Worker's log (note: no addresses, only method, path and status)"
grep 'wrangler:info\] [A-Z]' "$WORK/dev.log" || true
