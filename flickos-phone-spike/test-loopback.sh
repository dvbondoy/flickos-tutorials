#!/bin/sh
# Test phone-spike.py against fake-phone.py on 127.0.0.1: no phone, no LAN,
# no firewall change. The spike gets a throwaway identity in a temp folder,
# so the real one in phone-state/ (paired with the phone) isn't touched.
set -e
cd "$(dirname "$0")"
dir=$(mktemp -d)

# The spike reads commands from stdin: answer the pair request with "y",
# then print its memory and quit.
( sleep 2; echo y; sleep 3; echo mem; echo quit ) |
    python3 phone-spike.py --local --dir "$dir" &

while [ ! -s "$dir/port" ]; do sleep 0.1; done
python3 fake-phone.py --port "$(cat "$dir/port")" \
    --target "$(cat "$dir/phone-state/device_id")"
wait

echo
echo "Received by the spike:"
ls -l "$dir/received"
rm -rf "$dir"
