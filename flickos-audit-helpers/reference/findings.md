# Audit report: FlickOS privileged helpers (reference answer)

> Don't open this until you've written your own `work/findings.md`
> (exercise 10). It is one auditor's result, not the only right one. If you
> rated something differently and can defend it, that's fine. If you found
> something that isn't here, you beat the reference.

| | |
|---|---|
| **Scope** | `flickos-control`'s `/usr/libexec/flickos/control-helper` (pkexec, 17 verbs) and its polkit policy; `flickos-countme`'s `countme-helper` and policy; `flickos-greeter`'s `greetd-config` (run as root by greetd.service) and `greeter` |
| **Source** | FlickOS `main` at commit `2b43677` (2026-10-06) |
| **Method** | Surface map → threat model → sink listing → manual trace of every non-constant argument → harness with recorded commands → 39 hand-written cases → 3,000 mutation-fuzz runs → proofs with real adduser/userdel in a user-namespace lab |
| **Not in scope** | flickos-phone (network), apt repo and signing, login/lock screen, per-user IPC, polkit and pkexec themselves |

## Summary

| ID | Severity | Title |
|---|---|---|
| F-1 | Low | `user-add`: a full name starting with `-` is read by adduser as an option (`--system` → a hidden administrator) |
| F-2 | Low | `user-add`: a user name with a trailing newline passes the check and leaves an orphan account |
| F-3 | Low | Every control-helper action keeps the password for 5 minutes (`auth_admin_keep`), including account and update changes |
| F-4 | Info | `packages-undo`: package names from apt's log reach apt-get without `--`, and the real run isn't held to the simulated plan |
| F-5 | Info | `packages-list ²` crashes with a traceback (`str.isdigit()` accepts Unicode digits) |
| F-6 | Info | "Keep one administrator" is checked without a lock: two removals at once can remove the last two |

Chain: **F-3 + F-1 = Medium.** Code running in an administrator's session within
5 minutes of any Settings password prompt can create a password-protected
member of `sudo` that Settings > Users never shows, with no second prompt.

