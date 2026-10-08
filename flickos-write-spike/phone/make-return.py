#!/usr/bin/python3
"""Spike 1: make flickwrite://return addresses (design doc section 4).

    ./make-return.py --size 32 [--out FILE]      an address of ~32 KB, phone → computer
    ./make-return.py --decode ADDRESS|@FILE      check one (what the computer will do)

The text is random letters, which don't compress, so the address is about
the size asked for. "intact" means the text's sha256 matches the one inside.
"""
import argparse
import base64
import hashlib
import json
import random
import string
import sys
import zlib

PREFIX = "flickwrite://return?v=1&d="


def encode(text, cursor=0):
    data = {
        "v": 1,
        "origin": "jon-x555ld",
        "from": "HMD CREST",
        "ref": base64.urlsafe_b64encode(random.Random(1).randbytes(16)).rstrip(b"=").decode(),
        "path": "Spike/01 Size test.md",
        "base": hashlib.sha256(b"").hexdigest(),
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
        "text": text,
        "cursor": cursor,
    }
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
    return PREFIX + base64.urlsafe_b64encode(zlib.compress(raw, 9)).rstrip(b"=").decode()


def decode(address):
    address = address.strip()
    if not address.startswith(PREFIX):
        sys.exit(f"not a flickwrite return v1 address: {address[:60]!r}")
    packed = address[len(PREFIX):]
    raw = zlib.decompress(base64.urlsafe_b64decode(packed + "=" * (-len(packed) % 4)))
    data = json.loads(raw)
    return data, hashlib.sha256(data["text"].encode()).hexdigest() == data["sha256"]


def sized(kb):
    rng = random.Random(kb)
    letters = string.ascii_letters + string.digits
    want = kb * 1024 - 64            # a little under: the size is a ceiling
    n = want
    for _ in range(20):
        text = f"# Size test {kb} KB\n\n" + "".join(rng.choice(letters) for _ in range(n))
        address = encode(text)
        if want - 64 < len(address) <= want:
            break
        n = int(n * want / len(address))
    return address


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--size", type=int, metavar="KB")
    p.add_argument("--out")
    p.add_argument("--decode", metavar="ADDRESS|@FILE")
    a = p.parse_args()
    if a.decode:
        address = open(a.decode[1:]).read() if a.decode.startswith("@") else a.decode
        data, ok = decode(address)
        print(json.dumps({k: v for k, v in data.items() if k != "text"}, indent=1))
        print(f"address {len(address.strip()):,} characters; text {len(data['text']):,} characters,"
              f" {'intact' if ok else 'DAMAGED'}")
        return
    address = sized(a.size)
    if a.out:
        with open(a.out, "w") as f:
            f.write(address)
        print(f"{a.out}: {len(address):,} characters")
    else:
        print(address)


if __name__ == "__main__":
    main()
