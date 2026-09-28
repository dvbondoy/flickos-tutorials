#!/usr/bin/env python3
"""check-wiring.py: is a FlickOS package wired in everywhere? HIG PKG-10 as a
list you can run, plus the version rules of PKG-3.

    ./check-wiring.py [--repo DIR] PACKAGE …
    ./check-wiring.py --all

DIR is a FlickOS clone (default: this folder's practice/). For each package
it looks at:

  debian/     control, changelog, copyright, rules (executable),
              source/format, and install when there are files to install
              and no build system of its own; the top changelog entry
              released (trixie, not UNRELEASED), without a revision (-1)
  tests       tests/test_*.py for a Python program of FlickOS's own in
              usr/bin/ (third-party packages have debian/README.source)
  pulled in   who installs it: flickos-desktop's Depends or Recommends,
              another package's Depends, or a list in config/package-lists/
  REQUIRED    in the sanity hook's list (expected for a Depends of
              flickos-desktop, not for a Recommends)
  boot test   the package or one of its programs named in tools/boot-test.py
              (a note only, for a package with no program or desktop file)
  docs        a section in docs/04, a row in docs/01's table and a line in
              its folder tree, a paragraph in CLAUDE.md, and whether
              docs/design/PACKAGE.md exists

Each line starts with ok, MISSING or note. It only reads files. What it
can't judge (is the design doc needed, is the boot-test check any good) is
a note for you to decide.

Exit codes: 0 nothing missing, 1 something missing, 2 usage error.
"""
import argparse
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEBIAN_FILES = ("control", "changelog", "copyright", "rules", "source/format")
# A package with one of these builds and installs its files itself.
BUILD_SYSTEMS = ("meson.build", "Makefile", "setup.py", "pyproject.toml", "CMakeLists.txt")
# Packages that are the wiring themselves, so some checks don't apply.
META = "flickos-desktop"
SANITY_HOOK = "config/hooks/normal/0010-sanity.hook.chroot"


