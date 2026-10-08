#!/usr/bin/python3
"""Map FlickOS's privileged attack surface from the source tree.

Reference answer for exercise 1. It answers: what runs as root (or as a
system user), who can start it, and with what password rule?

  1. polkit actions (packages/*/usr/share/polkit-1/actions/*.policy) and the
     helper verbs they guard: every verb of a helper is matched to its action,
     so a verb without an action, or an action without a verb, shows up;
  2. every other way into root that a package ships: systemd units and
     drop-ins (ExecStart*= without User=), maintainer scripts, apt hooks,
     sudoers, polkit rules, udev RUN+=, D-Bus system services, profile.d.

It reads files only; it never imports or runs a helper (why not? exercise 1).

    python3 surface-map.py [FLICKOS]
"""

import ast
import glob
import os
import re
import sys
import xml.etree.ElementTree as ET

FLICKOS = sys.argv[1] if len(sys.argv) > 1 else \
    os.environ.get("FLICKOS", os.path.expanduser("~/Documents/Projects/FlickOS"))
PACKAGES = os.path.join(FLICKOS, "packages")
EXEC_PATH = "org.freedesktop.policykit.exec.path"
EXEC_ARGV1 = "org.freedesktop.policykit.exec.argv1"
# Default answers from the weakest to the strongest.
STRENGTH = {"yes": 0, "auth_self_keep": 1, "auth_self": 2, "auth_admin_keep": 3, "auth_admin": 4, "no": 5}


def package_files(pattern):
    """Files of the packages' trees, not build output (packages/.build, debian/PKG/)."""
    found = []
    for path in glob.glob(os.path.join(PACKAGES, pattern), recursive=True):
        rel = os.path.relpath(path, PACKAGES)
        if rel.startswith(".build") or re.match(r"[^/]+/debian/[^/]+/", rel):
            continue
        if os.path.isfile(path):
            found.append(path)
    return sorted(found)


def policy_actions():
    actions = []
    for path in package_files("*/usr/share/polkit-1/actions/*.policy"):
        for action in ET.parse(path).getroot().iter("action"):
            defaults = action.find("defaults")
            notes = {a.get("key"): (a.text or "").strip() for a in action.findall("annotate")}
            actions.append({
                "id": action.get("id"),
                "package": os.path.relpath(path, PACKAGES).split("/")[0],
                "any": defaults.findtext("allow_any", "no").strip() if defaults is not None else "no",
                "inactive": defaults.findtext("allow_inactive", "no").strip() if defaults is not None else "no",
                "active": defaults.findtext("allow_active", "no").strip() if defaults is not None else "no",
                "path": notes.get(EXEC_PATH),
                "argv1": notes.get(EXEC_ARGV1),
            })
    return actions


def helper_verbs(path):
    """(verbs, read-only verbs) of a Python helper: the keys of its VERBS dict
    and the strings of READ_ONLY, read from the syntax tree."""
    with open(path, encoding="utf-8") as f:
        source = f.read()
    if not source.startswith("#!/usr/bin/python3"):
        return None, ()
    verbs, read_only = [], ()
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name == "VERBS" and isinstance(node.value, ast.Dict):
                verbs = [k.value for k in node.value.keys if isinstance(k, ast.Constant)]
            elif name == "READ_ONLY" and isinstance(node.value, (ast.Tuple, ast.List)):
                read_only = tuple(e.value for e in node.value.elts if isinstance(e, ast.Constant))
    return verbs, read_only


def flags(action):
    found = []
    if action["active"] == "yes":
        found.append("NO PASSWORD for the person at the computer")
    elif action["active"].endswith("_keep"):
        found.append("password kept ~5 min (auth_admin_keep)")
    if STRENGTH.get(action["any"], 0) < STRENGTH["auth_admin"]:
        found.append(f"remote/ssh: {action['any']}")
    return found


def section(title):
    print(f"\n== {title} " + "=" * max(0, 70 - len(title)))


