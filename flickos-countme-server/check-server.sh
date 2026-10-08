#!/bin/sh
# check-server.sh BASE [--local]
#
# Checks a FlickOS count server (server/countme) from the outside, the way a
# FlickOS computer sees it. BASE is the Worker's address without a path, e.g.
#   https://flickos-countme.ACCOUNT.workers.dev   (the deployed one)
#   http://127.0.0.1:8787 --local                 (wrangler dev)
#
# It sends one real count with the made-up version 0.0, checks that /v1/stats
# shows it, and deletes it again with wrangler (--remote unless --local), so
# the real numbers are left as they were. Everything else it sends is refused
# by the Worker and stores nothing.
#
# COUNTME_DIR: the folder with wrangler.toml (default: the FlickOS repo's).
set -e

BASE=${1:?usage: check-server.sh BASE [--local]}
BASE=${BASE%/}
WHERE=--remote
[ "$2" = --local ] && WHERE=--local
FLICKOS=${FLICKOS:-$HOME/Documents/Projects/FlickOS}
COUNTME_DIR=${COUNTME_DIR:-$FLICKOS/server/countme}
export WRANGLER_SEND_METRICS=false
failed=0

# expect CODE METHOD PATH: one request, compare the HTTP status.
expect() {
    code=$(curl -s -o /dev/null -w '%{http_code}' -X "$2" "$BASE$3")
    if [ "$code" = "$1" ]; then
        echo "ok    $2 $3 -> $code"
    else
        echo "FAIL  $2 $3 -> $code (wanted $1)"
        failed=1
    fi
}

echo "== Requests that must be refused (nothing is stored)"
expect 404 GET  /
expect 405 POST /v1/countme
expect 400 GET  "/v1/countme?version=2.0&age=9"
expect 400 GET  "/v1/countme?version=2.0&age=1&id=abc"
expect 400 GET  "/v1/countme?version=latest&age=1"

echo "== One test count (version 0.0)"
expect 200 GET "/v1/countme?version=0.0&age=1"
if curl -s "$BASE/v1/stats" | grep -q '"version":"0.0"'; then
    echo "ok    /v1/stats shows it"
else
    echo "FAIL  /v1/stats doesn't show version 0.0"
    failed=1
fi

echo "== Deleting the test count ($WHERE)"
(cd "$COUNTME_DIR" && npx wrangler d1 execute flickos-countme "$WHERE" \
    --command "DELETE FROM counts WHERE version = '0.0'" >/dev/null)
if curl -s "$BASE/v1/stats" | grep -q '"version":"0.0"'; then
    echo "FAIL  version 0.0 is still there"
    failed=1
else
    echo "ok    gone again"
fi

[ "$failed" = 0 ] && echo "All checks passed." || echo "Some checks FAILED."
exit "$failed"
