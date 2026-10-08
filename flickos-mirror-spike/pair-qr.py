#!/usr/bin/env python3
"""pair-qr.py: pair a phone for wireless debugging by QR code, the way
Android Studio does, using the unpacked adb (load env.sh first).

    . ./env.sh
    ./pair-qr.py            QR in the terminal and in qr.png, then wait
    ./pair-qr.py --connect-only   skip pairing: find the phone and adb connect
    ./pair-qr.py --code     pair with the phone's six digits instead of a QR
    ./pair-qr.py -v ...     show every mDNS answer while waiting

The computer makes up a service name and a password and shows them as
WIFI:T:ADB;S:NAME;P:PASSWORD;; in a QR code. The phone scans it (Developer
options -> Wireless debugging -> Pair device with QR code) and advertises
_adb-tls-pairing._tcp under that NAME. We find its address and port with
mdns.py, run `adb pair ADDR:PORT PASSWORD`, then find the phone's
_adb-tls-connect._tcp port and run `adb connect`.

Every step prints how long it took. Exit status: 0 connected, 1 failed.
"""
import argparse
import os
import secrets
import subprocess
import sys
import time

import mdns

HERE = os.path.dirname(os.path.abspath(__file__))
ADB = os.environ.get("ADB", "adb")
t0 = time.monotonic()


def say(msg):
    print(f"[{time.monotonic() - t0:6.1f} s] {msg}", flush=True)


def adb(*args, timeout=30):
    r = subprocess.run([ADB, *args], capture_output=True, text=True, timeout=timeout)
    out = (r.stdout + r.stderr).strip()
    say(f"adb {' '.join(args)} -> exit {r.returncode}: {out}")
    return r.returncode, out


def show_qr(text):
    try:
        import qrcode
    except ImportError:
        sys.exit("no qrcode module: load env.sh (it sets PYTHONPATH)")
    # A quiet zone of 4 modules, as the QR standard asks: with 2, a dark
    # terminal or image viewer around the code can stop a strict scanner.
    qr = qrcode.QRCode(border=4, box_size=12)
    qr.add_data(text)
    qr.make()
    qr.print_ascii(invert=True)
    path = os.path.join(HERE, "qr.png")
    qr.make_image().save(path)
    say(f"also saved as {path} (xdg-open it if the terminal one won't scan)")


LOG = None


def seen_pairing(found):
    for k, v in found.items():
        addr = (v["addrs"] or [v["from"]])[0]
        say(f"  pairing service seen: {k} at {addr}:{v['port']}")


def pair_code(seconds):
    say("on the phone: Wireless debugging -> Pair device with pairing code")
    say(f"looking up to {seconds} s for its _adb-tls-pairing._tcp")
    found = mdns.browse([mdns.SHORT["pair"]], listen=True, seconds=seconds, log=LOG,
                        want=lambda f: any(v["port"] for v in f.values()))
    seen_pairing(found)
    services = [v for v in found.values() if v["port"]]
    if not services:
        say("no pairing service seen (Q13: no), type `adb pair IP:PORT CODE` by hand")
        return False
    info = services[0]
    addr = (info["addrs"] or [info["from"]])[0]
    code = input(f"six digits shown on the phone for {addr}:{info['port']}: ").strip()
    code_rc, out = adb("pair", f"{addr}:{info['port']}", code)
    return code_rc == 0 and "Successfully paired" in out


def pair(seconds):
    name = "flickos-" + secrets.token_hex(3)
    password = secrets.token_hex(6)
    show_qr(f"WIFI:T:ADB;S:{name};P:{password};;")
    say(f"waiting up to {seconds} s for the phone to scan it (service {name})")
    found = mdns.browse([mdns.SHORT["pair"]], listen=True, seconds=seconds, log=LOG,
                        want=lambda f: any(k.split(".")[0] == name for k in f))
    seen_pairing(found)
    match = [(k, v) for k, v in found.items() if k.split(".")[0] == name]
    if not match:
        say(f"no pairing service named {name}; seen: {list(found) or 'none'}")
        return False
    info = match[0][1]
    addr = (info["addrs"] or [info["from"]])[0]
    say(f"phone's pairing service: {addr}:{info['port']}")
    code, out = adb("pair", f"{addr}:{info['port']}", password)
    return code == 0 and "Successfully paired" in out


def connect(seconds):
    say("looking for the phone's _adb-tls-connect._tcp")
    found = mdns.browse([mdns.SHORT["connect"]], listen=True, seconds=seconds,
                        want=lambda f: any(v["port"] for v in f.values()))
    for name, info in found.items():
        if not info["port"]:
            continue
        addr = (info["addrs"] or [info["from"]])[0]
        say(f"{name} at {addr}:{info['port']}")
        code, out = adb("connect", f"{addr}:{info['port']}")
        if code == 0 and "connected to" in out and "failed" not in out:
            adb("devices", "-l")
            return True
    say("no connect service found (is Wireless debugging on?)")
    return False


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--connect-only", action="store_true")
    p.add_argument("--code", action="store_true", help="pair with the phone's six digits")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--seconds", type=int, default=120, help="how long to wait for the scan")
    a = p.parse_args()
    global LOG
    if a.verbose:
        LOG = lambda m: say(f"  [{m}]")
    adb("start-server")
    pairing = pair_code if a.code else pair
    if not a.connect_only and not pairing(a.seconds):
        return 1
    return 0 if connect(10) else 1


if __name__ == "__main__":
    sys.exit(main())