def read(repo, path):
    try:
        with open(os.path.join(repo, path), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def stanzas(control):
    """debian/control as a list of {field: value}, comments dropped and
    continuation lines joined."""
    result, current, field = [], {}, None
    for line in control.splitlines():
        if line.startswith("#"):
            continue
        if not line.strip():
            if current:
                result.append(current)
            current, field = {}, None
        elif line[0] in " \t" and field:
            current[field] += " " + line.strip()
        elif ":" in line:
            field, value = line.split(":", 1)
            field = field.strip().lower()
            current[field] = value.strip()
    if current:
        result.append(current)
    return result


def names(relation):
    """Package names in a Depends-style field: "a (>= 1), b | c" → {a, b, c}."""
    return {re.split(r"[\s(\[:]", alt.strip())[0] for part in relation.split(",")
            for alt in part.split("|") if alt.strip() and not alt.strip().startswith("$")}


def pulled_in(repo, package):
    """[(how, by)]: the relations and package lists that install it."""
    found = []
    for control in sorted(glob.glob(os.path.join(repo, "packages/*/debian/control"))):
        for stanza in stanzas(read(repo, control)):
            owner = stanza.get("package")
            if not owner or owner == package:
                continue
            for field in ("depends", "recommends"):
                if package in names(stanza.get(field, "")):
                    found.append((field.capitalize(), owner))
    for listing in sorted(glob.glob(os.path.join(repo, "config/package-lists/*.list.chroot"))):
        words = {word for line in read(repo, listing).splitlines()
                 if not line.lstrip().startswith("#") for word in line.split()}
        if package in words:
            found.append(("listed in", os.path.relpath(listing, repo)))
    return found


def required(repo):
    match = re.search(r'REQUIRED="([^"]*)"', read(repo, SANITY_HOOK))
    return set(match.group(1).split()) if match else set()


def check(repo, package):
    """[(level, text)] for one package."""
    out = []
    add = lambda level, text: out.append((level, text))
    folder = os.path.join("packages", package)
    if not os.path.isdir(os.path.join(repo, folder, "debian")):
        return [("MISSING", f"{folder}/debian/ doesn't exist")]

    # debian/
    root = os.path.join(repo, folder)
    files_to_install = any(os.path.isdir(os.path.join(root, top)) for top in ("etc", "usr", "lib"))
    own_build = any(os.path.isfile(os.path.join(root, name)) for name in BUILD_SYSTEMS)
    wanted = DEBIAN_FILES + (("install",) if files_to_install and not own_build else ())
    missing = [name for name in wanted if not os.path.isfile(os.path.join(root, "debian", name))]
    add("MISSING" if missing else "ok", "debian/: " + (f"no {', '.join(missing)}" if missing else
                                                      f"{', '.join(wanted)}"))
    rules = os.path.join(repo, folder, "debian/rules")
    if os.path.isfile(rules) and not os.access(rules, os.X_OK):
        add("MISSING", "debian/rules isn't executable (chmod +x)")
    top = read(repo, f"{folder}/debian/changelog").split("\n", 1)[0]
    match = re.match(r"(\S+) \(([^)]+)\) (\S+);", top)
    if not match:
        add("MISSING", f"debian/changelog: no entry at the top ({top!r})")
    else:
        version, distribution = match.group(2), match.group(3)
        problems = ([f"{distribution}, not trixie"] if distribution != "trixie" else []) + (
            [f"{version} has a Debian revision"] if "-" in version else [])
        add("MISSING" if problems else "ok", f"version {version}" + (f": {', '.join(problems)}" if problems else ""))

    # tests (only for FlickOS's own Python programs)
    programs = glob.glob(os.path.join(root, "usr/bin/*"))
    third_party = os.path.isfile(os.path.join(root, "debian/README.source"))
    python = [p for p in programs if read(repo, p).startswith("#!/usr/bin/python3")]
    tests = glob.glob(os.path.join(root, "tests/test_*.py"))
    if python and not third_party:
        add("ok" if tests else "MISSING",
            f"tests: {len(tests)} file(s) in tests/" if tests else "tests: no tests/test_*.py for its program (PKG-8)")
        if tests and "dh_auto_test" not in read(repo, f"{folder}/debian/rules"):
            add("MISSING", "tests: debian/rules doesn't run them (override_dh_auto_test)")

    # pulled in, REQUIRED
    if package != META:
        how = pulled_in(repo, package)
        if how:
            for relation, by in how:
                add("ok", f"pulled in: {relation} {by}")
        else:
            add("MISSING", f"pulled in: nothing installs it ({META}'s Depends or Recommends?)")
        in_required = package in required(repo)
        desktop_depends = ("Depends", META) in how
        if desktop_depends and not in_required:
            add("note", f"REQUIRED: a Depends of {META} but not in {SANITY_HOOK} (needed if the desktop breaks without it)")
        elif ("Recommends", META) in how and in_required:
            add("note", f"REQUIRED: listed, but only a Recommends of {META}")
        else:
            add("ok", "REQUIRED: listed" if in_required else "REQUIRED: not listed (not a must-have)")

    # boot test
    boot_test = read(repo, "tools/boot-test.py")
    words = list(dict.fromkeys([package] + [os.path.basename(p) for p in programs]))
    named = [word for word in words if re.search(rf"(?<![\w-]){re.escape(word)}(?![\w-])", boot_test)]
    visible = programs or glob.glob(os.path.join(root, "usr/share/applications/*.desktop"))
    add("ok" if named else "MISSING" if visible else "note",
        f"boot test: {', '.join(named)} named in tools/boot-test.py" if named
        else "boot test: not named in tools/boot-test.py (PKG-9: a check for what users can see)")

    # docs
    add("ok" if f"### `{package}`" in read(repo, "docs/04-packages.md") else "MISSING",
        f"docs/04: section ### `{package}`")
    overview = read(repo, "docs/01-overview.md")
    row = any(line.startswith("|") and f"packages/{package}/" in line for line in overview.splitlines())
    add("ok" if row else "MISSING", f"docs/01: a row in \"Where to change what\" naming packages/{package}/")
    tree = f"── {package}/" in overview
    add("ok" if tree else "note", f"docs/01: {package}/ in the repository layout tree")
    add("ok" if re.search(rf"^  - `{re.escape(package)}`", read(repo, "CLAUDE.md"), re.M) else "MISSING",
        f"CLAUDE.md: a paragraph   - `{package}`: …")
    design = f"docs/design/{package}.md"
    add("ok" if os.path.isfile(os.path.join(repo, design)) else "note",
        design + (" exists" if os.path.isfile(os.path.join(repo, design))
                  else " doesn't exist (needed for anything bigger than a small tool)"))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("packages", nargs="*", metavar="PACKAGE")
    parser.add_argument("--repo", default=os.path.join(HERE, "practice"), help="the FlickOS clone (default: practice/)")
    parser.add_argument("--all", action="store_true", help="every package in packages/")
    opts = parser.parse_args()
    if not os.path.isdir(os.path.join(opts.repo, "packages")):
        parser.error(f"{opts.repo} isn't a FlickOS clone (no packages/)")
    packages = opts.packages or []
    if opts.all:
        packages = sorted(os.path.basename(os.path.dirname(d))
                          for d in glob.glob(os.path.join(opts.repo, "packages/*/debian")))
    if not packages:
        parser.error("name a package, or --all")
    missing = 0
    for number, package in enumerate(packages):
        print(("\n" if number else "") + package)
        for level, text in check(opts.repo, package):
            print(f"  {level:<8}{text}")
            missing += level == "MISSING"
    if len(packages) > 1:
        print(f"\n{missing} missing")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
