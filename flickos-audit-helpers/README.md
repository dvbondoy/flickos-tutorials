# Auditing FlickOS's privileged helpers

> Set `TUTORIALS` to the root of the [tutorials repository](https://github.com/dvbondoy/flickos-tutorials) and `FLICKOS` to your clone of [FlickOS](https://github.com/dvbondoy/FlickOS). Paths below use those two variables. The scripts read the FlickOS checkout from `FLICKOS` (default `~/Documents/Projects/FlickOS`).

This is the first part of a FlickOS security audit: **the programs that run
as root on a user's behalf.** In Settings, the user clicks something, a
password dialog appears, and a small helper program runs as root and changes
the system. Of all the code in FlickOS, this is where a mistake is most
likely to become "a user became root" or "a user got around the password".

You'll audit it the way a professional does: map the attack surface, model
the attacker, find every place where input becomes action, read the code
behind each one, then **prove** what you suspect with tests that never touch
your real system. Along the way you'll build five small tools, each one
first on your own and then compared with a reference version.

**Who this is for:** someone with a security degree who knows what privilege
escalation, injection and a threat model are, but hasn't audited a real Linux
program yet. You need to read Python and sh. You don't need to know FlickOS.

- **Time:** 8 to 12 hours over several sittings. The questions are most of
  the work, so don't rush them.
- **What it touches:** a `work/` folder here and temporary folders in `/tmp`.
  Steps that need real root say so and run in a **test VM**. Nothing in this
  guide runs a helper as root on your own computer.

## How this guide works (read this first)

Every exercise has the same four parts:

1. **Think first.** Questions to answer in `work/notes.md` *before* you look
   at code or run anything. Write a real answer, even if it's a guess:
   a prediction you wrote down and got wrong teaches you more than one you
   only half-thought.
2. **Build.** A spec for a script: what it takes, what it prints, and how you
   know it works (acceptance checks). Write it yourself in `work/`.
3. **Stuck?** `hints.md` has three hints per exercise, from a nudge to almost
   the answer. Take one at a time.
4. **Compare.** Only after your version passes its checks, open the
   reference in `reference/` and the answers in `answers.md`. Write down one
   thing yours does better and one thing it missed.

Each exercise also names an **existing tool** that does part of the job, or a
way to do it by hand. Professionals use tools when they fit. Building your
own once shows you what the tool can and can't see.

> **The honesty rule.** The reference answers were written by someone who
> already audited this code. They are not the only right answers. If your
> reasoning differs and holds up, keep it. If you find something
> `reference/findings.md` doesn't list, you did better than the reference.

## What's in this folder

| Path | What it is |
|---|---|
| `README.md` | This guide |
| `hints.md` | Three graded hints per exercise |
| `answers.md` | Answers to every **Q** question (spoilers) |
| `findings-template.md` | The report you'll fill in (copy it to `work/`) |
| `tools/userns-lab.sh` | Given, not an exercise: runs real `adduser`/`userdel` as a fake root against a copy of `/etc` |
| `reference/surface-map.py` | Exercise 1: the privileged attack surface from the source tree |
| `reference/sinks.py` | Exercise 3: every program and file write each verb can reach |
| `reference/harness.py` | Exercise 5: runs a helper as fake root, records instead of executing, blocks escapes |
| `reference/attack.py` | Exercise 6: 39 hostile inputs with expected outcomes |
| `reference/fuzz.py` | Exercise 7: mutation fuzzer with five safety rules |
| `reference/keep-probe.sh` | Exercise 8: how far one password reaches |
| `reference/findings.md` | The reference audit report |
| `work/` | Yours (git-ignored): notes, scripts, report |

## Contents

0. [Background: helpers, pkexec and polkit](#0-background-helpers-pkexec-and-polkit)
1. [Set up](#1-set-up)
2. [Threat model (no code)](#2-threat-model-no-code)
3. [Exercise 1: map the attack surface](#3-exercise-1-map-the-attack-surface)
4. [Exercise 2: what pkexec hands the helper](#4-exercise-2-what-pkexec-hands-the-helper)
5. [Exercise 3: find the sinks](#5-exercise-3-find-the-sinks)
6. [Exercise 4: trace every argument by hand](#6-exercise-4-trace-every-argument-by-hand)
7. [Exercise 5: a harness that can't hurt you](#7-exercise-5-a-harness-that-cant-hurt-you)
8. [Exercise 6: an attack table](#8-exercise-6-an-attack-table)
9. [Exercise 7: a fuzzer with rules](#9-exercise-7-a-fuzzer-with-rules)
10. [Exercise 8: prove it on real programs](#10-exercise-8-prove-it-on-real-programs)
11. [Exercise 9: the other two helpers](#11-exercise-9-the-other-two-helpers)
12. [Exercise 10: rate, report, compare](#12-exercise-10-rate-report-compare)
13. [A checklist you can reuse](#13-a-checklist-you-can-reuse)

---

## 0. Background: helpers, pkexec and polkit

A desktop program like Settings (`flickos-control`) runs as **you**. It can't
write `/etc/default/keyboard` or add a user. So it runs a *helper* as root:

```
Settings window (you, uid 1000)
   │  pkexec /usr/libexec/flickos/control-helper user-add ann "Ann Lee" no
   ▼
pkexec (setuid root)  ── asks polkitd ──►  polkitd: which action is this? who may do it?
   │                                         └─ the password dialog (polkit agent)
   ▼  (only if allowed)
control-helper (root) ──► adduser, chpasswd, usermod, files in /etc
```

The pieces:

- **pkexec** is a setuid-root program that runs another program as root if
  polkit allows it. It clears the environment first, and it sets
  `PKEXEC_UID` to the uid of whoever called it.
- **polkit** decides. A helper ships an **action** file
  (`/usr/share/polkit-1/actions/*.policy`). Each action says which program
  and which first argument it covers (`org.freedesktop.policykit.exec.path`
  and `…exec.argv1` annotations), and what to ask for in each situation:
  - `allow_active`: the person at the computer (a local, active session)
  - `allow_inactive`: a local session that isn't in front (another VT)
  - `allow_any`: anyone else, such as an ssh login
  - answers: `no`, `yes` (no password), `auth_self` (your own password),
    `auth_admin` (an administrator's password), and the `_keep` forms,
    which remember the answer for a few minutes.
- **The helper** is where FlickOS's own code runs as root. pkexec and
  polkit check *who* may run it. **They don't check the arguments.** That is
  entirely the helper's job.

Read the warning in the pkexec manual yourself:

```sh
man pkexec | col -b | sed -n '/SECURITY NOTES/,/ACTION AND/p'
```

Keep its last paragraph in mind for the whole guide. pkexec has had its own
serious bugs too: look up **CVE-2021-4034 ("PwnKit")**, a local root in pkexec
itself from 2009 to 2022. Your helper sits on top of that code, so keeping
polkit updated is part of the defence, even though it isn't FlickOS's code.

> **Q0.1** In one sentence each: what does polkit protect against, and what
> does it *not* protect against, for a pkexec helper?
>
> **Q0.2** A helper verb has `allow_active = yes`. Who can run it, with what
> arguments, without any password? What does that mean for how carefully its
> input must be checked?

---

## 1. Set up

```sh
export TUTORIALS=~/Documents/flickos-tutorials FLICKOS=~/Documents/Projects/FlickOS
cd "$TUTORIALS/flickos-audit-helpers"
mkdir -p work && cp findings-template.md work/findings.md && touch work/notes.md
git -C "$FLICKOS" log --oneline -1      # write the commit you audit at the top of work/findings.md
```

Every audit names the exact version it looked at. Code changes, and a report
without a commit is a report about nothing in particular.

Optional tools (you'll be told when each is useful):

```sh
sudo apt install bandit shellcheck strace python3-hypothesis
```

- **bandit**: static checks for Python security patterns
- **shellcheck**: static checks for sh scripts
- **strace**: shows which programs a process really starts
- **hypothesis**: property-based testing, a ready-made alternative to the
  fuzzer you'll write

**A test VM** for exercise 8: install FlickOS in QEMU with
`$FLICKOS/tools/test-iso.sh --install`, then start it with `--disk`. Take a
qcow2 snapshot before you break anything. `$TUTORIALS/flickos-ship-tutorial`
explains both steps. You only need the VM from exercise 8 on.

---

## 2. Threat model (no code)

Don't open the helper yet. Write a threat model in `work/notes.md`: what you
protect, from whom, and where the boundaries are. Use what you know from
section 0 and the one-line description of each verb:

```sh
sed -n '2,105p' "$FLICKOS/packages/flickos-control/usr/libexec/flickos/control-helper"
```

(That is the helper's docstring: its own description of its 17 verbs. Read it
as a *claim* that you will check, not as fact.)

> **Q2.1 Assets.** List at least five things on a FlickOS computer that these
> verbs could damage if they misbehaved. Think beyond "root": who can log in,
> what updates install, what the firewall lets through.
>
> **Q2.2 Attackers.** For each of these, say what they can already do and
> what they'd want from the helper:
> - **A1**: a standard (non-admin) user at the keyboard
> - **A2**: malware running as an *administrator's* account, inside their
>   desktop session (a bad browser extension, a malicious script)
> - **A3**: someone on the same Wi-Fi
> - **A4**: whoever controls the FlickOS apt repository
>
> **Q2.3** Which of A1–A4 is this audit actually about, and why can you set
> the others aside *for this part*? (Setting aside isn't ignoring: write where
> each one belongs.)
>
> **Q2.4 Trust boundaries.** Mark every place where data crosses from "less
> trusted" to "more trusted". There are more than the command line. Think about
> standard input, the environment, files the helper *reads*, and files that
> *other* root programs read after the helper writes them.

Compare with `answers.md` §2 before going on: the rest of the guide builds on
this model.

---

## 3. Exercise 1: map the attack surface

Before you review code, you need the list of everything that runs with
privilege. A bug in a program that isn't on your list never gets reviewed.

### Think first

> **Q3.1** List every way a *package* can make code run as root on a Debian
> system without any user typing `sudo`. Aim for at least six mechanisms.
> (Start with "pkexec helper" and "dpkg maintainer script".)
>
> **Q3.2** Your script will read helper source files to find their verbs.
> Why should it **parse** them (Python's `ast`) instead of **importing** them,
> even though importing is easier?
>
> **Q3.3** A helper has a verb that no polkit action names in its `exec.argv1`.
> What happens when someone runs `pkexec HELPER that-verb`? Find the answer
> in `man pkexec` before you guess.

### Build: `work/surface-map.py`

**Input:** the FlickOS checkout (argument or `$FLICKOS`).

**Output, part 1:** for every program named in a polkit action's
`exec.path`: the program's file in the tree, and one row per **verb** with
its action id, `allow_active`, and a note. Flag:
- `yes` (no password at all) and `*_keep` (password remembered)
- a verb with no action of its own (what does Q3.3 say happens then?)
- an action whose `argv1` isn't a verb of the helper (dead or mistyped)
- an `allow_any` weaker than `auth_admin` (who is "any"?)

**Output, part 2:** every *other* root entry point the packages ship, one row
each with what runs and as which user: the mechanisms from Q3.1 that you can
find as files under `packages/*/`.

**Acceptance checks:**
- It finds both helpers and all 17 control-helper verbs and 3 countme verbs.
- It lists the verbs that have no action of their own (there are three).
- Part 2 finds greetd's `ExecStartPre` and shows it runs as root, and shows
  that the countme service does *not*.
- It ignores build output (`packages/.build/`, `packages/*/debian/PKGNAME/`).
- It never imports or executes anything from the tree.

### Tool or by hand

On an installed system, polkit tells you directly:

```sh
pkaction --verbose --action-id org.flickos.control.user-add
pkaction | grep flickos
```

For part 2, `grep -rn 'ExecStart\|User=' packages/*/usr/lib/systemd packages/*/debian/*.service`
and `ls packages/*/debian/*.{preinst,postinst,prerm,postrm}` get you most of the
way. Your script is still worth having: it runs on every commit, and a
`grep` you run by hand only when you remember to.

### Compare

```sh
python3 reference/surface-map.py
```

> **Q3.4** One policy gives `allow_active = yes`. Is that a problem? Decide
> from what that verb takes as input, not from the word "yes".
>
> **Q3.5** Every control-helper action is `auth_admin_keep`. Write down what
> you *think* "keep" covers: the same terminal? any program in your session?
> other actions? You'll measure it in exercise 8. Keep your prediction.

---

## 4. Exercise 2: what pkexec hands the helper

Your helper calls `gpasswd`, `adduser` and `systemctl` by bare name. Whether
that is safe depends on an environment you haven't seen yet, so look at it.

### Think first

> **Q4.1** Predict the output of this, line by line: which of your variables
> survive, what `PATH` is, and what `PKEXEC_UID` is:
> ```sh
> FOO=bar PKEXEC_UID=0 LD_PRELOAD=/tmp/nothing.so PATH=/tmp/evil:$PATH pkexec /usr/bin/env
> ```
> **Q4.2** Which directory is the helper's current directory? Does the helper
> ever use a relative path? (`grep -n "open(\|glob\|mkstemp" …control-helper`)

### Do it

Run the command from Q4.1 on your own computer. It asks for your password and
runs `env` as root, which only prints. Then run `pkexec /usr/bin/pwd`.

> **Q4.3** Compare with your prediction. Which line surprised you?
>
> **Q4.4** `calling_user()` trusts `PKEXEC_UID`. Name a way to run the helper
> as root where a caller *could* choose `PKEXEC_UID`. Does it matter? (Who
> is the caller in that case?)
>
> **Q4.5** bandit (exercise 3) will warn "starting a process with a partial
> executable path" for `gpasswd`. Using what you just saw, write the
> one-sentence argument for why it's safe here, and the one condition under
> which it stops being safe.

No script to build here: this exercise is an experiment. Record the output in
`work/notes.md`, since it's evidence for your report.

---

## 5. Exercise 3: find the sinks

A **source** is where untrusted data enters (argv, stdin, environment, files
others can write). A **sink** is where data causes an effect (a program
started, a file written, a permission changed). Security review is mostly
*source-to-sink tracing*: for each sink, where does each piece of its data
come from, and what checked it on the way?

### Think first

> **Q5.1** Name the sink types in this helper you expect to matter most, and
> for each the *kind* of bug it invites (for a program started with a list
> argv and no shell, what can still go wrong?).
>
> **Q5.2** The helper wraps `subprocess.run` in `run_tool()`, `gpasswd()`,
> `ufw()`. Why does that make a naive "grep for subprocess.run" useless?

### Build: `work/sinks.py`

**Input:** a helper's path, optionally one verb.

**Output:** for each verb (from its `VERBS` table), every sink reachable from
its handler function: line number, function, the call, and, for programs, the
argv with **constants and non-constants told apart** (the reference writes
`<name>` for a non-constant). Mark each sink that receives a non-constant
value, since those are your review list.

**Requirements that make it useful:**
- Follow calls into the module's own functions (a call graph), including
  functions passed as values (`simulate=simulate`).
- Detect **wrappers**: a function whose parameter reaches a sink. Its call
  sites are sinks too, shown with *their* arguments.
- Handle `f(*args)` wrappers: every argument of the call is an argv item.

**Acceptance checks:**
- `user-add` shows four account-tool calls (`adduser`, `chpasswd`, `usermod`,
  `userdel`), with chpasswd's stdin `f'{name}:{password}\n'`.
- `autologin-on` shows `gpasswd ['-M' <user> <AUTOLOGIN_GROUP>]`, not a
  confused stdin.
- `firewall-on` shows its ufw call, and `keyboard` shows the file write.
- It runs on `countme-helper` without crashing. (Its `VERBS` holds data, not
  functions: what should your script do then?)

### Tool: bandit

```sh
bandit -q "$FLICKOS/packages/flickos-control/usr/libexec/flickos/control-helper"
```

> **Q5.3** bandit reports 14 issues, all "Low". Sort them into "already
> known safe from exercise 2", "needs a look", and "noise". Which line that
> *your* script marks does bandit not mention at all?
>
> **Q5.4** In one sentence: what kind of bug can pattern-based tools like
> bandit or semgrep find, and what kind can't they?

### Compare

```sh
python3 reference/sinks.py "$FLICKOS/packages/flickos-control/usr/libexec/flickos/control-helper"
```

Count the `!` lines. That's your work list for exercise 4.

---

## 6. Exercise 4: trace every argument by hand

This is the core of the audit, and there's no script for it. For every `!`
line, trace each non-constant value **backwards** to its source and write down
every check it passes through. Then ask: *what input passes all those checks
and still does something the author didn't intend?*

Make a table in `work/notes.md`:

| Verb | Sink (line) | Value | Source | Checks on the way | What gets through? | Who reads the result later? |
|---|---|---|---|---|---|---|

The last column matters: a file written now and read later by another root
program is a sink that fires *later*.

Work through these groups. Each has questions to answer **from the code**.
Quote line numbers in your answers.

### 6.1 keyboard: a file that root shells read

> **Q6.1** Find every program on your system that reads
> `/etc/default/keyboard` and how it reads it:
> `grep -rln /etc/default/keyboard /usr/bin /usr/sbin /lib/console-setup`.
> Which of them run as root, and when? What does the helper itself run right
> after writing the file?
>
> **Q6.2** `rewrite()` writes `XKBLAYOUT="<value>"`. What value would turn
> that into code? What in `cmd_keyboard` stops it? The defence assumes
> something about a file *the helper doesn't own*. What exactly, and how
> would you verify the assumption on this system? (Verify it.)

### 6.2 Accounts: adduser, chpasswd, usermod, userdel

> **Q6.3** chpasswd reads `name:password` lines. List three password inputs
> that could make it change *another* account, and show which line of the
> helper stops each one. Why is the password given on stdin and not as an
> argument?
>
> **Q6.4** `USER_NAME = re.compile(r"^[a-z][-a-z0-9_]{0,31}$")`, used with
> `.match()`. Is there any string that matches and is not a plain user name?
> Check the Python `re` documentation for `$` very carefully, then test it in
> `python3`.
>
> **Q6.5** The full name goes to adduser as the word after `--comment`. The
> helper refuses `: , = \` and control characters. Open `/usr/sbin/adduser`
> and find how `--comment` is declared (`grep -n "comment" /usr/sbin/adduser | head`).
> Then read about that kind of option in `perldoc Getopt::Long` (search for
> "optional"). What happens if the full name starts with `--`? Write a
> three-line Perl test that proves your answer *without* running adduser.
>
> **Q6.6** `user-remove` checks "not logged in" and "not the last
> administrator", then acts. What can change between the check and the act?
> Does it matter here? (Look up *TOCTOU*.)

### 6.3 autologin

> **Q6.7** Who decides which user is logged in automatically at boot? Trace it
> from `cmd_autologin_on` to the program that reads the result
> (`$FLICKOS/packages/flickos-greeter/`). Can the caller choose *which* user?

### 6.4 Fixed-choice verbs

> **Q6.8** For `power`, `updates`, `firewall-on|off|phones`, `firefox-memory`,
> `locale-add`: confirm that every caller value is compared with a fixed list
> **before** it's used. One of them compares against a list read from a file:
> which, and who can write that file?

### 6.5 packages-undo: data from a log

> **Q6.9** Where do the package names that reach `apt-get` come from? Who can
> write that source? Does `PACKAGE_ITEM` accept a "name" starting with `-`?
> Test whether apt-get treats a word after `remove` as an option:
> `apt-get -s remove -oDebug::NoLocking=1 hello` vs
> `apt-get -s remove -- -oDebug::NoLocking=1` (as yourself; `-s` only simulates).
>
> **Q6.10** The plan is checked with `apt-get -s`, then the real `apt-get -y`
> runs. What could make the real run do more than the simulation showed? Is
> there an apt-get option that would make it refuse instead? (`man apt-get`)

### 6.6 Plumbing

> **Q6.11** `write_atomic()`: the temp file is created where, with what mode,
> and what does `os.replace` do if the target is a symlink? Under what
> folder permissions would this be unsafe? Are any of the helper's folders
> like that?
>
> **Q6.12** `main()` catches three exception types. Find an input to a verb
> that raises something else. (Hint: `str.isdigit()` and `int()` don't agree
> on everything.) Is a traceback from a root helper a security problem?

When you've finished the table, you should have **suspicions**: places where
you believe something gets through. The next three exercises turn suspicions
into proof (or into "checked, it holds", which is just as useful).

---

## 7. Exercise 5: a harness that can't hurt you

To test a root helper you need to run it as root, which is dangerous on your
own computer and slow in a VM. Instead, run its Python code in-process and
**fake** the dangerous parts.

### Think first

> **Q7.1** List everything the harness has to fake or redirect so that
> `main(["user-add", …])` runs *as if* root, but changes nothing real. (Read
> the helper's constants at the top: what kinds of paths are there?)
>
> **Q7.2** Your harness will have bugs. How do you make sure a harness bug
> can't turn into "the test changed my real `/etc`" or "the test really ran
> `userdel`"? You want a guard that doesn't depend on the harness being right.
> (Look up `sys.addaudithook`.)
>
> **Q7.3** What should the harness *not* fake, because faking it would hide
> real behaviour? (Example: does it matter if `pwd.getpwnam` reads the real
> user list?)

### Build: `work/harness.py`

A library with one class:

```python
h = Harness(path_to_helper)
result = h.run(argv, stdin="", pkexec_uid=None, responder=None, setup=None, patches=())
result.code       # main()'s return value
result.commands   # [(argv list, stdin text or None)]: what WOULD have run
result.changed    # {real path: new content or None}: what WOULD have changed
result.crashed    # traceback if main() raised something it didn't catch
```

**Requirements:**
- Load the helper with `importlib` (it has no `.py` extension).
- Redirect every path constant under `/etc`, `/var`, `/run` into a fresh temp
  "fake root" per run, copying the real file in first so reads still work.
- Replace `subprocess.run` with a recorder that returns a canned answer
  (`responder(argv, stdin) -> (code, stdout, stderr)`). Watch out for
  `check=True`, `text=True` and bytes.
- Make `os.geteuid()` return 0 and set `PKEXEC_UID`.
- **Guard:** an audit hook that raises on any file write outside a fake root
  and on any process start at all. It stays installed for the whole process.
- Clean up the fake root after every run.

**Acceptance checks:**
- `python3 work/harness.py HELPER keyboard pc105 us "" ""` shows the new
  keyboard file and the two commands that *would* run.
- A self-test: point `KEYBOARD_DEFAULTS` at `~/harness-canary` and run the
  keyboard verb, and the write must be **blocked** and the file must not
  exist. Call `subprocess.Popen(["true"])` from inside a run, and it must be
  **blocked**.
- After 100 runs, `ls /tmp | grep harness` is empty. (Mine wasn't the first
  time: hint 5.3 says why.)

### Tool or by hand

The repo's own unit tests (`$FLICKOS/packages/flickos-control/tests/test_control.py`,
class `HelperTest`) load the helper the same way with `unittest.mock`. Read
them for technique. For a *compiled* helper you can't import, you'd use a
VM and `strace -f -e trace=execve,openat` instead, or a container.

### Compare

```sh
python3 reference/harness.py "$FLICKOS/packages/flickos-control/usr/libexec/flickos/control-helper" --self-test
```

---

## 8. Exercise 6: an attack table

Now use the harness to test your suspicions from exercise 4, plus the inputs
every helper should survive.

### Think first

> **Q8.1** For a *refused* input, why isn't "exit code is not 0" enough
> proof? What else must be true?
>
> **Q8.2** For an *accepted* input, "exit code 0" proves nothing about safety.
> What would you check instead for (a) the keyboard file, (b) chpasswd's
> stdin, (c) adduser's argv?
>
> **Q8.3** Write your expected outcome (refuse/accept) for each case **before**
> you run the table. A case you only label after seeing the result proves
> nothing.

### Build: `work/attack.py`

A table of at least **30** cases: `(name, argv, stdin, expect, check)`, with
`expect` `"refuse"` or `"accept"`, and `check(result) -> (ok, why)` for
accepted ones. Print `ok` or `FINDING` per case and a total.

Cover at least:
- every verb with a wrong number of arguments, an unknown value, and an
  injected newline;
- shell syntax (`"`, `$( )`, `` ` ``, `;`) where a file is written;
- argument-like values (`-x`, `--something`) wherever a value reaches a program;
- your suspicions from Q6.4, Q6.5, Q6.9 and Q6.12;
- `autologin-on` with `PKEXEC_UID` missing, `0`, and `"1000 "`;
- for `packages-undo`, a **crafted** apt log placed in the fake root with
  `setup=`, and a `responder` that answers `dpkg-query` and `apt-get -s`.

### Compare

```sh
python3 reference/attack.py
```

> **Q8.4** The reference reports 4 findings. Which did you also find? For each
> one you missed, which question in exercise 4 should have led you to it?
>
> **Q8.5** The case "password with newline" (`"pw\nroot:owned\n"`) is **ok**,
> but not for the reason many people expect. Why?

---

## 9. Exercise 7: a fuzzer with rules

A table tests the inputs *you* thought of. A fuzzer makes up inputs, and an
**oracle** (a rule that must always hold) decides whether something went
wrong. A fuzzer without good rules only finds crashes.

### Think first

> **Q9.1** Write rules that must hold for **every** input to **every** verb,
> rules you can check from `result` without knowing the verb. Aim for four.
> (One is "doesn't crash".)
>
> **Q9.2** Random strings are a poor way to fuzz a program that checks its
> input first: almost all of them are refused at the first check. What should
> you start from instead, and how should you change it?

### Build: `work/fuzz.py`

- Start from one **valid** call per verb (seeds).
- Change one argument, or stdin, with a payload from a list (dashes, quotes,
  `$( )`, newline, `\r`, path traversal, very long, Unicode digits,
  right-to-left mark, empty …), placed before, after, inside or instead of
  the value.
- Check your rules on every result. Print each **distinct** problem once (by
  rule, verb, argument) with the input that caused it.
- Use a fixed random seed (`--seed`) so a result can be reproduced.

**Acceptance:** 2,000 runs in under a minute; reproducible with the same seed.

### Tool: Hypothesis

`python3-hypothesis` does this with less code: `@given(st.text())` generates
inputs, *shrinks* a failing one to the smallest example, and remembers
failures between runs. Try one property with it after your own fuzzer works:

```python
from hypothesis import given, strategies as st
@given(st.text(min_size=1, max_size=40))
def test_user_add_never_passes_options(full_name):
    r = h.run(["user-add", "fuzzann", full_name, "no"], "pw\n")
    for argv, _ in r.commands:
        assert not any(w.startswith("-") and w not in CONSTANTS for w in argv[1:])
```

> **Q9.3** Hypothesis would shrink the adduser finding to which input?

### Compare

```sh
python3 reference/fuzz.py --runs 3000 --seed 7
```

> **Q9.4** The reference fuzzer finds something attack.py's hand-written case
> missed. Which one, and why did the hand case miss it?
>
> **Q9.5** Its R2 rule reports a full name of `-` (a single dash). Is that a
> real problem? How would you decide? (This is **triage**: deciding which
> fuzzer reports are real is half the job.)

---

## 10. Exercise 8: prove it on real programs

The harness proves what the helper *would run*. It doesn't prove what adduser
*does* with it. Now check your findings against the real programs.

### 10.1 adduser in a lab (no root, no VM)

`tools/userns-lab.sh` runs commands as a fake root (a user namespace) against
a **copy** of `/etc`. Read the script first (about 60 lines) and answer:

> **Q10.1** Why can't this script change your real `/etc/passwd`, even though
> `adduser` inside it believes it is root? What are the lab's limits?

Then prove F-candidates with real tools:

```sh
tools/userns-lab.sh run 'adduser --quiet --disabled-password --comment --system labsys; getent passwd labsys'
tools/userns-lab.sh run 'usermod --append --groups sudo labsys; getent group sudo'
tools/userns-lab.sh run 'adduser --quiet --disabled-password --system --comment=--system -- labok; getent passwd labok'
tools/userns-lab.sh reset
```

> **Q10.2** What is UID 103's shell, and why would Settings > Users not show
> this account? (`accounts()` in `$FLICKOS/packages/flickos-control/usr/bin/flickos-control`.)
>
> **Q10.3** Reproduce the trailing-newline chain from Q6.4 with the real tools
> in the lab: create `labnl` followed by a newline (use `python3 -c` with
> `subprocess.run`, since the shell's `$( )` strips trailing newlines), then
> try the helper's cleanup `userdel` with the same name. What is left behind?

### 10.2 How far one password reaches (VM, or your own FlickOS)

`reference/keep-probe.sh` is given (it's an experiment, not a coding
exercise). It runs one harmless verb through pkexec and shows polkit's
temporary authorizations before and after. Read its header, then **write
down your prediction for all eight rows**, then run them:

| # | Where | Prediction: asked for password? | Result |
|---|---|---|---|
| 1 | terminal A | | |
| 2 | terminal A again | | |
| 3 | new terminal B | | |
| 4 | `setsid` background process | | |
| 5 | `systemd-run --user` service | | |
| 6 | a different action | | |
| 7 | text console (Ctrl+Alt+F2) | | |
| 8 | after 5 minutes | | |

> **Q10.4** Which process does polkit tie the "kept" authorization to? Use
> the subject that `pkcheck --list-temp` prints. Given that answer, could a
> malicious browser extension use it? Could a cron job?
>
> **Q10.5** Make the argument for keeping `auth_admin_keep` on `user-add`,
> then the argument against. Look at what Debian's own account service does:
> `grep -A3 user-administration /usr/share/polkit-1/actions/org.freedesktop.accounts.policy`.
> Which verbs would you move to `auth_admin`, and what would the user notice?

### 10.3 End to end (VM only)

In the VM, as the administrator:

```sh
printf 'Hidden1!\n' | pkexec /usr/libexec/flickos/control-helper user-add ghost --system yes
getent passwd ghost; getent group sudo
```

Open Settings > Users. Then run `pkexec true` and see which accounts the
password dialog offers.

> **Q10.6** Can you authenticate as `ghost` in that dialog? What does that
> make `ghost`? Revert the snapshot afterwards.

---

## 11. Exercise 9: the other two helpers

Re-use your tools, which is the point of having built them.

```sh
python3 work/surface-map.py
python3 work/sinks.py "$FLICKOS/packages/flickos-countme/usr/libexec/flickos/countme-helper"
python3 work/harness.py "$FLICKOS/packages/flickos-countme/usr/libexec/flickos/countme-helper" on
shellcheck "$FLICKOS"/packages/flickos-greeter/usr/libexec/flickos/*
```

> **Q11.1 countme-helper.** Can the caller put any of their own data into
> `/etc/flickos/countme`? Is `off` with `allow_active = yes` safe? What would
> make it unsafe?
>
> **Q11.2 greetd-config** runs as root before every greetd start and writes a
> TOML file. Where does its input come from? Its `case` filters the user name
> even though account names are already restricted: name a way an account
> with a stranger name could exist. What could a name containing `"` do to
> the TOML?
>
> **Q11.3 greeter** runs as `_greetd` and does `. /etc/default/keyboard`.
> Connect this to Q6.1: how many different programs, as how many users,
> trust that one file's content, and which code is the *only* thing keeping it
> safe?
>
> **Q11.4** Did your scripts need changes to handle these helpers? What
> assumptions about "a helper" did you have to drop?

---

## 12. Exercise 10: rate, report, compare

### Severity

Severity is **impact × preconditions**, not how scary the bug class sounds.
An argument injection that needs the administrator's password is less severe
than a typo that lets a standard user skip it. Use this scale:

| Severity | Means |
|---|---|
| Critical | Anyone without a password → root, or the network → code execution |
| High | A standard user → root or administrator, or into another user's data, without an administrator's password |
| Medium | Needs a realistic foothold (code running as an administrator) and gives *more* than that foothold already has: lasting or hidden access, or skipping a password prompt the design relies on |
| Low | Needs administrator rights or root-only data anyway; defence in depth; makes a later mistake exploitable |
| Info | Robustness or quality with a security angle; no attacker gain |

> **Q12.1** Rate each of your findings. For each, write the precondition in
> one line ("needs: …"). If two findings combine into something worse than
> either, write the *chain* as its own row.

### Report

Fill in `work/findings.md` from the template. Each finding needs: where (file
and line), what, a concrete scenario, evidence (the harness or lab output),
why this severity, a fix, and the regression test that would have caught it.
Add a **"Checked and found OK"** section: a reader can't tell "not checked"
from "checked and fine" unless you say.

### Compare

Now open `reference/findings.md`.

> **Q12.2** Which reference findings did you miss, and which question would
> have led you there? Which of yours aren't in the reference? Are they real?
>
> **Q12.3** Where did you rate differently? Write the strongest argument for
> your rating.
>
> **Q12.4** (Extension.) Write the fix for F-1 and F-2 in a scratch copy of
> the helper, add both as cases that must be refused, and show that
> `attack.py` and `fuzz.py` report them as `ok`. Don't change the FlickOS repo
> from this tutorial: a real fix goes through the normal package process
> (changelog bump, tests in `tests/test_control.py`, review against the HIG).

---

## 13. A checklist you can reuse

For any privileged helper, in any project:

1. **Surface:** what runs as root, started how, guarded by which rule?
   Anything with no password, or with a kept one?
2. **Environment:** what does the launcher clear and set (PATH, LD_*, cwd,
   caller identity)? Is the caller's identity taken from the launcher or
   from the caller?
3. **Sinks:** every program, file write, permission change. Wrappers too.
4. **Each non-constant value:** source → checks → sink. Allowlist or
   denylist? Does the check match the whole value (`fullmatch`, not `$`)?
5. **Argument injection:** can a value start with `-`? Is there a `--`, or
   is the value attached (`--opt=value`)? How does *that* program parse
   options (optional values!)?
6. **Line injection:** can a value contain `\n` or `\r` where lines are
   records (chpasswd, config files, TOML, logs)?
7. **Later readers:** who reads the files you write, as whom, and how (sourced
   by a shell? parsed as TOML?)?
8. **Races:** check-then-act on users, groups, files, or the package state.
9. **Errors:** does a failure leave the system half-changed? Does cleanup use
   the same value the action did?
10. **Prove it:** a harness that records, a lab or VM for the real tools, and
    a regression test per finding.

Next part of the audit: **flickos-phone**, which listens on the network
and is the main remote attack surface.
