#!/usr/bin/python3
"""Make test/fixtures/addresses.json with the computer's own encoder and parser.

    tool/make-fixtures.py [PATH/TO/flickos-notes]   (default: ../flickos-notes/usr/bin/flickos-notes)

The address format (FlickOS's docs/design/flickos-notes.md, section 4) is the
contract between the two apps, so the phone's tests decode what the
computer's make_address() makes. Run it again when the format changes."""
import base64
import importlib.machinery
import importlib.util
import json
import os
import sys
import zlib

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROGRAM = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "flickos-notes", "usr", "bin", "flickos-notes")
sys.dont_write_bytecode = True
loader = importlib.machinery.SourceFileLoader("flickos_notes", PROGRAM)
notes = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
loader.exec_module(notes)


def packed(obj):
    raw = json.dumps(obj, ensure_ascii=False).encode()
    return notes.ADDRESS_PREFIX + base64.urlsafe_b64encode(zlib.compress(raw)).rstrip(b"=").decode()


groceries = "# Groceries 🍰\n#home\n\n- [ ] milk\n- [x] bread\n"
good = notes.make_address(groceries, "Home/Groceries.md", "2026-10-02T10:15:00+0800", 16, "jon-x555ld")
data = json.loads(zlib.decompress(base64.urlsafe_b64decode(good[len(notes.ADDRESS_PREFIX):] + "==")))
cases = [
    {"name": "a note, cursor after an emoji", "address": good,
     "expect": {"origin": "jon-x555ld", "path": "Home/Groceries.md", "modified": "2026-10-02T10:15:00+0800",
                "text": groceries, "sha256": data["sha256"],
                # 16 code points: "# Groceries 🍰\n#h" ends at "#h", 17 UTF-16 units
                "cursor": 17}},
    {"name": "cursor past the end is clamped",
     "address": notes.make_address("ab", "x.md", "2026-10-02T10:15:00+0800", 99, "pc"),
     "expect": {"text": "ab", "cursor": 2}},
    {"name": "empty note", "address": notes.make_address("", "Empty.md", "2026-10-02T10:15:00+0800", 0, "pc"),
     "expect": {"text": "", "cursor": 0}},
    {"name": "text changed on the way", "address": packed({**data, "text": groceries + "x"}), "error": "damaged"},
    {"name": "a newer address", "address": good.replace("v=1&", "v=2&"), "error": "update"},
    {"name": "a newer JSON", "address": packed({**data, "v": 2}), "error": "update"},
    {"name": "not base64", "address": notes.ADDRESS_PREFIX + "!!!", "error": "damaged"},
    {"name": "not zlib", "address": notes.ADDRESS_PREFIX + base64.urlsafe_b64encode(b"hello").decode(),
     "error": "damaged"},
    {"name": "not an object", "address": packed([1, 2]), "error": "damaged"},
    {"name": "a field missing", "address": packed({k: v for k, v in data.items() if k != "origin"}),
     "error": "damaged"},
    {"name": "unpacks to too much", "address": notes.ADDRESS_PREFIX + base64.urlsafe_b64encode(
        zlib.compress(json.dumps({**data, "text": "a" * 5_000_000}).encode(), 9)).rstrip(b"=").decode(),
     "error": "too long"},
    {"name": "another scheme", "address": "https://example.com/?v=1&d=x", "error": "not a note"},
    {"name": "another host", "address": "flicknotes://open?v=1&d=x", "error": "not a note"},
]
# What the computer makes of these texts: the phone must say the same.
texts = [
    "# Groceries\nmilk", "\n\n  Plan for **Monday**  \n", "### See [the shop](https://x.y)", "",
    "#home #errands\nmilk",
    "---\ntags: [work, 'project/flickos']\ntitle: x\n---\n# Plan\nFirst #idea\n",
    "---\naliases: []\ntags:\n  - Work\n  - \"#home\"\nother: 1\n---\nText",
    "---\ntags: a b, c\n---\n",
    "x #one (#two) a#three page.html#top # Heading ##four\n#5five #_six\n#Seven-8/sub",
    "Run `grep #nope` here #yes\n```\n#not-a-tag\n```\n~~~sh\n#nor\n~~~\nafter #also",
    "#before\n```\n#inside",
    "#Café #WORK #Ünïcode",
    "- [ ] milk\n- [x] bread\n  * [X] nested\n3. [ ] numbered\n- [] no\n-[ ] no\n```\n- [ ] code\n```",
    "# Plan\r\n- [ ] one #x\r\n",
]
parses = []
for text in texts:
    title, tags, _words, items, left = notes.parse(text)
    parses.append({"text": text, "title": title, "tags": sorted(tags), "items": items, "left": left})

out = os.path.join(HERE, "test", "fixtures", "addresses.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump({"made_by": "tool/make-fixtures.py", "cases": cases, "parse": parses}, f, ensure_ascii=False, indent=1)
    f.write("\n")
print(f"{out}: {len(cases)} addresses, {len(parses)} texts")