def main():
    actions = policy_actions()
    section("1. pkexec helpers and their polkit actions")
    helpers = sorted({a["path"] for a in actions if a["path"]})
    for helper in helpers:
        files = package_files("*" + helper)
        source = files[0] if files else None
        verbs, read_only = helper_verbs(source) if source else (None, ())
        guarded = {a["argv1"]: a for a in actions if a["path"] == helper}
        print(f"\n{helper}  ({os.path.relpath(source, FLICKOS) if source else 'NOT IN THE TREE'})")
        print(f"  {'verb':18} {'action':38} {'active':16} notes")
        for verb in verbs or []:
            action = guarded.get(verb)
            if action:
                print(f"  {verb:18} {action['id']:38} {action['active']:16} {'; '.join(flags(action))}")
            else:
                why = "read-only, runs without root" if verb in read_only else "-"
                print(f"  {verb:18} {'(none: generic pkexec action)':38} {'auth_admin':16} {why}")
        for argv1, action in guarded.items():
            if verbs is not None and argv1 not in verbs:
                print(f"  {argv1 or '(any)':18} {action['id']:38} {action['active']:16} ACTION WITHOUT A VERB")
    others = [a for a in actions if not a["path"]]
    if others:
        print("\nActions not tied to a program (checked by a daemon with pkcheck/D-Bus):")
        for action in others:
            print(f"  {action['id']:56} {action['active']:16} {'; '.join(flags(action))}")

    section("2. Other ways into root shipped by the packages")
    rows = []
    for path in package_files("*/**/systemd/system/**/*") + package_files("*/debian/*.service") + \
            package_files("*/debian/*.timer"):
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        user = re.search(r"^\s*User=(\S+)", text, re.M)
        for match in re.finditer(r"^\s*(Exec\w*)=(.+)$", text, re.M):
            if match.group(2).strip():
                rows.append((path, f"systemd {match.group(1)}", match.group(2).strip(),
                             f"as {user.group(1)}" if user else "AS ROOT"))
    for path in package_files("*/debian/*.preinst") + package_files("*/debian/*.postinst") + \
            package_files("*/debian/*.prerm") + package_files("*/debian/*.postrm") + \
            package_files("*/debian/*.config") + package_files("*/debian/*.triggers"):
        rows.append((path, "maintainer script", os.path.basename(path), "AS ROOT, by dpkg"))
    for path in package_files("*/etc/apt/apt.conf.d/*"):
        with open(path, encoding="utf-8", errors="replace") as f:
            hooks = re.findall(r"(\S*Invoke\S*)\s", f.read())
        rows.append((path, "apt configuration", ", ".join(hooks) or "no Invoke hooks",
                     "AS ROOT on every apt run" if hooks else "settings for root's apt"))
    for path in package_files("*/etc/sudoers.d/*"):
        rows.append((path, "sudoers", "", "AS ROOT"))
    for path in package_files("*/**/polkit-1/rules.d/*"):
        rows.append((path, "polkit rule (JavaScript)", "", "decides who is admin"))
    for path in package_files("*/**/udev/rules.d/*"):
        with open(path, encoding="utf-8", errors="replace") as f:
            runs = re.findall(r'RUN\+?="([^"]+)"', f.read())
        rows.append((path, "udev rule", ", ".join(runs) or "no RUN", "AS ROOT" if runs else "permissions"))
    for path in package_files("*/usr/share/dbus-1/system-services/*"):
        rows.append((path, "D-Bus system service", "", "see its User="))
    for path in package_files("*/etc/profile.d/*"):
        rows.append((path, "login shell snippet", "", "as EVERY user who logs in, root too"))
    for path in package_files("*/debian/*.sysusers"):
        rows.append((path, "sysusers", "creates system users/groups", "at install"))
    for path, kind, what, who in rows:
        print(f"  {os.path.relpath(path, PACKAGES):58} {kind:22} {who:30} {what}")


if __name__ == "__main__":
    main()
