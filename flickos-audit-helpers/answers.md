# Answers

> **Spoilers.** Open a section only after you've written your own answer in
> `work/notes.md`. Where an answer says *expected*, it wasn't measured while
> writing this guide (it needs a password or a VM). Your measurement wins:
> if it differs, write down both, then work out why.

---

## §0 Background

**Q0.1** polkit protects against the wrong **caller**: it decides whether this
user, in this kind of session, may run this program, and asks for a password
if needed. It does **not** protect against wrong **arguments** from a caller
it let through, against a malicious program running inside an authorized
session, or against bugs in the helper. pkexec "does no validation of the
ARGUMENTS" (its manual).

**Q0.2** Every process running in any active local session can run it
without a password: every user's, and every program those users start, with
any arguments. So the verb must check its input as strictly as a setuid
program does, by allowlist. Better still, it takes no input at all.

## §2 Threat model

**Q2.1** Assets (any five or more):
- root itself (code running as root)
- **who can get in:** accounts, passwords, membership of `sudo` (= administrator
  for both sudo and polkit), automatic login at boot
- **what the computer installs:** the automatic-update policy, and the
  removal or reinstallation of packages (packages-undo)
- **what the network can reach:** the firewall on/off and the ports opened for phones
- **files other root programs trust:** `/etc/default/keyboard` (sourced by
  shells as root), `/etc/locale.gen`, logind and apt drop-ins
- **availability:** the power button and lid actions; losing the last administrator
- **privacy:** the weekly count

**Q2.2**
- **A1, a standard user,** can run `pkexec` but every action except
  `countme off` needs an *administrator's* password. They want root, an
  administrator account, or someone else's account.
- **A2, malware as an administrator inside their session,** can run `pkexec`
  at any time. With `auth_admin_keep` it can reuse the password the person
  typed in the last ~5 minutes, without a dialog. It can also fake a dialog
  and phish the password. It wants lasting, preferably hidden, access: a
  second administrator, autologin, updates off, the firewall off.
- **A3, the network,** has no path to pkexec: pkexec is local.
  `allow_any = auth_admin` covers an ssh login, but that already needs an
  account. A3 belongs to the flickos-phone part of the audit.
- **A4, the repository,** already runs code as root in every package's
  maintainer scripts. It belongs to the supply-chain part.

**Q2.3** A1 and A2, the local attackers. A1 shows whether the password
requirement can be skipped at all. A2 is the realistic one for anything
that needs authorization. A3 belongs in the flickos-phone audit and A4 in
the repository/signing audit (`#2` and `#3` of the audit plan).

**Q2.4** Places where data crosses into the more trusted side:
1. **argv**, from the caller to root.
2. **stdin** (passwords).
3. **The environment.** pkexec cleans it, but `PKEXEC_UID` is read from it.
4. **Files the helper reads:** `evdev.lst`, `/usr/share/i18n/SUPPORTED`,
   `login.defs`, apt's history log, the existing contents of the files it
   rewrites, and the user and group databases (NSS: possibly LDAP, not only
   `/etc/passwd`).
5. **Files the helper writes that other root programs read later:**
   keyboard → setupcon/console-setup, logind drop-in → logind, apt drop-in →
   unattended-upgrades, ufw profile → ufw, `locale.gen` → locale-gen, Firefox
   prefs → every user's Firefox, group `autologin` → greetd-config.
6. Output back to the Settings window (minor).

## §3 Exercise 1

**Q3.1** Some ways a package runs code as root without anyone typing sudo:
- pkexec helpers (polkit `exec.path`)
- D-Bus system services that check polkit themselves
- systemd system units: service, timer, path and socket activation, and
  drop-ins that add `ExecStartPre=`
- dpkg maintainer scripts and triggers
- apt hooks (`DPkg::Pre-Invoke`, `DPkg::Post-Invoke`, `APT::Update::Post-Invoke`)
- `/etc/sudoers.d`
- setuid/setgid files and file capabilities
- udev `RUN+=`
- cron (`/etc/cron.d`)
- NetworkManager dispatcher scripts
- `/etc/profile.d` (also runs when root logs in)
- PAM configuration
- initramfs hooks, kernel modules
- `tmpfiles.d` and `sysusers.d` (create files, users and groups)
- at build time: live-build hooks

