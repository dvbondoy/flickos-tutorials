#!/usr/bin/python3
"""Make N fake notes (default 5,000) in ./notes for the search spike.

Same seed every time, so runs compare. Sizes follow a long tail: most notes
are short, a few are long, like a real notes folder."""
import os
import random
import sys

N = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notes")
WORDS = ("plan meeting milk bread eggs café résumé naïve Ñandú garden phone "
         "laptop budget invoice school recipe chicken adobo sinigang travel "
         "Manila Cebu flight hotel doctor appointment birthday gift book "
         "chapter idea project release package debian labwc waybar panel "
         "kernel backup photo video music guitar run walk weekend monday "
         "tuesday call email bank rent electricity water internet").split()
TAGS = ["work", "home", "errands", "ideas", "project/flickos", "travel",
        "money", "health", "school", "recipes"]


def main():
    rng = random.Random(42)
    os.makedirs(os.path.join(OUT, "Work"), exist_ok=True)
    os.makedirs(os.path.join(OUT, ".obsidian"), exist_ok=True)
    total = 0
    for n in range(N):
        title = " ".join(rng.choice(WORDS) for _ in range(rng.randint(1, 4))).capitalize()
        lines = [f"# {title} {n}", " ".join("#" + t for t in rng.sample(TAGS, rng.randint(0, 3)))]
        paragraphs = min(int(rng.paretovariate(1.2)), 200)
        for _ in range(paragraphs):
            if rng.random() < 0.3:
                lines += [f"- [{rng.choice(' x')}] " + " ".join(rng.choice(WORDS) for _ in range(rng.randint(1, 5)))
                          for _ in range(rng.randint(2, 8))]
            else:
                lines.append(" ".join(rng.choice(WORDS) for _ in range(rng.randint(10, 60))) + ".")
            lines.append("")
        text = "\n".join(lines)
        folder = "Work" if n % 7 == 0 else ""
        with open(os.path.join(OUT, folder, f"Note {n}.md"), "w", encoding="utf-8") as f:
            f.write(text)
        total += len(text.encode())
    with open(os.path.join(OUT, ".obsidian", "skip-me.md"), "w") as f:
        f.write("# hidden folder, must not be indexed #work\n")
    print(f"{N} notes, {total / 1e6:.1f} MB, largest paragraphs capped at 200")


main()
