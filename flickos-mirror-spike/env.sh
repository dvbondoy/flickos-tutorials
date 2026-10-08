# env.sh: run the unpacked adb and scrcpy from this folder without installing
# them. Load it into your shell first:   . ./env.sh
#
# LD_LIBRARY_PATH  where the dynamic loader looks for libraries before /usr/lib.
#                  adb's own libraries are one folder deeper, in android/, so
#                  try-unpacked.sh's check said "missing" for adb: it didn't
#                  look there.
# PATH             the unpacked adb and scrcpy come first.
# ADB              the adb scrcpy runs (scrcpy starts adb itself).
# SCRCPY_SERVER_PATH  the phone half of scrcpy: Debian's package downloads it
#                  at install time, we downloaded the same file (sha256
#                  checked) into server/.
# PYTHONPATH       the unpacked python3-qrcode, for pair-qr.py.
SPIKE=$(cd "$(dirname "${BASH_SOURCE:-$0}")" 2>/dev/null && pwd)
[ -d "$SPIKE/unpacked" ] || SPIKE=$PWD
LIB=$SPIKE/unpacked/usr/lib/x86_64-linux-gnu
export LD_LIBRARY_PATH=$LIB:$LIB/android
export PATH=$SPIKE/unpacked/usr/bin:$PATH
export ADB=$SPIKE/unpacked/usr/bin/adb
export SCRCPY_SERVER_PATH=$SPIKE/server/scrcpy-server
export PYTHONPATH=$SPIKE/unpacked/usr/lib/python3/dist-packages
echo "adb: $(command -v adb)  scrcpy: $(command -v scrcpy)"