**Q3.2** Importing *executes* the module's top level as you. A broken or
malicious file then acts instead of being read. Imports can also fail on
missing dependencies (GTK) or have side effects (files, network). An
auditor reads code and doesn't run code they haven't reviewed. `ast` gives
you the structure without running anything.

**Q3.3** pkexec looks for an action whose `exec.path` (and `exec.argv1`, if
given) matches. If none does, it uses the generic
`org.freedesktop.policykit.exec` action, which is `auth_admin` (no keep).
So a verb without an action isn't open: it just needs the full password
every time. For control-helper the verbs without an action are
`packages-list` and `packages-plan`, which are meant to run *without*
pkexec as the user. For countme-helper it is `installed`.

**Q3.4** `org.flickos.countme.off` takes no input (argv must be exactly `off`),
writes a fixed value, and its effect is "send less". The worst a malicious
local process can do with it is stop the count. That's fine. It would not be
fine if the verb took any argument, wrote anything the caller chose, or if
"off" turned off something protective.

**Q3.5** Your prediction; measured in exercise 8.

## §4 Exercise 2

**Q4.1** *Expected:* a short environment. `PATH` is a fixed system value
(something like `/usr/sbin:/usr/bin:/sbin:/bin`; write down exactly what
yours says). There are root's `HOME`, `USER` and `LOGNAME`, a few locale and
terminal variables, and **`PKEXEC_UID=<your uid>`**. Your `FOO`, your
`LD_PRELOAD` and your `PKEXEC_UID=0` are gone or replaced, and so is
`/tmp/evil` in `PATH`.

**Q4.2** pkexec runs the program in the target user's home folder, `/root`.
The helper uses only absolute paths: the constants, `tempfile.mkstemp(dir=folder)`,
and the glob of `APT_LOG`. So the current directory doesn't matter.

**Q4.3** Your own.

**Q4.4** Through `sudo -E` (or a sudoers `env_keep`/`SETENV` rule), from a
root shell with the variable exported, or from a systemd unit with
`Environment=`. In each case the caller is already root, so it gains
nothing. It would start to matter if someone later added a sudoers rule
letting a *user* run the helper with their own environment.

**Q4.5** It is safe because pkexec replaces `PATH` with a fixed list of
root-owned folders before the helper starts, so `gpasswd` can only be
`/usr/sbin/gpasswd`. It stops being safe as soon as something starts the
helper with the caller's `PATH` (a careless sudo rule, a service file).
Absolute paths cost nothing and remove the condition.

## §5 Exercise 3

**Q5.1** Program sinks with a list argv and no shell can't be broken with
`;` or `$( )`, but they still invite:
- **argument (option) injection:** a value that starts with `-`
- **record injection:** a newline in data that becomes lines (chpasswd stdin)
- **target confusion:** the right command applied to the wrong user or package

File sinks invite:
- **content injection** that a later parser misreads (shell, TOML, apt.conf)
- **symlink and path tricks**
- **wrong permissions**

**Q5.2** grep finds `subprocess.run(command, …)` inside `run_tool`, where
the argument is a variable. The line where caller data goes into the argv,
`run_tool(["adduser", …, full_name, name])`, contains no `subprocess` at all.
You have to follow wrappers to their call sites.

**Q5.3** bandit 1.9 reports: B404 (`import subprocess`, noise), B603
(subprocess without a shell; each one is a sink your script already lists,
so these are the ones that need a look) and B607 (partial path: `gpasswd`,
`dpkg`, `dpkg-query`; safe for the reason in Q4.5). Debian's older bandit may
count slightly differently. bandit flags `subprocess.run` at **line 360**
inside `run_tool`, but never line **463**, the adduser call where the full
name goes in, or line 465, where the chpasswd line is built.

**Q5.4** Pattern tools find **dangerous constructs** (shell=True, eval,
weak hashes, partial paths). They can't find **wrong meaning**: a check
that is a little too loose, a value that one program reads differently
from what the author assumed. That needs a person tracing data, then tests.

## §6 Exercise 4

**Q6.1** The readers of `/etc/default/keyboard`:
- `setupcon`, which sources it (`. "$MAIN_CONFIG"`) as **root**. The helper
  itself runs `setupcon --save-only -k` right after writing (`AFTER`), so
  an injection would run as root *during the same call*.
- `console-setup.sh` / keyboard-setup at boot (root)
- flickos-greeter's `greeter` (as `_greetd`)
- `flickos-session` (as every user who logs in)
- flickos-control (reads it as the user)

