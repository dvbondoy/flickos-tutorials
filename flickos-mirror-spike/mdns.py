#!/usr/bin/env python3
"""mdns.py: find a phone's services with mDNS, stdlib only.

Debian's adb is built without mDNS (its adb.mk replaces adb_mdns.cpp with
stubs), so `adb mdns services` lists nothing and QR pairing can't find the
phone. This asks the network directly, the way adb would have.

    ./mdns.py pair                       multicast, answers to our own port
    ./mdns.py --to 192.168.88.172 pair   ask only the phone (unicast)
    ./mdns.py --listen connect           real mDNS: from port 5353, answers to the group
    ./mdns.py kdeconnect                 the control: KDE Connect's own service

Names: pair = _adb-tls-pairing._tcp (shown while the phone's "Pair device"
screen is open), connect = _adb-tls-connect._tcp (while Wireless debugging is
on), kdeconnect = _kdeconnect._udp. Any other name is used as it is.

Exit status: 0 something found, 1 nothing found, 2 bad arguments.
"""
import argparse
import socket
import struct
import sys
import time

GROUP = "224.0.0.251"
PORT = 5353
SHORT = {
    "pair": "_adb-tls-pairing._tcp.local",
    "connect": "_adb-tls-connect._tcp.local",
    "kdeconnect": "_kdeconnect._udp.local",
}
A, PTR, TXT, AAAA, SRV = 1, 12, 16, 28, 33


def encode_name(name):
    out = b""
    for label in name.rstrip(".").split("."):
        raw = label.encode()
        out += bytes([len(raw)]) + raw
    return out + b"\0"


def query(types, unicast_bit):
    """One DNS message asking for the PTR records of every type."""
    # id 0, flags 0 (a standard query), len(types) questions, no answers.
    msg = struct.pack("!6H", 0, 0, len(types), 0, 0, 0)
    qclass = 1 | (0x8000 if unicast_bit else 0)   # IN, with the QU bit
    for t in types:
        msg += encode_name(t) + struct.pack("!2H", PTR, qclass)
    return msg


def read_name(data, pos):
    """A DNS name at pos, following compression pointers. -> (name, next pos)"""
    labels, end, jumps = [], None, 0
    while True:
        n = data[pos]
        if n == 0:
            pos += 1
            break
        if n & 0xC0 == 0xC0:                       # pointer to an earlier name
            if end is None:
                end = pos + 2
            pos = ((n & 0x3F) << 8) | data[pos + 1]
            jumps += 1
            if jumps > 20:
                raise ValueError("pointer loop")
            continue
        labels.append(data[pos + 1:pos + 1 + n].decode(errors="replace"))
        pos += 1 + n
    return ".".join(labels), (end if end is not None else pos)


def records(data):
    """Every answer, authority and additional record: (name, type, value)."""
    _, flags, qd, an, ns, ar = struct.unpack("!6H", data[:12])
    if not flags & 0x8000:                         # a query, not an answer
        return []
    pos = 12
    for _ in range(qd):
        _, pos = read_name(data, pos)
        pos += 4
    out = []
    for _ in range(an + ns + ar):
        name, pos = read_name(data, pos)
        rtype, _, _, length = struct.unpack("!2HIH", data[pos:pos + 10])
        pos += 10
        rdata = data[pos:pos + length]
        if rtype == PTR:
            value = read_name(data, pos)[0]
        elif rtype == SRV:
            _, _, port = struct.unpack("!3H", rdata[:6])
            value = (port, read_name(data, pos + 6)[0])
        elif rtype == A:
            value = socket.inet_ntoa(rdata)
        elif rtype == AAAA:
            value = socket.inet_ntop(socket.AF_INET6, rdata)
        elif rtype == TXT:
            items, i = [], 0
            while i < len(rdata):
                items.append(rdata[i + 1:i + 1 + rdata[i]].decode(errors="replace"))
                i += 1 + rdata[i]
            value = items
        else:
            value = None
        out.append((name, rtype, value))
        pos += length
    return out


