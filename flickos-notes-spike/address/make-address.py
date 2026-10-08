#!/usr/bin/python3
"""Spikes 1 and 2: make flicknotes:// addresses (design doc section 4).

    ./make-address.py FILE.md [--cursor N]     the address for a note
    ./make-address.py --size 32                 a note whose ADDRESS is ~32 KB
    ./make-address.py --decode ADDRESS          check one (what the phone does)

Send one with:  flickos-phone send "$(./make-address.py --size 32)"
The size notes are random letters, which don't compress, so the address
is the size asked for. The phone app shows the length and whether the
text's sha256 matches: "intact" is the answer to spike 2."""
import argparse
import base64
import datetime
import hashlib
import json
import random
import socket
import string
import sys
import zlib

PREFIX = "flicknotes://continue?v=1&d="


def encode(text, path, cursor):
    data = {
        "v": 1,
        "origin": socket.gethostname(),
        "path": path,
        "modified": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
        "text": text,
        "cursor": cursor,
    }
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
    packed = base64.urlsafe_b64encode(zlib.compress(raw, 9)).rstrip(b"=").decode()
    return PREFIX + packed


def decode(address):
    if not address.startswith(PREFIX):
        sys.exit("not a flicknotes v1 address")
    packed = address[len(PREFIX):]
    raw = zlib.decompress(base64.urlsafe_b64decode(packed + "=" * (-len(packed) % 4)))
    data = json.loads(raw)
    ok = hashlib.sha256(data["text"].encode()).hexdigest() == data["sha256"]
    return data, ok


def sized(kb):
    # base64 makes 4 characters of 3 bytes; zlib can't shrink random letters
    # much (about 6 bits each), so aim the text at the size and trim
    rng = random.Random(kb)
    letters = string.ascii_letters + string.digits
    want = kb * 1024
    n = want
    for _ in range(20):
        text = f"# Size test {kb} KB\n\n" + "".join(rng.choice(letters) for _ in range(n))
        address = encode(text, f"size-{kb}.md", 0)
        if abs(len(address) - want) < 64:
            break
        n = int(n * want / len(address))
    return address


def main():
    p = argparse.ArgumentParser()
    p.add_argument("file", nargs="?")
    p.add_argument("--cursor", type=int, default=0)
    p.add_argument("--size", type=int, metavar="KB")
    p.add_argument("--decode", metavar="ADDRESS")
    a = p.parse_args()
    if a.decode:
        data, ok = decode(a.decode)
        print(json.dumps({k: v for k, v in data.items() if k != "text"}, indent=1))
        print(f"text: {len(data['text'])} characters, {'intact' if ok else 'DAMAGED'}")
        return
    if a.size:
        print(sized(a.size))
        return
    with open(a.file, encoding="utf-8") as f:
        text = f.read()
    print(encode(text, a.file, a.cursor))


main()