**Q6.2** `us";touch /tmp/x;"` or `$(…)` or backticks would become code. What
stops them: `check_keyboard()`, where each model, layout, variant and option
must be a name from `evdev.lst`. The assumption is that **those names contain
no shell metacharacters**, and that `evdev.lst` (package xkb-data) is
root-owned. To verify, parse the file the way `rules()` does and test every
name with `re.fullmatch(r"[A-Za-z0-9_:()+.-]+", name)`. All 1,000 pass. The
`"` and `&lt;` in the file are in the description column only. Write it down:
a future xkb-data with a strange name would break this defence without any
FlickOS change. An extra format check in the helper costs one line.

**Q6.3** Inputs that could make chpasswd change *another* account:
- `"pw\nroot:new"`: a second line. Stopped because `read_password()` reads
  **only the first line** (`readline`), and also refuses `\n`, `\r` and `\0`.
- `"pw\rroot:new"`: refused (`\r`).
- `"pw\0…"`: refused (`\0`). The name side can't contain `:`, and only a
  trailing `\n` gets through, as Q6.4 shows.

The password goes on stdin because argv is readable by every user in
`/proc/PID/cmdline` and `ps`, and may end up in audit logs.

**Q6.4** Yes: `"ann\n"`. In Python's `re`, `$` matches at the end **or just
before a final newline**, so `^…$` with `.match()` lets one trailing newline
through. Use `fullmatch()` or `\Z`. This is **F-2**.

**Q6.5** `'comment:s'` is an **optional** value. Getopt::Long then treats a
following word that looks like an option as the next option, so a full name
`--system` makes a system account, and the comment is empty. Test:

```sh
perl -MGetopt::Long -e '@ARGV=("--comment","--system","ann");
  GetOptions("comment:s"=>\$c,"system"=>\$s); print "comment=[$c] system=[$s] rest=[@ARGV]\n"'
# comment=[] system=[1] rest=[ann]
```

This is **F-1**. `=` being refused hides the worst cases (`--uid=0`),
but by accident.

**Q6.6** Between "not logged in" and `userdel`, the user could log in. userdel
itself refuses an account with running processes (without `-f`), so that
holds. The "last administrator" check has no such second line of defence,
which is **F-6**.

**Q6.7** `gpasswd -M USER autologin` makes the caller (from `PKEXEC_UID`) the
**only** member. `greetd-config` reads the first member at every greetd
start and writes it into `[initial_session]`. The caller can only choose
themselves. If a standard user asks, the administrator who types the
password approves autologin *for that user*. The dialog text should say so.

**Q6.8**
- `power`: `POWER_SETTINGS` and `POWER_ACTIONS` dicts, both checked first.
- `updates`: `UPDATE_SETTINGS`.
- `firewall-*`, `firefox-memory`: the argv must equal `["on"]` or `["off"]`.
- `locale-add`: compared with `/usr/share/i18n/SUPPORTED`, which is
  root-owned (package locales). Keyboard's `evdev.lst` is the other list
  read from a file.

**Q6.9** From `/var/log/apt/history.log`, which only root (apt) writes.
`PACKAGE_ITEM` does accept `-oX::Y=1` as a name (`[^\s,()]+`). apt-get parses
options anywhere: `apt-get -s remove -oDebug::NoLocking=1 hello` takes it as
an option, while after `--` it is "Unable to locate package". Not exploitable
without root, so **F-4** is Info, and defence in depth.

**Q6.10** Another apt run, an unattended upgrade or the user's own
install between `apt-get -s` and `apt-get -y` can change what a removal pulls
with it, or make an install need a removal. `apt-get install --no-remove`
aborts if anything would be removed. The helper doesn't use it (F-4, part 2).

**Q6.11**
- `mkstemp(dir=<target's folder>)` creates the file with `O_EXCL`, mode 0600
  and a random name, then `chmod 0644`.
- `os.replace` is `rename(2)`, which replaces a symlink at the target instead
  of following it.
- It would be unsafe if the folder were writable by a non-root user (they
  could swap files around the rename). Every target folder is root-owned:
  `/etc/default`, `/etc/systemd/logind.conf.d` (made 0755), `/etc/apt/apt.conf.d`,
  `/etc/ufw/applications.d`, `/etc/firefox-esr`, `/etc`.
