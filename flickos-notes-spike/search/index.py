#!/usr/bin/python3
"""Spike 4: Notes' search index (ADR-003), standard library only.

    ./index.py FOLDER [QUERY…]     index, then time each query
    ./index.py FOLDER --hold       index, then wait (for tools/measure.py)

A query is words and #tags; every one must match. Words match the start of
any word in the note, case and accents folded (cafe finds Café)."""
import os
import re
import sys
import time
import unicodedata

TAG = re.compile(r"#(\w[\w/-]*)")
WORD = re.compile(r"\w+")
ITEM = re.compile(r"^[ \t]*(?:[-*+]|\d+[.)])[ \t]+\[([ xX])\]", re.M)


def fold(text):
    text = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in text if not unicodedata.combining(c))


class Note:
    __slots__ = ("path", "title", "tags", "words", "open_items", "items", "mtime")


def read_note(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    note = Note()
    note.path = path
    first = text.lstrip().split("\n", 1)[0]
    note.title = first.lstrip("#").strip() or os.path.basename(path)[:-3]
    # "#" then a letter, at the start of a line or after a space or "(":
    # checking the character before is 4x faster than a lookbehind
    note.tags = frozenset(fold(m.group(1)) for m in TAG.finditer(text)
                          if not m.group(1)[0].isdigit()
                          and (m.start() == 0 or text[m.start() - 1] in " \t\n("))
    # one string of the note's distinct folded words: a query word is a
    # substring search of " word" in it, so prefixes match
    words = set(WORD.findall(text.casefold()))
    note.words = " " + " ".join(sorted({w if w.isascii() else fold(w) for w in words}))
    ticks = ITEM.findall(text)
    note.items = len(ticks)
    note.open_items = ticks.count(" ")
    note.mtime = os.stat(path).st_mtime
    return note


def index(folder):
    notes = []
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in files:
            if name.endswith(".md") and not name.startswith("."):
                notes.append(read_note(os.path.join(root, name)))
    return notes


def search(notes, query):
    tags, words = [], []
    for part in query.split():
        if part.startswith("#") and len(part) > 1:
            tags.append(fold(part[1:]))
        else:
            words += [" " + w for w in WORD.findall(fold(part))]
    hits = [n for n in notes
            if all(t in n.tags or any(x.startswith(t + "/") for x in n.tags) for t in tags)
            and all(w in n.words for w in words)]
    hits.sort(key=lambda n: -n.mtime)
    return hits


def rss_kb():
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return int(line.split()[1])


def main():
    folder, args = sys.argv[1], sys.argv[2:]
    before = rss_kb()
    t = time.perf_counter()
    notes = index(folder)
    took = time.perf_counter() - t
    print(f"indexed {len(notes)} notes in {took * 1000:.0f} ms, "
          f"RSS {before} → {rss_kb()} KB (+{rss_kb() - before} KB)")
    print(f"checklists: {sum(1 for n in notes if n.items)} notes, "
          f"{sum(n.open_items for n in notes)} open items")
    if args == ["--hold"]:
        input("held; Enter to quit ")
        return
    for q in args:
        t = time.perf_counter()
        hits = search(notes, q)
        ms = (time.perf_counter() - t) * 1000
        print(f"{q!r}: {len(hits)} notes in {ms:.1f} ms; first: {hits[0].title if hits else '-'}")


main()
