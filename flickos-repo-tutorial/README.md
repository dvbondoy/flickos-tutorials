# Bringing a package into FlickOS, step by step

> Set `TUTORIALS` to the root of the [tutorials repository](https://github.com/dvbondoy/flickos-tutorials) and `FLICKOS` to your clone of [FlickOS](https://github.com/dvbondoy/FlickOS). Paths below use those two variables. Scripts read the FlickOS checkout from `FLICKOS_REPO` or `FLICKOS`.

This covers the stages of the path from idea to release that the other
tutorials only mentioned:

- **3, the design doc:** write down what you'll build and why, before the code.
- **4, the HIG review of the design:** find what the rules require while it's
  still cheap to change.
- **8, wiring it in:** every other place in the repo that has to know about a
  new package.
- **9, documenting it.**
- **10, committing it.**

The example is **flickos-hello** 2.0 from the code tutorial. By the end, a
copy of the FlickOS repo has it as a real FlickOS package:
- a design doc, `docs/design/flickos-hello.md`, first proposed, then accepted
  with measurements;
- flickos-hello 2.1, which records its changes for *Settings → History*;
- flickos-control 1.20, with a *Hello* tile and Hello's changes in History;
- flickos-desktop 1.22, which recommends it;
- three boot-test checks, tried in the live ISO;
- docs 01, 04 and 09 and CLAUDE.md updated;
- two commits, the way the repo's own history does it.

The review in step 3 finds three things the code tutorial left out. Two of
them mean changing another package (flickos-control). That's normal: most
FlickOS features touch more than one package.

Every command here was run while writing this guide, and the outputs shown are
the real ones.

- **Time:** 3 to 4 hours.
- **What it touches:** a **copy** of the repo in `practice/`, with nothing to
  push to. Your real repo, your apt repo and your desktop's settings are never
  changed. Step 10 boots the live ISO in a VM and uses the ship tutorial's
  throwaway local apt repo, which you delete at the end.

## Where this fits

| # | Stage | Tutorial |
|---|---|---|
| 1–2 | Idea, spike | `flickos-snip-spike`, `flickos-spike-kit` |
| **3–4** | **Design doc, HIG review** | **here** |
| 5 | Code + unit tests | `flickos-code-tutorial` |
| 6 | The .deb | `flickos-deb-tutorial` |
| 7 | Tests: own desktop, headless labwc, QEMU, boot test | `flickos-headless-labwc`, `flickos-ship-tutorial` |
| **8–10** | **Wire it in, document it, commit it** | **here** |
| 11–13 | Upgrade test, publish, release | `flickos-ship-tutorial` |

## What's in this folder

| Path | What it is |
|---|---|
| `README.md` | This guide |
| `check-wiring.py` | Checks that a package is wired in everywhere HIG PKG-10 asks for: debian files, who installs it, `REQUIRED`, the boot test, docs 01 and 04, CLAUDE.md, a design doc. Works on **any** package, in any clone |
| `try-checks.py` | Turns boot-test checks into a script for the ship tutorial's `vm-run.py`, so a new check runs in the live ISO before any ISO contains your package |
| `finished/0001-…patch`, `0002-…patch` | The answer key: the two commits, as `git format-patch` wrote them |
| `finished/flickos-hello-design.md` | The finished design doc, to read on its own |
| `practice/` | Made by you in step 1: your copy of the repo |

## Contents

0. [The one rule: nothing leaves practice/](#0-the-one-rule-nothing-leaves-practice)
1. [A practice copy of the repo](#1-a-practice-copy-of-the-repo)
2. [Stage 3: the design doc](#2-stage-3-the-design-doc)
3. [Stage 4: reviewing the design against the HIG](#3-stage-4-reviewing-the-design-against-the-hig)
4. [The first commit: the design alone](#4-the-first-commit-the-design-alone)
5. [The package goes in, and learns History](#5-the-package-goes-in-and-learns-history)
6. [flickos-control learns about Hello](#6-flickos-control-learns-about-hello)
7. [flickos-desktop, REQUIRED and the menus](#7-flickos-desktop-required-and-the-menus)
8. [Boot-test checks](#8-boot-test-checks)
9. [Build everything, run the repo's checks](#9-build-everything-run-the-repos-checks)
10. [Try the checks in the live ISO](#10-try-the-checks-in-the-live-iso)
11. [Stage 9: the docs](#11-stage-9-the-docs)
12. [Stage 10: the second commit](#12-stage-10-the-second-commit)
13. [Compare with the answer key](#13-compare-with-the-answer-key)
14. [What check-wiring.py found in the real repo](#14-what-check-wiringpy-found-in-the-real-repo)
15. [Doing it for real](#15-doing-it-for-real)
16. [Traps](#16-traps)
17. [Cheat sheet](#17-cheat-sheet)
18. [Clean up](#18-clean-up)

---

## 0. The one rule: nothing leaves practice/

You'll commit twice, and that's the point: committing is stage 10. What makes
this safe is that the commits land in a **copy** that has nowhere to push to.

| Kept safe | How |
|---|---|
| Your real repo, and its uncommitted work | You work in a clone. A clone has its own history, branches and working files |
| GitHub | The clone's remote is deleted in step 1, so `git push` has nowhere to go |
| Your apt repo | `repo/publish.sh` and `upload.sh` are never run. Step 10 uses the ship tutorial's local repo on 127.0.0.1 |
| Your desktop's settings and History | Everything runs with throwaway `XDG_CONFIG_HOME`/`XDG_STATE_HOME` folders, and the boot-test checks run only in the VM |

## 1. A practice copy of the repo

```sh
cd $TUTORIALS/flickos-repo-tutorial
git clone $FLICKOS practice
cd practice
git remote -v
```

```
origin	$FLICKOS (fetch)
origin	$FLICKOS (push)
```

A clone remembers where it came from as the remote `origin`. A `git push`
from here would go into your real repo, so remove it:

```sh
git remote remove origin
git remote -v              # prints nothing: there's nowhere to push
git log --oneline -1
```

This guide was written from `d10cde8 add super+1-4 shorcut for virtual
desktops`. If your repo has moved on since, everything still works, except
that version numbers may come out different and step 13's comparison needs a
little care.

**Why not a branch or a worktree in the real repo?** Both share the real
repo's `.git`: its branches, its stash, its remote. A practice branch could
get pushed, and a `git stash` there could sweep up your real uncommitted
work. A clone shares nothing. (A clone of a local path hard-links git's object
files to save space. That's safe: git never changes an object once written.)

**Only committed work is copied.** Your uncommitted changes in the real repo
(`git status` there) are not in `practice/`. That's what you want: a clean
starting point.

Check that `dch` will sign your entries with your name:

```sh
echo "$DEBFULLNAME <$DEBEMAIL>"     # Jon <dvbondoy@gmail.com>
```

## 2. Stage 3: the design doc

A design doc is written **before** the code, for three readers:
- **you, now:** writing the decisions down shows the ones you haven't made;
- **a reviewer:** it can be read and argued with before a line of code
  exists;
- **you in a year:** it says *why* things are the way they are, so nobody
  "fixes" a decision without knowing its reason.

### Read one first

```sh
less docs/design/flickos-menu.md
grep -n '^#' docs/design/*.md | less
```

Every design doc in the repo has the same five parts:

| Part | What goes in it |
|---|---|
| **Status** line | Proposed, Accepted or Rejected, the date, and later which package versions did which phase. A reader knows at once whether it's built |
| **1. Problem** | What's wrong today, for whom, in facts: numbers, names, file paths. No solution yet |
| **2. Goals and non-goals** | What it will do, and just as important, what it won't. Non-goals stop a feature from growing |
| **3. Decisions (ADRs)** | One heading per decision: **Decision**, then **Why**, then **Alternatives rejected** with the reason for each. An ADR (Architecture Decision Record) is the unit a reviewer argues with |
| **4. Phases** | Phase 0 (the spike and its measured results), then phases small enough to build and ship on their own, then **Later** |
| **5. Risks and open questions** | What could go wrong, and what you don't know yet |

The **Alternatives rejected** part matters most. flickos-menu's ADR-001
explains why it isn't nwg-menu (not in Debian, a second compiled package,
copies its config into `$HOME`). Without that paragraph, someone would
propose nwg-menu again next year.

### Write Hello's

Create `docs/design/flickos-hello.md` with the five parts. Start with:

```markdown
# Hello (flickos-hello)

**Status:** Proposed, 2026-09-28.
```

Things to get right:
- **The problem, honestly.** Hello's real reason to exist is to be the
  example: FlickOS has no small program that owns a setting. Check that with
  numbers before writing it:
  ```sh
  wc -l packages/*/usr/bin/* | sort -n
  ```
  flickos-welcome (433 lines) and flickos-shortcuts (634) own no settings;
  flick-tiler, flickos-phone, flickos-layout and flickos-control, which do,
  are 1,300 to 6,500 lines. That's the problem statement.
- **ADR-001, its own package**, with the alternatives: a card in
  flickos-welcome (Welcome owns no settings), a demo page in flickos-control
  (the Settings window only *runs* owners), only a document (nothing checks a
  document against the HIG).
- **ADR-002, the setting:** ids in a table, the conffile, the user's file,
  `default`, 1.x texts still understood. Why ids: a text can change, an id
  can't.
- **Phase 0:** no spike. Say so, and why: every part already works in
  another FlickOS program. A spike answers a question the repo can't answer.
  Put the code tutorial's measurements here.

Don't write ADR-003 to 005 yet. They come out of the review.

## 3. Stage 4: reviewing the design against the HIG

The HIG review happens twice: on the **design** (now) and on the **code**
(the code tutorial's step 12). Now is when a finding costs a paragraph
instead of a rewrite.

Go through `docs/hig/checklist.md` rule by rule, and ask for each: *does my
design already settle this?* Most rules are about code and are settled by
following the code tutorial. Three are not.

### Finding 1: INT-4, every setting can be found from Settings

```sh
grep -n -A9 '^### INT-4' docs/hig/02-desktop-integration.md
```

The greeting is a user-facing setting, so it needs a row on a Settings page,
or a **tile on More Settings when another app owns it**. Hello owns it in its
own window, so the answer is a tile. That tile lives in **flickos-control**,
another package.

Read how tiles work, and you'll find a disagreement:

```sh
grep -n -B2 -A8 '^TILES = (' packages/flickos-control/usr/bin/flickos-control
grep -n -A4 'Add a tile for another settings app' docs/09-customizing.md
```

docs/09 says a tile's app also goes into the Settings **menu** (labwc's, both
copies). But that menu lists the system's settings apps: Wallpaper, Sound,
Printers. Hello isn't one. The HIG's README says what to do when a rule or
doc and your decision disagree: **fix one of them in the same change.** Here
docs/09 changes to say "a settings app goes in the menu too". Write that down
as ADR-003, with *a Settings row* and *the Settings menu* as the rejected
alternatives.

### Finding 2: SET-4, History

```sh
grep -n -A18 '^### SET-4' docs/hig/03-settings-and-files.md
```

The last bullet: *every owner appends its changes to `history.jsonl` with its
own `record()`*. It's inside a **Must** rule, and the code tutorial's Hello
doesn't do it. The HIG's README is clear that breaking a Must needs a change
to the HIG first, not an exception. So Hello gets `record()`, and
flickos-control, which shows and undoes the changes, has to learn a new
owner. ADR-004. Its cost: two packages must be released together.

### Finding 3: PKG-4, Depends or Recommends?

```sh
grep -n -A17 '^### PKG-4' docs/hig/09-packaging.md
```

Every FlickOS program so far is a **Depends** of flickos-desktop, so it's
tempting to copy that. See what a Depends means when a user removes it (`-s`
only simulates, no root needed, nothing changes):

```sh
apt-get -s remove flickos-welcome | grep -A1 REMOVED
apt-get -s remove mousepad | grep -A1 REMOVED
```

```
The following packages will be REMOVED:
  flickos-desktop flickos-welcome
```
```
The following packages will be REMOVED:
  mousepad
```

Removing a Depends removes **flickos-desktop** with it. On your computer
autoremove wouldn't take more (the desktop's packages there are marked as
installed by hand), but without flickos-desktop the system stops getting
FlickOS's new Depends. New FlickOS programs reach installed systems only
through them. Welcome is part of the desktop, so that's fine for it. Hello is
an app a user may well remove, so it's a **Recommends** (mousepad's case).

The price, from the same rule: a Recommends **never reaches installed
systems** (`--apt-recommends false` and `00recommends`). Only new installs
get Hello; others `sudo apt install flickos-hello`. And it doesn't go in
`REQUIRED`, since the desktop works without it. ADR-005.

### Then: verification

ADR-006 says how you'll know it works, before you build it: which unit tests,
which boot-test checks, what you'll measure. Writing it now means step 8 has
a plan to follow.

Compare your design with `finished/flickos-hello-design.md`, but read only up
to *4. Phases* for now. The finished one already has phase 1's results.

## 4. The first commit: the design alone

The repo commits a design before its code (flickos-phone:
`git show --stat 45af63d`). The design can be reviewed, agreed or rejected on
its own, and a rejected design stays in the history with its reasons
(`docs/design/flickos-recap.md` was one).

```sh
git status                          # ?? docs/design/flickos-hello.md: new, not yet tracked
git add docs/design/flickos-hello.md
git diff --cached --stat            # what the commit will contain
git commit
```

`git add` puts a file in the **index** (the staging area): the next commit
is exactly what's in the index, not everything that's changed. `git diff
--cached` shows the index against the last commit, so it's the commit before
you make it.

`git commit` opens your editor for the message. The repo's style:

```
Design doc: Hello, the example program (proposed)

flickos-hello.md proposes a small package that has every part a FlickOS
program has, once: …  It is a Recommends of flickos-desktop (an app users
may remove), found from Settings through a More Settings tile rather than
the Settings menu, and it records its changes for History, so
flickos-control changes with it. No spike: every part exists already.
```

- **Subject line:** what it is, under about 70 characters, no final period.
  `git log --oneline` shows only this.
- **A blank line**, then the body: **why**, and the decisions a reader of the
  log should know about without opening the file. The diff already shows
  *what* changed.

```sh
git log --oneline -2
```

## 5. The package goes in, and learns History

```sh
cp -r $TUTORIALS/flickos-code-tutorial/finished/flickos-hello packages/
find packages/flickos-hello -name __pycache__        # must print nothing
```

(If you finished the code tutorial with your own `work/flickos-hello`, copy
that instead.)

### record(): copy it from an owner that has one

FlickOS doesn't have a shared Python library: each program is one file
(CODE-1). A new owner copies the History code from an existing one, and a
test in flickos-control (step 6) checks that they still agree. Look at
flick-tiler's:

```sh
grep -n 'HISTORY_\|^def state_home\|^def history_enabled\|^def record\|^def trim_history' packages/flick-tiler/usr/bin/flick-tiler
```

Into `packages/flickos-hello/usr/bin/flickos-hello`:

1. **Imports:** add `datetime`, `json` and `time`.
2. **Constants**, after `LOCK`:
   ```python
   # Settings → History: every change of the greeting is one JSON line appended to
   # $XDG_STATE_HOME/flickos/history.jsonl, in the format every owner shares
   # (docs/design/flickos-history.md, ADR-002). History undoes a change by running
   # `greeting set OLD`.
   HISTORY_OWNER = NAME
   HISTORY_KEY = "greeting"            # the setting's name in the history
   HISTORY_FILE = "history.jsonl"      # in $XDG_STATE_HOME/flickos
   HISTORY_LOCK = "history.lock"
   HISTORY_BYTES = 256 * 1024          # above this, the older half is dropped
   # flickos-control's: [History] Enabled=, then the user's ~/.config/flickos/history.
   HISTORY_CONF = PREFIX + "/etc/xdg/flickos/history.conf"
   DEFAULT_CHOICE = "default"          # no choice of the user's: `greeting set default`, and in the history
   ```
   Then replace every other `"default"` in the file with `DEFAULT_CHOICE`: one
   word, one constant.
3. **The four functions** `state_home`, `history_enabled`, `record`,
   `trim_history`, copied from flick-tiler under a new heading
   `# --- History ---`. `history_enabled` reads flickos-control's
   `history.conf` and then the user's `~/.config/flickos/history`: History can
   be turned off, and then no owner records anything.
4. **The call**, in `save_greeting`, which both the command and the window
   use:
   ```python
   path = user_conf()
   old = user_greeting() or DEFAULT_CHOICE
   if greeting is None:
       with contextlib.suppress(FileNotFoundError):
           os.unlink(path)
   else:
       write_atomic(path, …)                      # as before
   record(HISTORY_KEY, old, greeting or DEFAULT_CHOICE)
   ```
   `record` comes **after** the save, so a failed save (OSError) records
   nothing. `record` itself never fails the change: a history that can't be
   written is only a warning.
5. **The docstring:** one paragraph saying changes go to History (CODE-2:
   the docstring stays up to date).

### Tests, and the leak they'd cause

Add a `HistoryTest(HomeTest)` class to `tests/test_hello.py` (you'll need
`import json`):
- a change is recorded in the shared format (owner, key, old `default`, new
  `mabuhay`, a numeric id);
- `set default` records `default`;
- setting the same value twice records once;
- `Enabled=no` in the user's `history` file records nothing;
- a state folder that can't be written gives a warning, exit 0, and the
  greeting is still saved.

**Before running them**, think about where `record()` writes: it follows
`XDG_STATE_HOME`, else `~/.local/state`, and `HomeTest` fakes neither. On your
desktop the tests would add lines to **your real Settings → History**, and
read your real `/etc/xdg/flickos/history.conf`. See it without harm by
giving the tests a fake home that isn't under `/tmp` (leak-check allows
`/tmp`):

```sh
mkdir -p $TUTORIALS/flickos-repo-tutorial/fake-home
env -u XDG_STATE_HOME HOME=$HOME/Documents/flickos-repo-tutorial/fake-home \
    $TUTORIALS/flickos-code-tutorial/leak-check.py packages/flickos-hello | tail -8
```

```
test_hello.HistoryTest.test_no_change_no_record
    reads /etc/xdg/flickos/history.conf
test_hello.HistoryTest.test_no_change_no_record
    reads $TUTORIALS/flickos-repo-tutorial/fake-home/.local/state/flickos/history.lock
test_hello.HistoryTest.test_no_change_no_record
    reads $TUTORIALS/flickos-repo-tutorial/fake-home/.local/state/flickos/history.jsonl

21 host file(s)/program(s) touched
```

("reads" means *opens*: writing opens the file too.) Two leaks: the state
folder, and the host's `history.conf`. Fix both in `HomeTest.setUp`, the one
place every test goes through:

```python
environ = {"XDG_CONFIG_HOME": self.home, "XDG_STATE_HOME": os.path.join(self.root, "state")}
for patch in (mock.patch.dict(os.environ, environ),
              mock.patch.object(hello, "SYSTEM_CONF", self.system_conf),
              mock.patch.object(hello, "HISTORY_CONF", os.path.join(self.root, "etc/xdg/flickos/history.conf"))):
```

and say so in its docstring. Then:

```sh
rm -rf $TUTORIALS/flickos-repo-tutorial/fake-home; mkdir $TUTORIALS/flickos-repo-tutorial/fake-home
env -u XDG_STATE_HOME HOME=$HOME/Documents/flickos-repo-tutorial/fake-home \
    $TUTORIALS/flickos-code-tutorial/leak-check.py packages/flickos-hello | tail -3
rmdir $TUTORIALS/flickos-repo-tutorial/fake-home        # fails if anything was written there
```

```
Ran 25 tests in 0.196s

OK

nothing outside the test folders was touched
```

**The lesson:** every new path a program uses is a new path its tests must
fake. Run leak-check whenever a program starts reading or writing somewhere
new.

### Version and man page

The package's content changed, so it gets a new version (PKG-3):

```sh
cd packages/flickos-hello
dch -i -D trixie "Record every change of the greeting for Settings → History, which shows it and undoes it with greeting set OLD."
head -6 debian/changelog
cd ../..
```

```
flickos-hello (2.1) trixie; urgency=medium

  * Record every change of the greeting for Settings → History, which
    shows it and undoes it with greeting set OLD.
```

(dch's two lines about `libdistro-info-perl` are harmless: it only can't
list release names.)

Also add `~/.local/state/flickos/history.jsonl` to the man page's FILES
section in `debian/flickos-hello.1`, and change its version to 2.1. Check
with `man -l packages/flickos-hello/debian/flickos-hello.1`.

## 6. flickos-control learns about Hello

flickos-control reads everyone's History entries, but it only knows how to
*name* and *undo* the owners it has been told about. Find how an existing
owner is wired in; flickos-phone is the newest:

```sh
grep -n 'PHONE\b\|PHONE_HISTORY_KEYS\|(PHONE,' packages/flickos-control/usr/bin/flickos-control | head -20
```

Do the same for Hello in `packages/flickos-control/usr/bin/flickos-control`:

| Where | Add |
|---|---|
| after `PHONE = …` | `HELLO = "flickos-hello"` |
| after `PHONE_HISTORY_KEYS` | `HELLO_HISTORY_KEYS = ("greeting",)` |
| `HISTORY_LABELS` | `(HELLO, "greeting"): "Greeting",` |
| `can_undo()` | `if owner == HELLO: return key in HELLO_HISTORY_KEYS` |
| `undo_commands()` | `if owner == HELLO and key == "greeting": return [[HELLO, "greeting", "set", old]]` |
| `current_value()` | `if owner == HELLO and key == "greeting": return run([HELLO, "greeting", "current"]).strip()`. Undo checks the value is still the one recorded, so it never undoes something changed outside FlickOS |
| `restorable()` | `HELLO` in the tuple `(LAYOUT, TILER, PHONE, HELLO)`, for *Put Back as It Was* |
| `history_names()` | a `hello_names()` next to `tiler_names()` that reads `greeting list`, so History shows *Mabuhay*, not *mabuhay*. This is why `list` prints `id<TAB>text`: other programs parse it (TXT-7) |
| `TILES` | `Tile("hello", "Hello", ("face-smile",), (HELLO, "show")),` and change the comment above: tiles are the Settings menu's apps *plus apps that own a setting in their own window* |
| `SEARCH_KEYWORDS` | `"tile:hello": "greeting hello hi mabuhay howdy good day welcome message",` |
| the docstring | flickos-phone and flickos-hello in the list of History owners |

Nothing makes flickos-control depend on flickos-hello: `available_tiles()`
hides a tile whose program isn't installed, and History only calls Hello for
entries Hello wrote.

### Its tests

In `packages/flickos-control/tests/test_control.py`:
- a `HelloTest` class next to `PhoneTest`: the tile shows only while Hello is
  installed; `describe()` gives `("Greeting: Mabuhay", "Was the default")`;
  undo is `greeting set default`; `current_value` runs `greeting current`;
  `history_names` reads `greeting list`;
- in `HistoryTest`, next to `test_flick_tiler_writes_what_this_reads`,
  `test_flickos_hello_writes_what_this_reads`. It runs the **real**
  `packages/flickos-hello/usr/bin/flickos-hello greeting set mabuhay` and
  checks that flickos-control reads the entry as undoable. This is the test
  that notices when the copied `record()` and flickos-control stop agreeing.
  It needs `HELLO_PACKAGE = os.path.join(PACKAGE, "../flickos-hello")` next to
  `TILER_PACKAGE`.

A test that already exists checks every tile has search keywords, so a tile
without them fails on its own.

```sh
cd packages/flickos-control
python3 -B -m unittest discover -s tests 2>&1 | tail -3
$TUTORIALS/flickos-code-tutorial/leak-check.py . | tail -6
cd ../..
```

```
Ran 326 tests in 9.129s

OK
```
```
test_control.HelperTest.test_updates_as_apt_reads_them
    runs apt-config dump
test_control.RunTest.test_run_failure_says_why
    runs /nonexistent/program

2 host file(s)/program(s) touched
```

Those two were there before you started: one reads apt's configuration, the
other starts a program that doesn't exist on purpose. Neither writes
anything. What matters is that your new tests added nothing.

**Run these tests here, in the repo tree.** `packages/build.sh` builds each
package alone in a copy, where `../flickos-hello` doesn't exist, so the
cross-package test is **skipped** there (step 9 shows it). Only a run in the
tree exercises it.

### See it work together

Put both programs on your `PATH` in a sandbox, so flickos-control's undo runs
*your* flickos-hello, and History uses throwaway folders:

```sh
T=$(mktemp -d); mkdir $T/bin
ln -s $PWD/packages/flickos-hello/usr/bin/flickos-hello $PWD/packages/flickos-control/usr/bin/flickos-control $T/bin/
export PATH=$T/bin:$PATH XDG_CONFIG_HOME=$T/config XDG_STATE_HOME=$T/state PYTHONDONTWRITEBYTECODE=1

flickos-hello greeting set mabuhay
flickos-control history --days 1 | grep Greeting
```

```
1790554915694559081	2026-09-28 08:21	undo	Greeting: Mabuhay (was the default)
```

Columns: the change's id, when, whether it can be undone, what it says on
the History page. (Without the `grep` you'd also see your computer's recent
software changes: `history` reads apt's log, which is read-only.)

```sh
id=$(flickos-control history --days 1 | awk -F'\t' '/Greeting: Mabuhay/ {print $1; exit}')
flickos-control history undo "$id"; echo "exit $?"
flickos-hello greeting current
cat $XDG_STATE_HOME/flickos/history.jsonl
```

```
exit 0
hello
{"v": 1, "id": "1790554915694559081", …, "owner": "flickos-hello", "key": "greeting", "old": "default", "new": "mabuhay"}
{"v": 1, "id": "1790554917279541142", …, "owner": "flickos-hello", "key": "greeting", "old": "mabuhay", "new": "default"}
```

The undo ran `flickos-hello greeting set default`, which recorded the second
line. History now shows neither: two changes of one setting within two
minutes (`MERGE_SECONDS`) are merged, and a change that ends where it
started is left out.

**Leave the sandbox** before going on: close the terminal, or
`unset XDG_CONFIG_HOME XDG_STATE_HOME` and start a new shell for `PATH`.

Then the version:

```sh
cd packages/flickos-control
dch -i -D trixie "More Settings: a Hello tile while flickos-hello is installed. History shows the greeting's changes by name and undoes them with flickos-hello greeting set."
cd ../..
```

That made **1.20**. flickos-control doesn't depend on flickos-hello, so
neither package's `Depends` changes.

## 7. flickos-desktop, REQUIRED and the menus

### flickos-desktop

In `packages/flickos-desktop/debian/control`, at the end of `Recommends:`
(mind the comma on the line before):

```
            usbutils,
# flickos-hello: the example program (docs/design/flickos-hello.md). An app
# users may remove, so a Recommends: removing it must not remove the desktop.
# It reaches new installs only (a Recommends never reaches installed systems).
            flickos-hello
```

A comment on every dependency is PKG-4. Comment lines inside a field are
allowed in `debian/control` (dpkg drops them). Then:

```sh
cd packages/flickos-desktop && dch -i -D trixie "Recommend flickos-hello, the example program." && cd ../..
```

That's 1.22. How the Recommends gets into the image:
`config/hooks/normal/0050-flickos-recommends.hook.chroot` asks dpkg for
flickos-desktop's Recommends and installs exactly those. Read it: it's
eight lines.

### REQUIRED: no

`config/hooks/normal/0010-sanity.hook.chroot` stops the ISO build when a
must-have is missing. Hello isn't one (ADR-005), so it stays out. Had it been
a Depends, the line would be added to `REQUIRED`, as flickos-phone's commit
did (`git show 6f9b672 -- config/hooks`).

### The menus: no, but see the check work

INT-3: an entry in labwc's menu goes into **both** copies, the installed one
(flickos-settings) and the live one (flickos-installer). Hello goes in
neither (ADR-003), but try the check that guards it. Add Hello to one menu
only:

```sh
sed -i 's|      <item label="Keyboard Shortcuts">|      <item label="Hello"><action name="Execute"><command>flickos-hello show</command></action></item>\n      <item label="Keyboard Shortcuts">|' packages/flickos-settings/etc/xdg/labwc/menu.xml
python3 -B tools/check-menus.py; echo "exit $?"
```

```
check-menus: packages/flickos-installer/etc/xdg/flickos-live/labwc/menu.xml differs from packages/flickos-settings/etc/xdg/labwc/menu.xml (besides the install item and comments):
  element 64:
    packages/flickos-settings/etc/xdg/labwc/menu.xml: item label="Hello"
    packages/flickos-installer/etc/xdg/flickos-live/labwc/menu.xml: item label="Keyboard Shortcuts"
exit 1
```

`build-iso.sh` runs this, so a one-sided menu change never reaches an ISO.
Undo the experiment:

```sh
git restore packages/flickos-settings/etc/xdg/labwc/menu.xml
python3 -B tools/check-menus.py        # Menus in sync.
```

`git restore FILE` puts a file back as it is in the last commit: the fastest
way out of an experiment.

## 8. Boot-test checks

PKG-9: a user-visible feature gets a check in `CHECKS` in `tools/boot-test.py`.
The format is in the comment above the list:

```sh
grep -n -B2 '^CHECKS = \[' tools/boot-test.py
```

```
# (description, shell command that must exit 0, seconds to keep retrying[, screenshot name])
# With a screenshot name, boot-test/NAME.png is saved after the check passes.
```

The command runs in the booted live ISO, as the live user `user`, in a shell
on the serial console. It has no desktop environment variables:
`SESSION_ENV` borrows `WAYLAND_DISPLAY` from the running waybar so a window
can open on the live desktop. Read the helpers at the top (`SESSION_ENV`,
`open_control`, `CLOSE_CONTROL`) and flickos-phone's check.

Add three checks just before the welcome window's (`# The cards are
filtered …`):

```python
    # flickos-hello (a Recommends): the greeting is its setting. A change shows
    # in Settings → History, whose undo runs flickos-hello again.
    ("Hello installed, a greeting change shows in History and can be undone",
     "test $(flickos-hello greeting current) = hello"
     " && flickos-hello greeting set mabuhay && flickos-hello say Ana | grep -qx 'Mabuhay, Ana!'"
     " && flickos-control history --days 1 | grep -q 'Greeting: Mabuhay (was the default)$'"
     " && flickos-control history undo"
     " $(flickos-control history --days 1 | awk -F'\\t' '/Greeting: Mabuhay/ { print $1; exit }')"
     " && test $(flickos-hello greeting current) = hello", 0),
    ("Hello window opens",
     f"{SESSION_ENV} setsid -f flickos-hello show >/dev/null 2>&1; sleep 3"
     f" && grep -q libgtk-3 /proc/$(pgrep -n -u {LIVE_USER} -x flickos-hello)/maps", 10, "hello-dark"),
    ("close the Hello window",
     f"pkill -u {LIVE_USER} -x flickos-hello; sleep 1; ! pgrep -u {LIVE_USER} -x flickos-hello", 10),
```

- **One check tests the whole chain:** Hello records, flickos-control shows
  and undoes, and Hello is back where it started. The check also cleans up
  after itself, which matters because later checks share the same session.
- **`'\\t'`:** Python turns `\\` into one `\`, so the shell gets `'\t'`,
  which awk reads as a tab.
- **The window check** opens it with `setsid -f` (fully detached, so the
  serial shell doesn't wait), then proves it's a GTK window by finding
  `libgtk-3` in the process's memory map. Retried for 10 s. After it passes,
  the boot test saves `boot-test/hello-dark.png`: every CI run leaves a
  picture to look at.
- **Closing by name is fine here**, inside the VM. On your own computer
  `pkill -x flickos-hello` would close *your* Hello (the harness tutorial's
  first trap).

Check what you wrote parses, and see the checks as the boot test will:

```sh
$TUTORIALS/flickos-repo-tutorial/try-checks.py --show hello
```

```
Hello installed, a greeting change shows in History and can be undone	0 s
Hello window opens	10 s	hello-dark.png
close the Hello window	10 s
```

You can run the **first** check's command in the step 6 sandbox (it only
uses `flickos-hello` and `flickos-control` from your `PATH` and throwaway
folders). **Never the other two** on your computer: they open and pkill.
Step 10 runs all three in a VM.

## 9. Build everything, run the repo's checks

```sh
time sh packages/build.sh > ../build-all.log 2>&1; echo "exit $?"
tail -18 ../build-all.log
```

```
real	1m57.946s
exit 0
==> Staged in $TUTORIALS/flickos-repo-tutorial/practice/config/packages.chroot:
flickos-archive-keyring_1.4_all.deb
…
flickos-control_1.20_all.deb
flickos-desktop_1.22_all.deb
…
flickos-hello_2.1_all.deb
…
```

`build.sh` builds **all 16 packages** from copies in `packages/.build/`
(sfwbar is compiled, most of the two minutes), runs each one's tests, and
then checks that **no file is in two packages**. dpkg would refuse that, and
without this check it would surface only deep inside `lb build`. Both output
folders are git-ignored.

Look at the cross-package test from step 6:

```sh
grep 'hello_writes' ../build-all.log
```

```
test_flickos_hello_writes_what_this_reads (…) ... skipped 'flickos-hello is not next to this package'
```

As promised: skipped in the build, because packages are built one by one in
alphabetical order and flickos-control comes before flickos-hello. It ran in
step 6, in the tree.

The other checks `build-iso.sh` runs, and lintian on what you changed:

```sh
python3 -B tools/check-menus.py        # Menus in sync.
python3 -B tools/check-palette.py      # Palette check ok: 253 colors in 39 files, …
lintian config/packages.chroot/flickos-hello_2.1_all.deb config/packages.chroot/flickos-desktop_1.22_all.deb
lintian config/packages.chroot/flickos-control_1.20_all.deb   # W: no-manual-page: it was there before
```

And what Hello costs (PERF-7), against the last ISO build's package list:

```sh
python3 -B $FLICKOS/tools/package-cost.py config/packages.chroot/flickos-hello_2.1_all.deb
```

```
Compared with: the image (flickos-amd64.packages, 1152 packages, built 2026-09-26)
  flickos-hello                          35 KB on disk        8 KB download
  1 packages                             35 KB on disk        8 KB download
```

35 KB, and nothing new comes with it: python3-gi and GTK 3 are already in the
image. (The tool is run from your real repo because it's new there and
uncommitted, so the clone doesn't have it.)

## 10. Try the checks in the live ISO

A boot-test check normally runs only on an ISO built with your package
(30–50 minutes, sudo). Here's a faster way, reusing the ship tutorial: boot
the **existing** ISO, install your two packages from the local test repo,
run the checks.

`try-checks.py` writes the script:

```sh
cd $TUTORIALS/flickos-repo-tutorial
./try-checks.py --deb practice/config/packages.chroot/flickos-hello_2.1_all.deb \
                --deb practice/config/packages.chroot/flickos-control_1.20_all.deb \
                'Hello installed' 'Hello window opens' > hello-checks.txt
cat hello-checks.txt
```

It starts with `host:` lines that add your .debs to the local repo, then the
four lines from the ship tutorial that make the VM trust that repo and
install them, then each check (a retried one wrapped in a loop that retries
it the way boot-test does). The close check is left out on purpose, so the
window is still open for the screenshot at the end.

```sh
cd $TUTORIALS/flickos-ship-tutorial
./local-repo.sh init                       # once
./local-repo.sh serve                      # in a second terminal; leave it running
./vm-run.py --shot $TUTORIALS/flickos-repo-tutorial/hello-vm.png --script $TUTORIALS/flickos-repo-tutorial/hello-checks.txt
```

```
vm$ sudo apt-get install -q -y flickos-hello flickos-control
…
The following NEW packages will be installed:
  flickos-hello
The following packages will be upgraded:
  flickos-control
…
Unpacking flickos-control (1.20) over (1.18) ...
…
vm$ dpkg-query -W flickos-hello flickos-control
flickos-control	1.20
flickos-hello	2.1

vm$ test $(flickos-hello greeting current) = hello && flickos-hello greeting set mabuhay && …

vm$ end=$(($(date +%s) + 10)); until ( env $(tr '\0' '\n' < /proc/$(pgrep -o -u user -x waybar)/environ | …

screenshot: $TUTORIALS/flickos-repo-tutorial/hello-vm.png
all commands succeeded
```

About a minute. A check that passes prints nothing: the boot test's checks
are quiet on success. Open `hello-vm.png`: the Hello window on the live
desktop, in Arc-Dark.

### Make sure the check can fail

A check that can't fail proves nothing. Take flickos-control 1.20 out of the
test repo, so the VM keeps the ISO's 1.18, which doesn't know Hello:

```sh
./local-repo.sh remove flickos-control
cd $TUTORIALS/flickos-repo-tutorial
./try-checks.py --deb practice/config/packages.chroot/flickos-hello_2.1_all.deb 'Hello installed' > hello-only.txt
cd $TUTORIALS/flickos-ship-tutorial && ./vm-run.py --script $TUTORIALS/flickos-repo-tutorial/hello-only.txt | tail -4
```

```
vm$ test $(flickos-hello greeting current) = hello && flickos-hello greeting set mabuhay && …
(exit 1)

1 command(s) failed
```

It fails at the History part: 1.18 has no *Greeting* label and no undo for
this owner. So the check really tests both packages together, which is also
why they must be published together (ADR-004).

Stop the server with Ctrl+C in its terminal when you're done.

## 11. Stage 9: the docs

Every package appears in four places besides its own files, and the design
doc gets its results. Use your checker to find out what's still missing:

```sh
cd $TUTORIALS/flickos-repo-tutorial
./check-wiring.py flickos-hello
```

Before the docs, it says:

```
flickos-hello
  ok      debian/: control, changelog, copyright, rules, source/format, install
  ok      version 2.1
  ok      tests: 1 file(s) in tests/
  ok      pulled in: Recommends flickos-desktop
  ok      REQUIRED: not listed (not a must-have)
  ok      boot test: flickos-hello named in tools/boot-test.py
  MISSING docs/04: section ### `flickos-hello`
  MISSING docs/01: a row in "Where to change what" naming packages/flickos-hello/
  note    docs/01: flickos-hello/ in the repository layout tree
  MISSING CLAUDE.md: a paragraph   - `flickos-hello`: …
  ok      docs/design/flickos-hello.md exists
```

Work through it (in `practice/`):

| File | What | Model to copy |
|---|---|---|
| `docs/04-packages.md` | A section `### \`flickos-hello\`` before `### \`flickos-greeter\``: one paragraph of what it is, then bullets: the setting, the window, History, *a Recommends*, unit tests and the boot test. Also add Hello to the *More Settings* list in flickos-control's section | `### \`flickos-shortcuts\`` |
| `docs/01-overview.md` | A row in *Where to change what*: "Change the example program Hello (greetings, the default greeting for everyone)", its files and the design doc. A line in the repository tree under `flickos-greeter/` | the flickos-phone row |
| `docs/09-customizing.md` | The disagreement from step 3: a tile's app goes in the Settings menu only when it's a settings app. Also *More Settings* in the table above it: "plus Hello" | |
| `CLAUDE.md` | A paragraph `  - \`flickos-hello\`: …` before `waypaper`, dense like the others: the file, what it owns and its commands, the conffile and user file, History, the tile, *a Recommends, not in REQUIRED*, tests. And two sentences in flickos-control's paragraph: the tiles are "the Settings menu's apps plus Hello", and flickos-hello's `save_greeting` is among the History owners | the flickos-welcome paragraph |
| `docs/design/flickos-hello.md` | Status: **Accepted**, with the versions. Phase 1: "(done 2026-09-28)", a table of what you measured against the budgets, what the tests and the VM showed, and what you found on the way (the leak) | flickos-menu's phase 1 |

Why CLAUDE.md matters as much as the docs: it's what an AI assistant reads
first in this repo. If it doesn't say Hello is a Recommends on purpose,
the next change may "fix" it into a Depends.

The measurements for the design doc (yours will be close):
- `greeting list`: 76–79 ms (it was 72 ms: `record()` added the `json` and
  `datetime` imports);
- `greeting set`, with the record: 79–81 ms;
- first frame: 540–570 ms, measured the code tutorial's way (step 10 there),
  with `practice/packages/flickos-hello/usr/bin/flickos-hello show`;
- disk: 35 KB (step 9).

Then:

```sh
./check-wiring.py flickos-hello; echo "exit $?"      # all ok, exit 0
```

## 12. Stage 10: the second commit

One commit for the whole phase: flickos-hello, flickos-control and
flickos-desktop change together and are published together, so they go in
together. A later `git revert` of that one commit takes all of it back.

```sh
cd $TUTORIALS/flickos-repo-tutorial/practice
git status --short
```

```
 M CLAUDE.md
 M docs/01-overview.md
 M docs/04-packages.md
 M docs/09-customizing.md
 M docs/design/flickos-hello.md
 M packages/flickos-control/debian/changelog
 M packages/flickos-control/tests/test_control.py
 M packages/flickos-control/usr/bin/flickos-control
 M packages/flickos-desktop/debian/changelog
 M packages/flickos-desktop/debian/control
 M tools/boot-test.py
?? packages/flickos-hello/
```

`M` is modified, `??` is untracked (new, not yet known to git). Not listed:
`packages/.build/`, `config/packages.chroot/` and the like, because
`.gitignore` hides build output (`git status --ignored` shows it). **Read
this list before every commit**: anything you didn't mean to change shows up
here.

```sh
git add -A                              # everything git status listed
git diff --cached --stat
git diff --cached -- CLAUDE.md          # read the parts a reviewer would
git ls-files -s packages/flickos-hello/debian/rules packages/flickos-hello/usr/bin/flickos-hello
```

```
100755 packages/flickos-hello/debian/rules
100755 packages/flickos-hello/usr/bin/flickos-hello
```

`100755` means git stored them as executable. `debian/rules` must be (step
14 finds one in the real repo that isn't).

The message, in the style of flickos-phone's (`git show -s 6f9b672`): a
subject with the main package and version, then **one bullet per package
version**, then the tests and docs:

```
flickos-hello 2.1: the example program, in FlickOS (phase 1)

- flickos-hello 2.1 (new here): the greeting, one setting with a system
  default (/etc/xdg/flickos/hello.conf) and a user's choice
  (~/.config/flickos/hello); greeting list|current|set ID|default, say,
  and a window (show). Every change is now recorded for Settings →
  History. 25 unit tests, all with faked config, state and /etc paths.
- flickos-control 1.20: a Hello tile on More Settings while it is
  installed (INT-4), with search keywords. History knows flickos-hello:
  the label Greeting, the greetings' names from greeting list, undo with
  greeting set OLD, and Put Back as It Was. 4 new tests.
- flickos-desktop 1.22: Recommends flickos-hello. An app users may
  remove, so not a Depends and not in REQUIRED; new installs only.
- Boot test: change the greeting, undo it from History, open and close
  the window (hello-dark.png). Tried in the 2.1 live ISO with both
  packages from a local test repo.
- Docs: 04, 01 (row and tree), 09 (a tile's app goes in the Settings
  menu only when it is a settings app), CLAUDE.md, and the design doc,
  accepted, with phase 1's measurements.
```

The bullets let someone scanning `git log` find *which commit made
flickos-control 1.20* without opening it. The changelog entries say the same
things for users; the commit says them for developers.

```sh
git commit
git log --oneline -3
git show --stat HEAD
```

**Fixing a commit:** until it's pushed, a commit is yours to change. Forgot a
file? `git add FILE && git commit --amend`. Once it's pushed, never amend:
make a new commit. Once a *package version* is published, it's frozen for
good (the ship tutorial, step 13). That's a stronger rule than git's.

## 13. Compare with the answer key

Put the answer in the same clone, on its own branch, and compare:

```sh
cd $TUTORIALS/flickos-repo-tutorial/practice
git branch answer d10cde8                # a branch where this guide started
git checkout answer
git am ../finished/*.patch               # replays the two commits
git checkout main
git diff answer main --stat              # what's different between yours and the key
git diff answer main -- packages/flickos-control/usr/bin/flickos-control
```

`git am` applies patches made by `git format-patch`, commit messages
included. Differences in wording are expected. Look for missing pieces
instead: a place in the table in step 6 you skipped, a test, a doc row.

If your repo had moved on past `d10cde8` when you cloned, `git diff` also
shows everything that changed in between. Then compare file by file, or
apply the patches to a clone at `d10cde8`.

## 14. What check-wiring.py found in the real repo

`check-wiring.py` only reads files, so it's safe to point at your real repo:

```sh
./check-wiring.py --repo $FLICKOS --all | grep -v '^  ok'
```

Leaving out the design-doc notes (most small packages don't need one), this
is what it found in the real repo:

| Package | Finding |
|---|---|
| flickos-welcome | **`debian/rules` isn't executable** in git (`100644`). dpkg-buildpackage fixes the mode at build time and says so, so the build works, but docs/04 says it must be executable. Fix: `git update-index --chmod=+x packages/flickos-welcome/debian/rules` |
| flickos-welcome | **No section in docs/04.** CLAUDE.md, docs/01 and docs/09 describe it, docs/04 doesn't |
| flickos-greeter, sfwbar | **No row in docs/01's "Where to change what"** (both are in the tree above it) |
| flickos-menu, flickos-phone, flickos-welcome | Not in docs/01's **repository tree** (a note: PKG-10 asks only for the table row) |
| waypaper | A note: a Depends of flickos-desktop, but not in `REQUIRED`. A judgment call: FlickOS runs without the Wallpaper app |
| flickos-archive-keyring | A note: no boot-test check names it. It has no program or window; the check *FlickOS apt source enabled* covers its file |

These are small, real gaps. If you want the practice, fix them in `practice/`
first, then decide whether to fix them in the real repo (and `hig/audit.md`
is where findings go that aren't fixed right away).

## 15. Doing it for real

In your real repo the steps are the same, plus what `practice/` can't do:

1. **Work where you normally do**, on `main` or a branch.
2. **Check the pool before choosing versions:** your published apt repo may
   already have the version dch picked if you published from somewhere else
   (`ls repo/public/pool/main/f/flickos-control/`). A published version is
   frozen.
3. **Commit** as in steps 4 and 12.
4. **Push.** CI builds the ISO and runs the full boot test, with your new
   checks, on a clean machine (`docs/06`). Look at its `hello-dark.png`.
5. **Publish only when the phase is complete for users.** flickos-phone's
   commit says *"Not to be published before phase 2's Phone page in
   Settings (INT-4)"*: code can be in the repo before it's ready to reach
   installed systems. When it is, publish both packages together (ADR-004),
   after an upgrade test (the ship tutorial).

## 16. Traps

1. **`git push` from a clone of a local repo pushes into that repo.** Remove
   `origin` first (step 1).
2. **A practice branch or `git stash` in the real repo** shares its state
   with your real work. Use a clone.
3. **A new path in the program, not faked in the tests.** `record()` would
   have written your real History during every build (step 5). leak-check,
   with a fake `HOME` outside `/tmp`, shows it safely.
4. **Cross-package tests are skipped in `build.sh`.** They run only in the
   repo tree (step 6). Run the tests there after changing either side.
5. **Copying "every FlickOS program is a Depends".** For an app users may
   remove, a Depends means removing it removes flickos-desktop (step 3).
6. **Running boot-test checks on your own computer.** They change settings
   and close programs by name. Run them in the VM (step 10).
7. **A check that can't fail.** Run it once against the old version (step
   10).
8. **One menu edited, not the other.** `check-menus.py` catches it (step 7).
9. **A doc that disagrees with your decision.** Change the doc in the same
   commit (docs/09 in step 11), or the next person follows the doc.
10. **`dch` warnings about `libdistro-info-perl`** are noise. What matters is
    the top entry: version, `trixie`, your message.
11. **Committing without reading `git status`** is how build output, a
    `__pycache__` or an experiment gets into the repo.

## 17. Cheat sheet

```sh
# a safe copy
git clone $FLICKOS practice && cd practice && git remote remove origin

# git
git status --short                    # what changed (M modified, ?? new)
git add FILE | git add -A             # into the index
git diff | git diff --cached          # not yet added | what the commit will be
git commit | git commit --amend       # commit | fix the last one (before pushing)
git log --oneline -5 | git show --stat HEAD
git restore FILE                      # undo an experiment
git ls-files -s FILE                  # 100755 = executable in git
git format-patch A..B -o DIR | git am DIR/*.patch

# versions
dch -i -D trixie "Message."           # in the package folder

# checks
./check-wiring.py PACKAGE | --all [--repo DIR]
python3 -B tools/check-menus.py; python3 -B tools/check-palette.py
sh packages/build.sh                  # all packages, tests, file overlaps
cd packages/NAME && python3 -B -m unittest discover -s tests     # with siblings present
$TUTORIALS/flickos-code-tutorial/leak-check.py packages/NAME
apt-get -s remove PACKAGE             # what a removal would take with it

# boot-test checks in the live ISO
./try-checks.py --show PATTERN
./try-checks.py --deb FILE.deb … PATTERN > checks.txt
$TUTORIALS/flickos-ship-tutorial/local-repo.sh init | serve | remove NAME | clean
$TUTORIALS/flickos-ship-tutorial/vm-run.py [--shot FILE.png] --script checks.txt
```

## 18. Clean up

```sh
cd $TUTORIALS/flickos-ship-tutorial && ./local-repo.sh clean && rm -f vm-run.log
cd $TUTORIALS/flickos-repo-tutorial && rm -rf practice fake-home hello-checks.txt hello-only.txt hello-vm.png build-all.log
```

Your real repo was never touched, so there's nothing to undo there.