- Minor: the mode is always 0644, so an administrator's own 0600 would be
  widened. None of these files is secret.

**Q6.12** `packages-list ²` raises ValueError (`"²".isdigit()` is True, but
`int("²")` fails). This is **F-5**. A traceback from root mostly leaks paths
in public code. The real danger of uncaught exceptions is **half-done
changes**: `cmd_user_add`'s cleanup only runs for HelperError, OSError and
TimeoutExpired, so any other exception between adduser and usermod would
leave a half-made account.

## §7 Exercise 5

**Q7.1** What the harness has to fake:
- every path constant the helper writes (`/etc/…`, `/var/log/…`, `/run`):
  redirect it into a temp folder
- `subprocess.run`: record it, don't execute
- `os.geteuid()`: return 0
- `PKEXEC_UID`
- `sys.stdin`
- stdout and stderr: capture them

**Q7.2** Use a guard that is independent of the harness logic: an **audit
hook** (`sys.addaudithook`) that refuses any write outside the fake root and
any process start. It can't be removed once added, so a later bug can't
switch it off. Then test the guard itself (the self-test).

**Q7.3** Read-only lookups: `pwd`, `grp`, `/proc`, `evdev.lst`, `SUPPORTED`,
`login.defs`. Faking them would test your fake instead of the real checks.
For example, `regular_account("root")` must be refused by the *real* UID
range.

## §8 Exercise 6

**Q8.1** The helper might act **before** it fails: run `adduser`, then fail
at chpasswd. A refusal means exit ≠ 0 **and** no command recorded **and** no
file changed.

**Q8.2**
- (a) The keyboard file: every `XKB…=` line is a quoted plain word list.
- (b) chpasswd: exactly one line, starting with `name:`.
- (c) adduser: the word after `--comment` isn't option-like, and the
  account name comes after `--`.

**Q8.4** The reference's four: `--system` and `--add-extra-groups` (Q6.5),
the option-like package (Q6.9), `²` (Q6.12). If you missed one, the question
named is where it was hiding.

**Q8.5** `read_password()` reads only the **first line**: the password is
`pw` and `root:owned` is never read. The `\n` check doesn't even fire. That's
safe, but for a different reason than "newlines are refused". If someone
later changes `readline()` to `read()`, the newline check becomes the only
defence. Your test should keep checking the *result* (one chpasswd line),
not which line of code did the work.

## §9 Exercise 7

**Q9.1** Rules that hold for every verb:
- no uncaught exception
- no argv word that starts with `-` unless the helper itself wrote it
- no control characters in argv
- a program's stdin is exactly one line
- a new line in a written file has no control characters and no unquoted
  shell syntax

Also good: no write outside the listed paths, and a refused call changes nothing.

**Q9.2** Start from **valid** calls (seeds) and change **one** thing at a
time with payloads chosen for this kind of program (grammar-aware
mutation). Random bytes almost never pass `VERBS` lookup or the first check,
so they never reach the deep code.

**Q9.3** With the rule exactly as written, Hypothesis shrinks to the shortest
violation: **`-`**, the single dash. That's the false positive from Q9.5. So
shrinking also tests *your rule*. Refine it to "starts with `-` and is
longer than 1" (or ask the real parser), and the next smallest failure is
a short option-like word such as `-0` or `--`.

**Q9.4** The trailing newline in a user name (`"fuzzann\n"`, **F-2**). The
hand case `"ann\nroot"` has text **after** the newline, and `$` only allows
a newline at the very end. A small difference that a person rarely thinks
of and a fuzzer tries for free.

