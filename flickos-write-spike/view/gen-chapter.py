#!/usr/bin/python3
"""Make a long chapter of made-up prose for spike 2.

    ./gen-chapter.py [WORDS] > chapter.md      default 20,000 words

The same words every time (a fixed random seed), so runs compare. It looks
like a novel's chapter: one line per paragraph, dialogue, a few curly quotes
and accents, scene breaks (***), a heading on the first line.
"""
import random
import sys

NOUNS = ("rain boat harbour keeper lamp window door letter road sea cliff "
         "house mother brother morning night storm rope tide village bell "
         "kitchen table chair coat hand face voice light shadow island café "
         "stair garden field wall year week hour minute promise secret").split()
VERBS = ("watched held carried opened closed counted remembered forgot "
         "pulled pushed waited listened answered followed crossed found "
         "lost kept wrote read climbed turned left noticed believed").split()
ADJS = ("old grey quiet cold narrow wet bright small heavy long thin dark "
        "empty patient tired careful distant broken familiar").split()
ADVS = ("slowly again already never quietly suddenly almost still once "
        "carefully").split()
NAMES = ("Mara", "Tomás", "the keeper", "Ana", "her brother", "Old Ruth")
SAID = ("said", "asked", "whispered", "called", "answered")


def sentence(rnd):
    who = rnd.choice(NAMES)
    parts = [who[0].upper() + who[1:], rnd.choice(ADVS) if rnd.random() < .3 else "",
             rnd.choice(VERBS), "the", rnd.choice(ADJS), rnd.choice(NOUNS)]
    if rnd.random() < .5:
        parts += [rnd.choice(("by", "near", "under", "behind", "across")),
                  "the", rnd.choice(NOUNS)]
    if rnd.random() < .3:
        parts += ["and", rnd.choice(VERBS), "it", rnd.choice(ADVS)]
    text = " ".join(p for p in parts if p)
    return text + rnd.choice(".....?!")


def dialogue(rnd):
    line = sentence(rnd)[:-1]
    return f"“{line[0].upper()}{line[1:]},” {rnd.choice(NAMES)} {rnd.choice(SAID)}."


def main():
    want = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
    rnd = random.Random(3)
    out = ["# The Storm", ""]
    words = 2
    while words < want:
        if rnd.random() < .02:
            para = "***"
        elif rnd.random() < .25:
            para = dialogue(rnd)
        else:
            para = " ".join(sentence(rnd) for _ in range(rnd.randint(3, 9)))
        out += [para, ""]
        words += len(para.split())
    sys.stdout.write("\n".join(out))


if __name__ == "__main__":
    main()
