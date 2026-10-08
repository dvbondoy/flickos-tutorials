#!/usr/bin/python3
"""Mutation fuzzer for a privileged helper, with generic safety rules.

Reference answer for exercise 7. attack.py checks inputs you thought of;
this one makes up inputs and checks rules that must hold for EVERY input:

  R1 no crash        main() never raises an exception it doesn't catch
  R2 no options      an argument a program gets that starts with "-" is one of
                     the helper's own string constants, never caller data
  R3 no controls     no argument a program gets has a control character
  R4 one stdin line  standard input given to a program is exactly one line
  R5 inert files     a line the helper adds to a file has no control
                     character, and no shell syntax ($( ` ; | &) outside quotes
                     unless it is a comment

Start from valid calls (SEEDS), change one argument or the standard input
(MUTATIONS), run through the harness, check the rules.

    python3 fuzz.py [--runs N] [--seed S] [HELPER]
"""

import argparse
import ast
import collections
import os
import pwd
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness  # noqa: E402

FLICKOS = os.environ.get("FLICKOS", os.path.expanduser("~/Documents/Projects/FlickOS"))
DEFAULT_HELPER = os.path.join(FLICKOS, "packages/flickos-control/usr/libexec/flickos/control-helper")
ME_NAME = pwd.getpwuid(os.getuid()).pw_name

SEEDS = [
    (["keyboard", "pc105", "us,de", ",nodeadkeys", "grp:alt_shift_toggle"], ""),
    (["user-add", "fuzzann", "Ann Lee", "no"], "secret\n"),
    (["user-admin", ME_NAME, "yes"], ""),
    (["user-password", ME_NAME], "secret\n"),
    (["user-remove", ME_NAME, "keep"], ""),
    (["autologin-on"], ""),
    (["power", "lid", "suspend"], ""),
    (["updates", "scope", "debian"], ""),
    (["firewall-phones", "on"], ""),
    (["firefox-memory", "off"], ""),
    (["locale-add", "de_DE.UTF-8"], ""),
    (["packages-list", "30"], ""),
    (["packages-plan", "2030-01-01T10:00:00"], ""),
]

PAYLOADS = ["-", "--system", "--help", "-o", "--", '"', "'", "$(id)", "`id`", ";id", "|id", "&",
            "\n", "\r", "\t", "\x1b[31m", "../../etc/passwd", "/etc/shadow", "²", "٣",
            "‐", "a" * 5000, "", " ", ",", ":", "=", "\\", "#", "*", "‮"]


def mutate(value, rng):
    payload = rng.choice(PAYLOADS)
    how = rng.choice(("replace", "prefix", "suffix", "middle"))
    if how == "replace":
        return payload, f"replace with {payload[:12]!r}"
    if how == "prefix":
        return payload + value, f"prefix {payload[:12]!r}"
    if how == "suffix":
        return value + payload, f"suffix {payload[:12]!r}"
    i = rng.randrange(len(value) + 1)
    return value[:i] + payload + value[i:], f"insert {payload[:12]!r}"


def string_constants(path):
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    return {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}


CONTROL = re.compile(r"[\x00-\x08\x0a-\x1f\x7f]")
SHELL = re.compile(r"\$\(|`|;|\||&")


def unquoted(line):
    """The line without its "..." parts (a quoted value is data to a shell)."""
    return re.sub(r'"[^"]*"', '""', line)


def violations(result, constants):
    found = []
    if result.crashed:
        found.append(("R1 no crash", result.crashed.strip().splitlines()[-1]))
    for argv, given in result.commands:
        for word in argv[1:]:
            if word.startswith("-") and word not in constants:
                found.append(("R2 no options", f"{os.path.basename(argv[0])} gets {word[:40]!r}"))
            if CONTROL.search(word):
                found.append(("R3 no controls", f"{os.path.basename(argv[0])} gets {word[:40]!r}"))
        if given is not None and (given.count("\n") != 1 or not given.endswith("\n")):
            found.append(("R4 one stdin line", f"{os.path.basename(argv[0])} stdin {given[:40]!r}"))
    for path, text in result.changed.items():
        old = set((result.before.get(path) or "").splitlines())
        for line in (text or "").splitlines():
            if line in old:
                continue
            comment = line.lstrip().startswith(("#", "//", ";"))
            if CONTROL.search(line.replace("\t", "")) or (not comment and SHELL.search(unquoted(line))):
                found.append(("R5 inert files", f"{path}: {line[:60]!r}"))
    return found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("helper", nargs="?", default=DEFAULT_HELPER)
    opts = parser.parse_args()

    rng = random.Random(opts.seed)
    h = harness.Harness(opts.helper)
    constants = string_constants(opts.helper)
    # One example per (rule, verb, argument position): the first input that broke it.
    seen = collections.OrderedDict()
    for _ in range(opts.runs):
        argv, stdin = rng.choice(SEEDS)
        argv = list(argv)
        positions = list(range(1, len(argv))) + ["stdin"]
        where = rng.choice(positions)
        if where == "stdin":
            stdin, how = mutate(stdin, rng)
        else:
            argv[where], how = mutate(argv[where], rng)
        result = h.run(argv, stdin)
        for rule, detail in violations(result, constants):
            key = (rule, argv[0], where)
            if key not in seen:
                seen[key] = (argv, stdin, how, detail)

    for (rule, verb, where), (argv, stdin, how, detail) in seen.items():
        print(f"{rule:18} {verb} (argument {where}: {how})")
        print(f"{'':18} argv={argv!r:.120} stdin={stdin!r:.40}")
        print(f"{'':18} -> {detail}")
    print(f"\n{opts.runs} runs, {len(seen)} distinct problems")
    return 1 if seen else 0


if __name__ == "__main__":
    sys.exit(main())
