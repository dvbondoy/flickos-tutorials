#!/bin/sh
# serve.sh: give the live VM this folder's setup-live.sh and calamares/ configs.
# Listens only on 127.0.0.1; QEMU's user network shows it to the VM as
# 10.0.2.2:8000 and to nobody else. Stop it with Ctrl+C.
cd "$(dirname "$0")"
echo "serving $(pwd) on http://127.0.0.1:8000 (the VM: http://10.0.2.2:8000). Ctrl+C stops."
exec python3 -m http.server 8000 --bind 127.0.0.1
