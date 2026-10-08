#!/bin/bash
# Close every test window, load cfg/labwc/rc.xml and open new windows:
# ./fresh.sh a:#ff0000 b:#00ff00 …   (NAME:COLOR, see win.py)
cd "$(dirname "$0")"
for p in $(./headless.sh pid win.py); do kill "$p"; done
sleep 0.3
./headless.sh reload
sleep 0.3
for w in "$@"; do
    ./headless.sh run ./win.py "${w%%:*}" "${w#*:}" > "logs/win-${w%%:*}.log" 2>&1 &
done
sleep 1.5
echo "windows: $(./headless.sh pid win.py | wc -l)"