**Q9.5** Ask the real parser. The Getopt::Long test in hints Q6.5 with a
full name `-` gives `comment=[-]`: a lone `-` is a value, not an option. So
it's a false positive. Note it as "checked, not a problem", and decide
whether refusing a leading `-` in full names is still worth it (it is, and
it's cheap).

## §10 Exercise 8

**Q10.1** In the user namespace your uid is mapped to 0, but "root" there has
capabilities only over things the namespace owns. The real `/etc/passwd`
belongs to the real root, who isn't mapped, so it appears to be owned by
`nobody` and writes fail. The bind mounts change `/etc` only inside the
script's private mount namespace. The limits: only one uid is mapped (a
regular account's `chown` fails), PAM-based tools fail (chpasswd), and
there is no real logind, polkit or greetd.

**Q10.2** `/usr/sbin/nologin`. `accounts()` keeps only UID 1000–60000
(`login.defs` `UID_MIN`/`UID_MAX`), so a system account (UID 100–999) is
never listed.

**Q10.3** adduser creates `labnl` (no newline), and `userdel 'labnl\n'` says
the user doesn't exist. The account stays. In the helper, chpasswd fails
first, the cleanup userdel fails, the error is swallowed, and the caller sees
an error while an orphan account (password disabled, home created on a real
system) remains.

**Q10.4** *Expected* results:

| # | Expected |
|---|---|
| 1 | asked |
| 2, 3, 4 | not asked: same login session |
| 5 | refused or asked: a systemd user service is not in the login session, and has no agent |
| 6 | asked: the keep is per action |
| 7 | asked: a different session |
| 8 | asked |

`pkcheck --list-temp` should name a **unix-session** as the subject. polkit
ties a kept authorization to the session, because pkexec's caller is usually
a short-lived process. So a browser extension or anything started from the
desktop *can* reuse it. A cron job or a systemd user service, which run
outside the session, can't.

**Q10.5**
- **For** keeping it: the Users page does several things in a row; the
  person just proved they are there; Debian's accountsservice uses
  `auth_admin_keep` for `user-administration` too; malware in an
  administrator's session has other ways to get root.
- **Against:** account changes are exactly what malware wants, and they
  last; one extra password prompt on a page people rarely use costs little.

The reference moves the verbs that change who can get in or what gets
installed to `auth_admin`. The user notices a second prompt only when they
make two such changes within five minutes.

**Q10.6** *Expected:* yes. polkit's administrators are the members of
`sudo`, and the dialog offers `ghost`. A correct password makes `ghost` a
working administrator for every polkit action and for `pkexec bash`, even
though it can't log in and Settings never shows it. Revert the snapshot.

## §11 Exercise 9

**Q11.1** No caller data reaches the file: argv must be exactly one of three
verbs, and each writes a fixed value (`yes`, `no`, today's date). `off` with
`yes` is safe for the reasons in Q3.4. It would become unsafe if a verb took
a value (`installed DATE`) or wrote anything from the caller.

**Q11.2** The input is `getent group autologin`, through NSS, so possibly
LDAP or SSSD and not only `/etc/group`. Stranger names can come from
`useradd --badname`, `adduser --allow-bad-names`, Samba machine accounts
(`name$`), a directory service, or a hand-edited `/etc/group`. A `"`
closes the TOML string. A name like `x"\ncommand = "…` would add keys or
make greetd's config invalid: at best greetd fails (no login screen), at
worst it runs a different command for the session. The `case` filter allows
only `[A-Za-z0-9._-]`, so neither can happen.

**Q11.3** One file is trusted by setupcon and console-setup (root), the
greeter (`_greetd`), flickos-session (every user) and flickos-control. That's
at least five programs and three kinds of user. What keeps it safe is
whatever **writes** it: control-helper's `check_keyboard()`, the installer
(Calamares) and Debian's `dpkg-reconfigure keyboard-configuration`. A file
read by a shell is code. Treat every writer of such a file as writing code.

**Q11.4** countme-helper's `VERBS` maps to **data tuples**, not functions,
so a sinks tool must fall back to `main()`. greetd-config is **sh** with
no verbs, so the Python tools don't apply: use shellcheck and read it. The
lesson is that tools encode assumptions. Write them down in the tool's
docstring, so the next auditor knows what it can't see.

## §12 Exercise 10

**Q12.1** See `reference/findings.md` for one set of ratings and chains. The
important habit is the one-line precondition: "needs: an administrator's
authorization (or its 5-minute keep)".

**Q12.2 and Q12.3** Your own. If you rated F-1 Medium on its own, that's
defensible: concealment from the system's own UI has real value to an
attacker. Write the argument down.

**Q12.4** The fixes are one line each. F-1:
`["adduser", "--quiet", "--disabled-password", f"--comment={full_name}", "--", name]`,
plus refusing a leading `-` in `check_full_name`. F-2:
`USER_NAME.fullmatch(name)`. Then both reference scripts report the cases as
`ok`. In a real fix, follow the FlickOS process: `dch -i`, tests in
`tests/test_control.py`, and the same change in flickos-control's dialog
checks (`full_name_problem`, `user_name_problem`).