No finding lets a standard user, or anyone without an administrator's password
(or that password's 5-minute window), change anything.

---

## F-1 (Low): adduser reads a full name as an option

**Where:** `control-helper` `cmd_user_add`, line 463:
`run_tool(["adduser", "--quiet", "--disabled-password", "--comment", full_name, name])`

**What:** adduser declares `'comment:s'` (Getopt::Long, `/usr/sbin/adduser`
line 163). `:s` means the value is **optional**, and Getopt::Long then takes a
following word that starts with `-` as the next option, not as the value.
`check_full_name` refuses `: , = \` and control characters, but not a leading
`-`. So a full name of `--system`, `--add-extra-groups`, `--no-create-home`,
`--disabled-login`, `--allow-all-names` or `--debug` is an adduser option.
(`--uid=0` is refused only because `=` is refused, for a different reason.)

**Scenario:** `pkexec control-helper user-add ghost --system yes` with a
password on stdin. adduser makes a **system** account (UID 100–999, shell
`/usr/sbin/nologin`, no home folder). chpasswd gives it the password, and
usermod adds it to `sudo`. Settings > Users lists only UID 1000–60000
(`accounts()`), so the new administrator is not shown and can't be removed
there. `user-remove` refuses it too ("not a regular account"). polkit's
administrators are `unix-group:sudo` (`/usr/share/polkit-1/rules.d/50-default.rules`),
so the account should work as the administrator in any password dialog.
(*Expected; prove it in the VM, exercise 8.3.*)

**Evidence:**
- `attack.py`: `FINDING user-add: full name --system`. The recorded argv is
  `['adduser', '--quiet', '--disabled-password', '--comment', '--system', 'ann']`.
- `tools/userns-lab.sh run 'adduser --quiet --disabled-password --comment --system labsys; getent passwd labsys'`
  prints `labsys:x:103:65534::/nonexistent:/usr/sbin/nologin`.

**Why only Low:** it needs an administrator's authorization, and an
administrator can already make an administrator. What it adds is
*concealment* from FlickOS's own UI. It is still in `/etc/group`, so
`getent group sudo` shows it.

**Fix:** attach the value, and end the options before the name:
`["adduser", "--quiet", "--disabled-password", f"--comment={full_name}", "--", name]`.
Verified in the lab: `--comment=--system` gives the GECOS field `--system`
and a normal account. Also refuse a leading `-` in `check_full_name` and in
flickos-control's `full_name_problem`, so the dialog says why.

**Regression test:** `HelperTest`: `main(["user-add", "ann", "--system", "no"])`
records an adduser argv in which every word after `--` is `ann`, and no
argument from the caller starts with `-`.

## F-2 (Low): a trailing newline passes the user-name check

**Where:** `USER_NAME = re.compile(r"^[a-z][-a-z0-9_]{0,31}$")` with `.match()`
(`check_new_name`, line 368).

**What:** in Python's `re`, `$` matches at the end of the string **or just
before a newline at the end**. `"ann\n"` passes. adduser accepts it too and
creates `ann`. Then chpasswd gets `"ann\n:secret\n"`, two lines and neither
valid, so it fails. The cleanup runs `userdel --remove "ann\n"`, which fails
("user 'ann\n' does not exist"), and that error is suppressed. The helper
reports an error, but the account `ann` stays: password disabled, home
folder created, no groups.

**Evidence:** `fuzz.py` finds it as R3 (adduser gets `'fuzzann\n'`) and R4
(chpasswd stdin `'fuzzann\n:secret\n'`). attack.py's hand case `"ann\nroot"`
is refused, because text follows the newline. The lab shows that adduser
creates `labnl` and userdel can't find `labnl\n`.

**Impact:** no privilege gain: the leftover account has no usable
password. A failed call that changes the system anyway is the problem.

**Fix:** `USER_NAME.fullmatch(name)` (or `\Z`). Look for the same pattern
elsewhere: `TRANSACTION_ID` (harmless: the id must equal one from the log)
and flickos-control's `USER_NAME` (dialog only).

## F-3 (Low, design): the password is kept for every action

**Where:** `org.flickos.control.policy`: all 15 actions are
`allow_active = auth_admin_keep`.

**What:** after one password, polkit gives the session a temporary
authorization for **that action** for about 5 minutes. Any process in the same
login session can then run that verb without a prompt. The pkexec manual says
so under SECURITY NOTES: with a kept authorization, "programs ... should never
implicitly trust user input (e.g. like any other well-written suid program)".

**Measured with `keep-probe.sh`** (fill in your own results; the expected
ones are in `answers.md` 8.2): second terminal, `setsid` background process,
systemd user service, other action, text console.

**Why Low:** code running as an administrator already has many ways to get
root. It can wait for `sudo`, edit `~/.bashrc`, or draw a fake password
dialog (a layer-shell overlay is easy on labwc). Debian's accountsservice
uses `auth_admin_keep` for `user-administration` too. The keep doesn't create
the risk, it shortens the wait.

**Recommendation:** use `auth_admin` (no keep) for the verbs that change *who
can get in*: `user-add`, `user-admin`, `user-password`, `autologin-on`,
`firewall-off`, `updates`, `packages-undo`. Keep `auth_admin_keep` where
the Settings window makes several calls in a row and the result is visible
and harmless: `keyboard`, `locale-add`, `power`, `firefox-memory`,
`firewall-on`, `firewall-phones`, `user-remove`, `autologin-off`.

## F-4 (Info): apt-get gets log data without `--`, and the real run isn't checked

**Where:** `undo_plan` / `cmd_packages_undo` (lines 976–1027), `PACKAGE_ITEM` (line 189).

**What:**
1. `PACKAGE_ITEM` accepts any name without spaces, commas or parentheses, so
   `-oAPT::Get::Show-Versions=1` in a log line becomes a "package". The plan
   passes it to `apt-get -s` and `apt-get -y` as an argument with no `--`,
   and apt-get parses options anywhere on its command line (tested:
   `apt-get -s remove -- -oFoo=1` treats it as a package, without `--` as an option).
2. The real `apt-get -y install …` has no `--no-remove`, so if the system
   changed between the simulation and the run, apt could remove packages
   the plan never showed.

**Why Info:** `/var/log/apt/history.log` is written only by root (apt), and
the package also has to pass `dpkg-query` as installed. Nobody without root
can put that line there. This is defence in depth: the helper shouldn't
need the log to be friendly.

**Fix:** accept only Debian package names
(`^[a-z0-9][a-z0-9+.-]+(:[a-z0-9-]+)?$`), put `--` before the names in both
apt-get calls, and add `--no-remove` to the install undo.

**Evidence:** `attack.py` case "option-like package in the log" with a crafted
log in the fake root: `apt-get would see an option: [..., 'remove', '-oAPT::Get::Show-Versions=1', 'hello']`.

## F-5 (Info): Unicode digits crash packages-list

`cmd_packages_list` checks `args[0].isdigit()` and calls `int(args[0])`.
`"²".isdigit()` is True, but `int("²")` raises ValueError, and `main()`
catches only HelperError, OSError and SubprocessError. The result is a
traceback, in a verb that runs without root. Fix: `re.fullmatch(r"[0-9]{1,5}", …)`.
(`"٣"`, Arabic-Indic three, is both a digit and an int, which shows that
`isdigit()` answers a different question from "ASCII number".)

## F-6 (Info): the last-administrator rule has a race

`keep_an_administrator()` reads group `sudo` and then the verb changes it.
Two calls at once (`user-admin ann no` and `user-admin bob no` while they are
the only administrators) can both pass the check. The result is no
administrator, so no password dialog can be answered until someone uses
recovery mode. It needs two authorized calls at the same moment, so the
impact is lock-out by mistake rather than attack. Fix: hold a lock
(`fcntl.flock` on a file in `/run`) around check-and-change.

---

## Checked and found OK

An audit records what holds as well as what fails.

- **keyboard:** every value must be a name from `evdev.lst`. Those names
  contain only `[A-Za-z0-9_:()+.-]` (checked: all 1,000 model, layout, variant and option names; the
  special characters in the file are in descriptions, not names). This
  matters because setupcon (as root, run by the helper itself right after
  writing), console-setup at boot, the greeter (as `_greetd`) and
  flickos-session all `.` the file in a shell.
- **Passwords** go through stdin, never argv (`/proc/PID/cmdline` is
  readable by every user). Only the first line is read, so a `\n` in the
  input can't add a `root:…` line. `\r` and NUL are refused. A `:` in a password
  is fine: chpasswd splits at the first `:`, and names can't contain one.
- **PKEXEC_UID** is set by pkexec after it clears the environment, so a caller
  can't choose it. The value must be digits and a regular UID. `autologin-*`
  act only on that user.
- **Environment:** pkexec runs the helper with a fixed PATH and without
  `LD_*`. That is what makes the bare names `gpasswd`, `adduser` and
  `systemctl` safe. Running the helper through `sudo -E` would not be,
  but that caller is already root.
- **Fixed-choice verbs** (`power`, `updates`, `firewall-*`,
  `firefox-memory`, `locale-add`) compare every argument with a list before
  using it. Nothing from the caller is written into a file except a listed
  value.
- **write_atomic:** the temp file is created in the target's own
  root-owned folder (`mkstemp`, O_EXCL), and `os.replace` replaces a
  symlink instead of following it. No user-writable folder is ever written to.
- **firewall-phones** refuses to touch a profile file that isn't its own.
- **countme-helper:** one fixed value per verb and no caller data. `off`
  needing no password is fine: it takes no input and only sends less.
  `installed` has no action of its own, so it falls back to pkexec's
  generic `auth_admin`.
- **greetd-config** (root, at every greetd start): takes the first member of
  group `autologin`, and keeps it only if it matches `[A-Za-z0-9._-]` and
  exists. That stops a strange name (useradd `--badname`) from breaking
  out of the TOML string. Its trust anchor is the group itself: whoever can
  add to `autologin` can make the computer start a session without a password.
  Only root can (`gpasswd -M` in the helper, for the caller only).
- **bandit** reports 14 Low items: `import subprocess`, subprocess without a
  shell, and partial paths. None of them is one of the findings above,
  and none of the findings above is in bandit's output.