def open_socket(listen):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    if listen:
        # Real mDNS: send from 5353 and hear the group. A responder then
        # answers by multicast, which ufw's before.rules let in.
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        s.bind(("", PORT))
        mreq = socket.inet_aton(GROUP) + socket.inet_aton("0.0.0.0")
        s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    else:
        # A "one-shot" query from any port (RFC 6762 6.7): the responder
        # answers by unicast straight to this port.
        s.bind(("", 0))
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
    return s


def browse(types, to=None, seconds=3.0, listen=False, unicast_bit=False,
           want=None, log=None):
    """Ask for types until seconds pass (or want(found) is true).

    -> {instance: {"type", "port", "host", "addrs", "txt", "from"}}
    """
    s = open_socket(listen)
    dest = (to or GROUP, PORT)
    msg = query(types, unicast_bit)
    found, hosts = {}, {}
    start = time.monotonic()
    next_send = start
    try:
        while True:
            now = time.monotonic()
            if now - start >= seconds:
                break
            if now >= next_send:
                s.sendto(msg, dest)
                next_send = now + 1.0
            s.settimeout(max(0.05, min(next_send, start + seconds) - now))
            try:
                data, src = s.recvfrom(9000)
            except socket.timeout:
                continue
            try:
                recs = records(data)
            except (ValueError, IndexError, struct.error) as e:
                if log:
                    log(f"bad packet from {src[0]}: {e}")
                continue
            if log and recs:
                log(f"{len(recs)} records from {src[0]}:{src[1]}")
                kinds = {A: "A", PTR: "PTR", TXT: "TXT", AAAA: "AAAA", SRV: "SRV"}
                for name, rtype, value in recs:
                    log(f"    {kinds.get(rtype, rtype)} {name} -> {value}")
            for name, rtype, value in recs:
                if rtype == PTR and name.lower() in (t.lower() for t in types):
                    found.setdefault(value, {"type": name, "port": None,
                                             "host": None, "addrs": [],
                                             "txt": [], "from": src[0]})
            for name, rtype, value in recs:
                if rtype in (A, AAAA):
                    hosts.setdefault(name.lower(), set()).add(value)
                elif name in found and rtype == SRV:
                    found[name]["port"], found[name]["host"] = value
                elif name in found and rtype == TXT:
                    found[name]["txt"] = value
            for info in found.values():
                if info["host"]:
                    info["addrs"] = sorted(hosts.get(info["host"].lower(), ()))
            if want and want(found):
                break
    finally:
        s.close()
    return found


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("types", nargs="+", help="pair, connect, kdeconnect or a full name")
    p.add_argument("--to", help="ask only this address (unicast)")
    p.add_argument("--listen", action="store_true",
                   help="send from port 5353 and hear the group (real mDNS)")
    p.add_argument("--qu", action="store_true", help="set the unicast-response bit")
    p.add_argument("--seconds", type=float, default=3.0)
    p.add_argument("-v", "--verbose", action="store_true")
    a = p.parse_args()
    types = [SHORT.get(t, t) for t in a.types]
    log = (lambda m: print(f"  [{m}]", file=sys.stderr)) if a.verbose else None
    try:
        found = browse(types, a.to, a.seconds, a.listen, a.qu, log=log)
    except OSError as e:
        print(f"mdns.py: {e}", file=sys.stderr)
        return 2
    mode = f"unicast to {a.to}" if a.to else ("from 5353" if a.listen else "one-shot multicast")
    print(f"{len(found)} found in {a.seconds:g} s ({mode})")
    for name, info in sorted(found.items()):
        addr = (info["addrs"] or [info["from"]])[0]
        print(f"  {name}\n    {addr}:{info['port']}  host {info['host']}  txt {info['txt']}")
    return 0 if found else 1


if __name__ == "__main__":
    sys.exit(main())
