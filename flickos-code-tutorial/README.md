# Writing a FlickOS program, step by step

> Set `TUTORIALS` to the root of the [tutorials repository](https://github.com/dvbondoy/flickos-tutorials) and `FLICKOS` to your clone of [FlickOS](https://github.com/dvbondoy/FlickOS). Paths below use those two variables. Scripts read the FlickOS checkout from `FLICKOS_REPO` or `FLICKOS`.

This is stage 5 of the path from idea to release: **writing the program and
its unit tests.** You'll rewrite **flickos-hello** as a real FlickOS program,
following the HIG (`$FLICKOS/docs/hig/`). By the end it:
- owns one setting (the greeting), with a default for the computer and each
  account's own choice;
- has the commands every FlickOS setting has: `list`, `current`,
  `set ID|default`;
- has a small GTK 3 window that follows the Dark and Light styles;
- has 20 unit tests that never touch your real desktop;
- builds into a `.deb` as version 2.0.

It's built in four stages. Each stage is a complete program in `stages/`,
so you can always compare your file with the right one.

Every command here was run while writing this guide, and the outputs shown are
the real ones.

- **Time:** 2 to 3 hours if you type the code yourself, which is the point.
- **What it touches:** a `work/` folder here, throwaway folders in `/tmp`,
  and a window on your screen when you ask for one. Nothing is installed.

## Where this fits

| # | Stage | Tutorial |
|---|---|---|
| 1–2 | Idea, spike | `flickos-snip-spike`, `flickos-spike-kit` |
| 3–4 | Design doc, HIG check | `flickos-repo-tutorial` |
| **5** | **Code + unit tests** | **here** |
| 6 | The .deb | `flickos-deb-tutorial` |
| 7 | Tests: own desktop, headless labwc, QEMU, boot test | `flickos-headless-labwc`, `flickos-ship-tutorial` |
| 8–10 | Wire it into the repo, document it, commit it | `flickos-repo-tutorial` |
| 11–13 | Upgrade test, publish, release | `flickos-ship-tutorial` |

## What's in this folder

| Path | What it is |
|---|---|
| `README.md` | This guide |
| `stages/1/` … `stages/4/` | The program after each stage (and the tests at stages 3 and 4). `diff stages/2/flickos-hello stages/3/flickos-hello` shows exactly what a stage adds |
| `finished/flickos-hello/` | The whole package at the end: program, conffile, desktop file, tests, `debian/` (version 2.0) |
| `leak-check.py` | Runs **any** package's tests and reports every file or program on your computer they touch. It works on the repo's packages too |
| `work/` | Made by you in step 2: your own copy |

## Contents

0. [The rules this program follows](#0-the-rules-this-program-follows)
1. [Set up](#1-set-up)
2. [Stage 1: the manual and the table](#2-stage-1-the-manual-and-the-table)
3. [Stage 2: reading the setting](#3-stage-2-reading-the-setting)
4. [Stage 3: changing it](#4-stage-3-changing-it)
5. [Unit tests](#5-unit-tests)
6. [Leaks: tests that touch your computer](#6-leaks-tests-that-touch-your-computer)
7. [Stage 4: the window](#7-stage-4-the-window)
8. [Trying the window](#8-trying-the-window)
9. [The desktop file](#9-the-desktop-file)
10. [Measuring it](#10-measuring-it)
11. [Packaging 2.0](#11-packaging-20)
12. [Reviewing against the checklist](#12-reviewing-against-the-checklist)
13. [What a real FlickOS program adds](#13-what-a-real-flickos-program-adds)
14. [Traps](#14-traps)
15. [Cheat sheet](#15-cheat-sheet)
16. [Clean up](#16-clean-up)

---

## 0. The rules this program follows

The HIG has about 90 rules. A program like this one meets these, and each
step below points to the ones it's about. Keep `docs/hig/checklist.md` open
while you work.

| Rule | In one line | Where here |
|---|---|---|
| CODE-1 | One Python file, standard library (+ `gi` for a window) | the whole program |
| CODE-2 | The docstring is the manual | stage 1 |
| CODE-3 | Tables of constants at the top drive the code | stage 1: `GREETINGS` |
| CODE-4 | argparse subcommands, `main()` returns the exit code | stage 1 |
| TXT-7 | CLI output: `NAME: message` on stderr, tab-separated lines on stdout, exit 0/1/2 | stages 1–3 |
| SET-1, SET-2 | One owner per setting, and it works on the command line before any window | stages 2–3 |
| SET-4 | System default in `/etc/xdg/flickos/`, user choice in `~/.config/flickos/`, a broken file means defaults | stage 2 |
| SET-6, SET-8 | Atomic writes, every setting can go back to its default | stage 3 |
| CODE-6 | Expected failures become messages, not tracebacks | stages 2–4 |
| PKG-8 | Unit tests in `tests/`, no display, network or root | step 5 |
| CODE-9, PERF-3 | GTK loaded late, only for the window | stage 4 |
| WIN-1…4, WIN-10 | Title bar from labwc, one window, fits 1366×768, title = name, errors shown in the window | stage 4 |
| A11Y-2, A11Y-3 | Escape closes, mnemonics on labels and buttons | stage 4 |
| INT-1 | A program people open has a desktop file | step 9 |
| PERF-1 | Window ≤ 1 s, `list` ≤ 200 ms | step 10 |

## 1. Set up

Start from the package you built in the deb tutorial (version 1.0). Its
`debian/` folder stays, and its program and tests get rewritten:

```sh
cd $TUTORIALS/flickos-code-tutorial
mkdir -p work
cp -r $TUTORIALS/flickos-deb-tutorial/finished/flickos-hello work/
rm work/flickos-hello/tests/test_hello.py         # 1.0's tests: stage 5 writes new ones
cd work/flickos-hello
```

**A sandbox for trying things.** The program reads two places, which the next
steps explain. While you develop, point both at throwaway folders, so trying
a command never changes your real account:

```sh
export XDG_CONFIG_HOME=/tmp/hello-home            # instead of ~/.config
export FLICKOS_HELLO_PREFIX=/tmp/hello-root       # instead of / for /etc/xdg/flickos/hello.conf
```

These two lines only affect the terminal you type them in. Open a new
terminal (or `unset XDG_CONFIG_HOME FLICKOS_HELLO_PREFIX`) to get back to
normal. The unit tests in step 5 do exactly the same thing, from Python.

## 2. Stage 1: the manual and the table

Open `usr/bin/flickos-hello` and replace everything in it. Type it from
`stages/1/flickos-hello`. Here is what each part is, in file order.

**The docstring comes first, and it's written before the code (CODE-2).** It's
the manual:
1. what the program is, and what it owns;
2. how it fits with the rest;
3. every command, one line each;
4. the exit codes.

Writing it first forces the design questions before any code exists. "Which
file wins?" "What does `default` do?" "What happens with a broken file?" Stage
1's docstring already describes the finished program; the code catches up
over the next stages.

```python
"""Hello: greets you with the greeting you choose. …

It owns one setting, the greeting. The machine's default is in the conffile
/etc/xdg/flickos/hello.conf ([Hello] Greeting=ID); a user's choice is in
~/.config/flickos/hello, written only when they choose one, and wins. …

Commands:
  (none), say [NAME]      print the greeting to NAME (default: your user name)
  show                    open the window
  greeting list           print the greetings: id, text
  greeting current        print the id of the greeting in use
  greeting set ID|default choose a greeting (default: the machine's)

Exit codes: 0 ok, 1 error, 2 usage error.
"""
```

**The table (CODE-3).** What the program supports is a list of constants at
the top, not decisions spread through functions. Adding a greeting means
adding a row, and nothing else changes:

```python
# The greetings, in the order they are listed: id (stored in the files, never
# changed once shipped), text. Adding a greeting is adding a row.
GREETINGS = [
    ("hello", "Hello"),
    ("hi", "Hi"),
    ("mabuhay", "Mabuhay"),
    ("howdy", "Howdy"),
    ("good-day", "Good day"),
]
# When neither file sets one. The shipped hello.conf says the same (a test checks).
DEFAULT_GREETING = "hello"
```

Why an **id** and a **text**?
- The files store the id (`mabuhay`).
- The screen shows the text (`Mabuhay`).
- The text can be reworded, or translated one day, without breaking anyone's
  saved choice.
- The comment says the ids never change once shipped. That's a promise to
  every file already written on someone's computer.

Every constant has a comment saying what it is and who depends on it.

**`warn()` (TXT-7).** Every message for a person goes to stderr as
`flickos-hello: message`. One function, so they all look the same.

**`main()` and argparse (CODE-4).**
- One `cmd_NAME(opts)` function per command.
- `main(argv=None)` **returns** the exit code rather than calling `sys.exit`,
  so tests can call `main(["greeting", "list"])` and look at the result.
- `sys.exit(main())` happens only when the file is run as a program.

```python
def cmd_list(_opts):
    for greeting, text in GREETINGS:
        print(f"{greeting}\t{text}")
    return 0
```

`list` prints what TXT-7 asks for scripts: one item per line, the id first,
then fields separated by **tabs**. Settings and the boot test read that
output, so its form is a promise too.

**Try it:**

```sh
diff ../../stages/1/flickos-hello usr/bin/flickos-hello && echo "same as stage 1"
chmod +x usr/bin/flickos-hello
usr/bin/flickos-hello greeting list
usr/bin/flickos-hello --help
usr/bin/flickos-hello greeting nonsense; echo "exit $?"
```

```
hello	Hello
hi	Hi
mabuhay	Mabuhay
howdy	Howdy
good-day	Good day
usage: flickos-hello [-h] COMMAND ...
…
flickos-hello greeting: error: argument ACTION: invalid choice: 'nonsense' (choose from list)
exit 2
```

argparse writes `--help` from the `help=` strings and exits with 2 on a wrong
command: TXT-7's "usage error" at no cost.

## 3. Stage 2: reading the setting

Add what `stages/2/flickos-hello` adds. `diff ../../stages/1/flickos-hello
../../stages/2/flickos-hello` shows it:
- the `# --- The setting ---` section;
- `say` and `greeting current`;
- saying hello when no command is given.

**Where the setting lives (SET-4):**

| Place | Who writes it | When it's read |
|---|---|---|
| `/etc/xdg/flickos/hello.conf` | the package (a **conffile**), changed by an administrator | always, as the computer's default |
| `~/.config/flickos/hello` | this program, only when the user chooses | if present, it wins |
| `DEFAULT_GREETING` in the code | nobody | when neither file says anything |

```python
PREFIX = os.environ.get("FLICKOS_HELLO_PREFIX", "")
SYSTEM_CONF = PREFIX + "/etc/xdg/flickos/hello.conf"
```

**`PREFIX` is the testing hook (CODE-5, PKG-8).** It's empty normally, so the
path is the real `/etc/…`. Tests and your sandbox set it to a throwaway
folder. It's read once, at the top, like every FlickOS program's
`FLICKOS_NAME_PREFIX`.

**`config_home()`** follows the XDG rule (CODE-8): `$XDG_CONFIG_HOME` if set,
else `~/.config`. Never write `~/.config` by hand: the sandbox, the tests and
the headless harness all depend on the variable being honoured.

**`read_ini()` never fails.** A missing file is empty. A broken one is empty
**with a warning**, and the program carries on (SET-4: "never refuse to start
because of a config file"):

```python
    except (configparser.Error, UnicodeDecodeError) as error:
        # configparser's messages run over several lines; the first says it.
        warn(f"{path}: can't read it, ignored ({str(error).splitlines()[0].rstrip('.')})")
        return {}
```

**`greeting_id()` is forgiving.** It accepts the id or the text, in any case.
1.0's `hello.conf` said `Greeting=Hello`, and an administrator who changed it
kept their file through the upgrade: it's a conffile, as the deb tutorial
showed. So 2.0 must still understand `Hello`, `Hi` and `Mabuhay`. A value it
doesn't know is warned about and ignored, and the next place down is used.

**Update the conffile** to the new format, from
`finished/flickos-hello/etc/xdg/flickos/hello.conf`. The comment at the top
says who reads it and how to change it (SET-4):

```ini
# flickos-hello's greeting for every account on this computer.
# An account's own choice (flickos-hello greeting set ID, or the Hello window)
# is in ~/.config/flickos/hello and wins.
# The greetings: flickos-hello greeting list
[Hello]
Greeting=hello
```

**Try every case, in the sandbox:**

```sh
P=usr/bin/flickos-hello
$P                                                    # Hello, jon!   (no files: the built-in default)
$P say Ana                                            # Hello, Ana!
mkdir -p $FLICKOS_HELLO_PREFIX/etc/xdg/flickos $XDG_CONFIG_HOME/flickos
printf '[Hello]\nGreeting=Mabuhay\n' > $FLICKOS_HELLO_PREFIX/etc/xdg/flickos/hello.conf
$P                                                    # Mabuhay, jon!  (the text form, like 1.0's file)
printf '[Hello]\nGreeting=howdy\n' > $XDG_CONFIG_HOME/flickos/hello
$P; $P greeting current                               # Howdy, jon!  howdy  (the user wins)
printf '[Hello]\nGreeting=Bonjour\n' > $XDG_CONFIG_HOME/flickos/hello
$P
printf 'garbage [[\n' > $FLICKOS_HELLO_PREFIX/etc/xdg/flickos/hello.conf
$P
rm -rf /tmp/hello-home /tmp/hello-root
```

The last two:

```
flickos-hello: /tmp/hello-home/flickos/hello: unknown greeting 'Bonjour', ignored
Mabuhay, jon!
flickos-hello: /tmp/hello-home/flickos/hello: unknown greeting 'Bonjour', ignored
flickos-hello: /tmp/hello-root/etc/xdg/flickos/hello.conf: can't read it, ignored (File contains no section headers)
Hello, jon!
```

Each problem gets one line that names the file, and the program still greets.

## 4. Stage 3: changing it

Add what `stages/3/flickos-hello` adds: `write_atomic()`, `save_greeting()`
and `greeting set`.

**Atomic writes (SET-6):**

```python
def write_atomic(path, text):
    """Write text to path through a temporary file in the same folder, so no
    one ever reads half a file. Raises OSError."""
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
```

- A plain `open(path, "w")` empties the file first and then writes it. A crash,
  a full disk, or another program reading at that moment would see an empty
  or half file.
- `os.replace()` swaps the finished file in, in one step. Readers see the old
  file or the new one, never something in between.
- The temporary file must be in **the same folder**, because a rename can't
  cross filesystems.
- The `except` removes the temporary file on any failure, so nothing is left
  lying around. A test checks this.

**`default` removes the choice (SET-8):**

```python
    if greeting is None:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(path)
        return
```

"Default" means "no choice of my own": the user file goes away, and the
computer's greeting applies again. That also covers the case where the
administrator later changes it. Storing `hello` instead would freeze today's
default into the user's file forever. (flickos-control writes defaults
explicitly for a different reason: labwc never resets an option that
disappears.)

**The file says who wrote it**, the SET-4 comment:

```
# Written by flickos-hello. Change it with: flickos-hello greeting set ID|default
[Hello]
Greeting=mabuhay
```

**`set` validates through argparse:** `choices=` lists the ids plus
`default`. Anything else is a usage error (exit 2) with the valid choices in
the message. A save that fails (disk full, read-only folder) is an **expected
failure**: it becomes one line and exit 1, never a traceback (CODE-6).

**Try it:**

```sh
export XDG_CONFIG_HOME=/tmp/hello-home FLICKOS_HELLO_PREFIX=/tmp/hello-root
P=usr/bin/flickos-hello
$P greeting set mabuhay; echo "exit $?"; $P
cat $XDG_CONFIG_HOME/flickos/hello
$P greeting set nope; echo "exit $?"
$P greeting set default; ls -A $XDG_CONFIG_HOME/flickos; $P greeting current
chmod 500 $XDG_CONFIG_HOME/flickos; $P greeting set hi; echo "exit $?"; chmod 700 $XDG_CONFIG_HOME/flickos
```

```
exit 0
Mabuhay, jon!
# Written by flickos-hello. Change it with: flickos-hello greeting set ID|default
[Hello]
Greeting=mabuhay
usage: flickos-hello greeting set [-h]
                                  {hello,hi,mabuhay,howdy,good-day,default}
flickos-hello greeting set: error: argument value: invalid choice: 'nope' (choose from hello, hi, mabuhay, howdy, good-day, default)
exit 2
hello
flickos-hello: can't save the greeting ([Errno 13] Permission denied: '/tmp/hello-home/flickos/.l3yrs5jb.tmp')
exit 1
```

A successful `set` prints nothing (TXT-7: success is quiet), and `default`
left the folder empty. **This is the whole setting, finished, on the command
line (SET-2), before any window exists.** Settings, a panel button, a script
or someone over ssh would all use these same commands.

## 5. Unit tests

Copy `stages/3/test_hello.py` to `tests/test_hello.py` and read it. It has 17
tests. The ideas in it:

**Importing a program that has no `.py`.** `import` only finds `NAME.py`
files, so the test loads the file by its path. Every FlickOS test starts this
way:

```python
sys.dont_write_bytecode = True
_loader = importlib.machinery.SourceFileLoader("flickos_hello", PROGRAM)
hello = importlib.util.module_from_spec(importlib.util.spec_from_loader(_loader.name, _loader))
_loader.exec_module(hello)
```

The file's code runs, but `main()` doesn't, because `__name__` isn't
`"__main__"`. So `hello.GREETINGS`, `hello.main([...])` and the rest are
available to the tests.

**Every test gets its own world (`HomeTest`):**

```python
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.home = os.path.join(self.root, "config")
        self.system_conf = os.path.join(self.root, "etc/xdg/flickos/hello.conf")
        for patch in (mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": self.home}),
                      mock.patch.object(hello, "SYSTEM_CONF", self.system_conf)):
            patch.start()
            self.addCleanup(patch.stop)
```

- `mock.patch.dict(os.environ, …)` changes an environment variable for one test.
- `mock.patch.object(hello, "SYSTEM_CONF", …)` replaces the module's constant.
- `addCleanup` puts everything back even when the test fails.

This is the sandbox from step 1, in Python. It's not optional: **the tests run
on your computer during every package build**, and your computer is a live
FlickOS desktop (step 6).

**Test through `main()`, the way people use it:**

```python
    def test_set_default_goes_back_to_the_machines(self):
        self.system_says("howdy")
        run_main("greeting", "set", "hi")
        self.assertEqual(run_main("greeting", "set", "default"), (0, ""))
        self.assertEqual(run_main("greeting", "current"), (0, "howdy\n"))
        self.assertFalse(os.path.exists(hello.user_conf()), "no choice, no file")
```

`run_main()` catches stdout and returns `(exit code, output)`. The test reads
like the docstring's promises: set, go back to default, the machine's value
applies, no file is left. The third argument of `assertFalse` is the message
you'll see when it fails, so write why the check matters.

**What else is tested:**

| Class | It checks |
|---|---|
| `ReadTest` | no files → default; system file; the user wins; text and any case (1.0's files); unknown and broken files → one-line warning, carry on |
| `CommandTest` | `say`, no command, `list`'s tab format, `set`/`current`, `default`, no temporary file left behind, a bad id → exit 2, a read-only folder → exit 1 with a message |
| `NoGtkTest` | the commands never load GTK (PERF-3). It runs the program in a **fresh** Python, where nothing is imported yet, and checks `'gi' in sys.modules` |
| `ShippedFilesTest` | the files of the package agree: the shipped `hello.conf` names `DEFAULT_GREETING`, ids are unique and simple (PKG-8: "what must hold across files gets a test") |

**Run them:**

```sh
python3 -B -m unittest discover -s tests -v
```

`-B` means "write no `__pycache__`". The package build gets the same effect
from `PYTHONDONTWRITEBYTECODE=1` in `debian/rules`.

```
test_a_read_only_folder_is_an_error_not_a_crash (test_hello.CommandTest…) ... ok
…
Ran 17 tests in 0.136s

OK
```

**Make one fail on purpose.** A test you've never seen fail may not test
anything. Change `DEFAULT_GREETING = "hello"` to `"hi"` and run again:

```
FAIL: test_no_command_says_hello_to_you (test_hello.CommandTest.test_no_command_says_hello_to_you)
FAIL: test_say (test_hello.CommandTest.test_say)
FAIL: test_shipped_conf_names_the_default_greeting (test_hello.ShippedFilesTest.test_shipped_conf_names_the_default_greeting)
```

Notice which test did **not** fail: `test_no_files_is_the_default` compares
the answer with `hello.DEFAULT_GREETING` itself, so it moves along with the
change. A test that computes its expected value from the code it tests can't
catch a mistake in that code. `test_say`, with the literal `"Hello, Ana!"`,
can. Put it back.

## 6. Leaks: tests that touch your computer

A test that forgets its sandbox reads **your** `/etc/xdg/flickos/hello.conf`
or **your** `~/.config`. It passes in CI, which has none of those files, and
behaves differently on your desktop. It has happened in FlickOS:
- flickos-layouts' tests once stopped your real start menu daemon;
- flickos-control's History test failed after an `apt install`.

`leak-check.py` finds these. It runs a package's tests with an **audit hook**,
Python's way of reporting every `open()`, `os.listdir()` and
`subprocess.Popen()`. It lists each one outside the test's own folders, with
the test that did it.

```sh
cd $TUTORIALS/flickos-code-tutorial
./leak-check.py work/flickos-hello
```

```
Ran 17 tests in 0.138s

OK

nothing outside the test folders was touched
```

**Plant a leak** to see what it catches. In `tests/test_hello.py`, delete the
`mock.patch.object(hello, "SYSTEM_CONF", …)` line from `HomeTest.setUp` (keep
the `XDG_CONFIG_HOME` one), and run it again:

```
FAILED (failures=5)
test_hello.CommandTest.test_no_command_says_hello_to_you
    reads /etc/xdg/flickos/hello.conf
test_hello.CommandTest.test_say
    reads /etc/xdg/flickos/hello.conf
…
test_hello.ReadTest.test_no_files_is_the_default
    reads /etc/xdg/flickos/hello.conf
…
8 host file(s)/program(s) touched
```

Look at which tests *passed* anyway: `test_say`, `test_no_files_is_the_default`
and `test_no_command_says_hello_to_you`. They pass only because your computer
has no `/etc/xdg/flickos/hello.conf` yet. Install flickos-hello, or have an
administrator change it, and they fail on this computer alone. The checker
finds them before that happens. Put the line back.

It works on the repo's packages too. It only watches, and the tests run just
as they do in a build:

```sh
./leak-check.py $FLICKOS/packages/flick-tiler        # nothing outside the test folders was touched
./leak-check.py $FLICKOS/packages/flickos-welcome    # nothing outside the test folders was touched
```

What it allows without a report:
- the package folder and the folder it's in (the repo's `packages/`, since a
  test may compare two packages' files on purpose);
- the temp folder, and `/nonexistent`;
- Python's own library folders.

A program a test starts is listed but not followed. Check what it's given.

## 7. Stage 4: the window

Add what `stages/4/flickos-hello` adds:
- `escape()`;
- the `# --- Single instance ---` and `# --- The window ---` sections;
- `show`;
- `APP_ID`, `TITLE`, `ICON` and `LOCK` at the top.

Copy `stages/4/test_hello.py` too: it adds the single-instance tests.

**Load GTK late, and check for a display (CODE-9, PERF-3):**

```python
def load_gtk():
    """GTK 3, or None with a warning (not installed, or no display)."""
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        from gi.repository import GLib
        GLib.set_prgname(APP_ID)
        from gi.repository import Gdk, Gtk
    except (ImportError, ValueError) as error:
        warn(f"can't open the window ({error}); python3-gi and gir1.2-gtk-3.0 are needed")
        return None
    if not Gtk.init_check(sys.argv[:1])[0]:
        warn("can't open the window (no display)")
        return None
    return Gtk, Gdk
```

- **The import is inside the function.** Importing GTK takes about a quarter
  of a second (230 ms on your i3, against 25 ms for Python alone), and `list`,
  `current` and `set` don't need it. They stay fast, and
  work over ssh and in the boot test.
- **`require_version("Gtk", "3.0")`** pins GTK 3. GTK 4 would ignore the Arc
  theme (CODE-9).
- **`set_prgname(APP_ID)`** happens before GTK starts. It becomes the Wayland
  **app id**: labwc uses it to find the desktop file's icon, and window rules
  and `wlrctl` use it to find the window.
- **`init_check`** returns False instead of crashing when there's no display.

**One window per session (WIN-2):** `single_instance()` takes an `flock` on
`$XDG_RUNTIME_DIR/flickos/hello.lock`. The kernel releases it when the process
ends, even after a crash, which a "PID file" can't promise. A second `show`
prints `Hello is already open.` and exits 0.

**The window**, rule by rule:

| Code | Rule |
|---|---|
| `Gtk.Window(title=TITLE, icon_name=ICON)`, no header bar | WIN-1 (labwc draws the title bar in the style's theme), WIN-4 (title = the desktop file's `Name`) |
| `set_default_size(420, 220)` | WIN-3: at most 1280×680 |
| spacing 24 around, 18 between groups, 12 in a row | WIN-5's scale |
| `Gtk.Label(label="_Greeting", use_underline=True)` + `set_mnemonic_widget(combo)`, `Gtk.Button.new_with_mnemonic("_Close")` | A11Y-3: Alt+G, Alt+C |
| Escape in `key_pressed` | A11Y-2 |
| `Gtk.ComboBoxText` whose first entry is `Default (Hello)` | WIN-7 (one of a list), SET-8 (the default is a choice) |
| saving in the `changed` handler, no Apply button | WIN-8, SET-7: it applies at once |
| no CSS, the `dim-label` style class for the hint | VIS-2: it follows Dark and Light by itself |
| `problem` label, selectable, with the error | WIN-10, TXT-6: what happened, what to do, then the detail for a bug report |

**Two details learned the hard way while writing this:**

1. **A selectable label that comes first opens with all its text selected.**
   When a window opens, GTK focuses its first focusable widget, and a
   selectable label counts. The first version had the big greeting
   selectable, and it opened fully highlighted. The greeting doesn't need
   copying, so it's a plain label now. The error label is selectable, but it
   comes after the combo.
2. **After a failed save, put the control back.** Without this, the combo
   showed "Hi" while "Mabuhay" was still saved: the control lied. This is the
   same thing flickos-welcome does with its check box:

```python
            # Show what is really in use again, without saving it once more.
            box.handler_block_by_func(changed)
            box.set_active_id(user_greeting() or "default")
            box.handler_unblock_by_func(changed)
```

`handler_block_by_func` stops the change from firing `changed` again, which
would try to save a second time.

## 8. Trying the window

**On your own desktop**, with the sandbox (step 1) so a choice doesn't touch
your real `~/.config`:

```sh
export XDG_CONFIG_HOME=/tmp/hello-home FLICKOS_HELLO_PREFIX=/tmp/hello-root
usr/bin/flickos-hello show &
usr/bin/flickos-hello show              # Hello is already open.
```

Check what the harness can't (below):
- **by keyboard only:** Alt+G, arrow keys, Alt+C, Escape (A11Y-1/2/3);
- switch the style to Light in Settings while it's open, and see it follow.

**In the headless harness**, for screenshots and a measured start time,
without touching your session:

```sh
cd $TUTORIALS/flickos-headless-labwc
./start.sh --flickos
./run.sh $TUTORIALS/flickos-code-tutorial/work/flickos-hello/usr/bin/flickos-hello show &
./shot.sh hello
./run.sh flickos-layout style set light     # inside the harness only
./shot.sh hello-light
./stop.sh
```

The harness has its own home (`$HL/home`), so a greeting chosen there is saved
there. Both styles, as they came out (the harness puts the window in the
middle of a 1366×768 screen):
- Dark: Arc-Dark, "Hello, jon!", the combo showing `Default (Hello)`, Close at
  the bottom right.
- Light: the same in Arc's light colors, with no change to the code.

**Driving it in the harness.** `wlrctl pointer move DX DY` moves relative to
where the pointer is (it starts at about 100,110), and `wlrctl pointer click
left` clicks. That's how the tests for this guide opened the combo, picked
*Mabuhay* (the file was written, and the heading changed at once), and made
the folder read-only to see the error message.

**Three harness limits** found while writing this guide:

| Limit | What to do |
|---|---|
| GTK's **keyboard navigation doesn't respond to wtype**: Tab, arrows, mnemonics. Typing text into a field works, and so does a window's own key handler (Escape here), but focus never moves | Test keyboard use by hand on your desktop. Drive widgets in the harness with the pointer |
| In `--flickos` mode, typed keys didn't reach a normal window at all | Use plain `./start.sh` for anything that types. Use `--flickos` for looks and styles |
| **labwc crashed** (assertion, then segfault; 2 out of 2) when a GTK window was killed **while its combo list was open** | Close windows with Escape or the Close button, not `kill`, and never while a popup is open. It isn't known whether this happens outside the harness |

## 9. The desktop file

A program people open needs a desktop file (INT-1), or fuzzel, the start menu
and Settings' search won't find it. Copy
`finished/flickos-hello/usr/share/applications/flickos-hello.desktop`:

```ini
[Desktop Entry]
Type=Application
Name=Hello
Comment=Choose how the computer greets you
Icon=face-smile
Exec=flickos-hello show
Terminal=false
StartupNotify=false
Categories=Utility;
Keywords=greeting;hello;example;
```

- **`Name`** is the window's title (WIN-4). **`Comment`** is one sentence, in
  sentence case, with no final period, saying what the user can do.
- **`Icon`** is a freedesktop name (VIS-6). Numix-Circle doesn't have
  `face-smile` itself, but it *inherits* Numix, which does:

```sh
grep -i inherits /usr/share/icons/Numix-Circle/index.theme       # Inherits=Numix
python3 -c "import gi; gi.require_version('Gtk','3.0'); from gi.repository import Gtk; t=Gtk.IconTheme(); t.set_custom_theme('Numix-Circle'); print(t.has_icon('face-smile'))"   # True
```

- **The file name is the app id** (`flickos-hello.desktop` for `APP_ID =
  "flickos-hello"`), which is how labwc finds the title bar icon. In the
  harness, which has nothing installed, the title bar shows labwc's fallback
  icon instead.

```sh
desktop-file-validate usr/share/applications/flickos-hello.desktop && echo valid
```

**Tie it to the code with a test.** The last test in `stages/4/test_hello.py`
checks that the desktop file's `Name`, `Icon`, `Exec` and file name match
`TITLE`, `ICON` and `APP_ID`. If someone renames one side, the build fails,
instead of the menu silently showing the wrong name.

```sh
python3 -B -m unittest discover -s tests         # Ran 20 tests … OK
```

## 10. Measuring it

PERF-1's budgets, measured:

**A command, ≤ 200 ms:**

```sh
export XDG_CONFIG_HOME=/tmp/hello-home FLICKOS_HELLO_PREFIX=/tmp/hello-root
time usr/bin/flickos-hello greeting list >/dev/null
```

It took **72 ms** on your i3, five times out of five, most of it Python
starting. To see what's slow in the imports:

```sh
python3 -X importtime usr/bin/flickos-hello greeting list 2>&1 >/dev/null | sort -t'|' -k2 -n | tail -4
```

```
import time:       893 |       7824 | tempfile
import time:      2452 |       8278 |     enum
import time:      1025 |      11858 |   re
import time:      1834 |      15781 | argparse
```

The second column is cumulative microseconds: argparse, the largest, costs
16 ms. No `gi` in the list, which is what `NoGtkTest` guarantees.

**The window, ≤ 1 s to the first frame:**

```sh
cd $TUTORIALS/flickos-headless-labwc && ./start.sh --flickos
for i in 1 2 3 4; do ./run.sh ./first-frame.py $TUTORIALS/flickos-code-tutorial/work/flickos-hello/usr/bin/flickos-hello show; done
./stop.sh
```

```
[first-frame] flickos-hello: first window 'Hello' drawn 600 ms after start
[first-frame] flickos-hello: first window 'Hello' drawn 570 ms after start
[first-frame] flickos-hello: first window 'Hello' drawn 580 ms after start
[first-frame] flickos-hello: first window 'Hello' drawn 680 ms after start
```

That's 570–680 ms, inside the budget. Most of it is Python and GTK starting,
which every GTK 3 window pays. `first-frame.py` closes the window itself after
the first frame. The window must not already be open, or the lock answers
"already open" and there's nothing to measure.

## 11. Packaging 2.0

Everything from the deb tutorial, for a real change. Compare your `debian/`
with `finished/flickos-hello/debian/`:

| File | What changes |
|---|---|
| `control` | `Depends: python3, python3-gi, gir1.2-gtk-3.0` for the window, **with a comment** saying why (PKG-4). A new description |
| `install` | one more line: the desktop file to `usr/share/applications/` |
| `flickos-hello.1` | the man page describes the new commands and exit codes |
| `changelog` | a new version: 2.0 |

**Why 2.0 and not 1.1?** The stored value changed meaning: `hello.conf` now
holds an id. The version number itself is your choice. `dch -v` sets it
directly, where `-i` would pick 1.1:

```sh
cd work/flickos-hello
dch -v 2.0 -D trixie "Rewritten the FlickOS way: greetings from a list (greeting list|current|set ID|default), a user's own choice in ~/.config/flickos/hello, and a window (show). hello.conf now holds a greeting's id; the old text still works."
cd ../..
$TUTORIALS/flickos-deb-tutorial/build-and-check.sh work/flickos-hello
```

```
Depends: python3, python3-gi, gir1.2-gtk-3.0

--- files
-rw-r--r-- ./etc/xdg/flickos/hello.conf
-rwxr-xr-x ./usr/bin/flickos-hello
-rw-r--r-- ./usr/share/applications/flickos-hello.desktop
-rw-r--r-- ./usr/share/doc/flickos-hello/changelog.gz
-rw-r--r-- ./usr/share/doc/flickos-hello/copyright
-rw-r--r-- ./usr/share/man/man1/flickos-hello.1.gz

--- lintian
(nothing to report)
```

The build log shows the 20 tests running inside the build (`Ran 20 tests …
OK`). The tests need no GTK, so the package's `Build-Depends` stay
`python3` only (PKG-8: no display).

From here, the ship tutorial takes over: an upgrade test from 1.x to 2.0 is
exactly what its `upgrade-test.txt` does, with 2.0's `.deb` in the local repo.

## 12. Reviewing against the checklist

Before calling it done, go through `docs/hig/checklist.md` and mark each Must
rule. For flickos-hello:

| Rule | Result |
|---|---|
| INT-1 desktop file | ✓ step 9 |
| INT-4 in Settings | ✗ not done: a real program gets a row or tile in flickos-control (step 13) |
| INT-6 all layouts, Dark and Light | ◐ Dark and Light seen. The window doesn't depend on the layout |
| INT-7 live session | ✓ nothing to hide |
| INT-9 opt-in | ✓ nothing runs until opened |
| SET-1, 2, 4, 6, 7, 8 | ✓ stages 2–4 |
| SET-5 user's files | ✓ only its own `~/.config/flickos/hello` |
| WIN-1, 2, 3, 4, 10 | ✓ step 7 |
| WIN-11 loading | ✓ nothing is slow enough to need a spinner |
| TXT-6, TXT-7 | ✓ |
| VIS-2 no CSS | ✓ |
| VIS-6 icon | ✓ step 9 |
| A11Y-1, 2, 3 keyboard | ◐ in the code. Check by hand (the harness can't) |
| A11Y-8 icon-only buttons | ✓ none |
| PERF-1, 3 | ✓ step 10 |
| PKG-4 dependency comments | ✓ |
| PKG-8 tests | ✓ 20, no leaks |
| PKG-9 boot-test check | ✗ only once it's in the image (step 13) |
| CODE-1…9 | ✓ |

The ✗ and ◐ rows are the honest part: write them in the change's description,
so the review knows what's left.

## 13. What a real FlickOS program adds

flickos-hello stops where a real program keeps going. Each of these has a
working example in the repo:

| Addition | Why | Example to copy |
|---|---|---|
| **History**: `record()` appends every change to `$XDG_STATE_HOME/flickos/history.jsonl` in the shared format, and flickos-control learns to undo it | Settings → History shows and undoes changes | flick-tiler's `save_choice()`, `docs/design/flickos-history.md` |
| **A Settings page or row** that *runs* the owner's commands, never opening its files (SET-1) | INT-4 | flickos-control's tiling page and `flick-tiler` |
| **`state`**: all values as one JSON, so a page reads them in one run | SET-2, PERF-1 | `flickos-layout state` |
| **Reading off the main loop**: a page reads in a thread with a spinner | PERF-2, WIN-11 | flickos-control's `Ui.background()` |
| **A boot-test check** | PKG-9 | `CHECKS` in `tools/boot-test.py` |
| **A design doc** before the code, with phase 0's spike results | stages 3–4 of the path | `docs/design/flickos-phone.md` |

`$TUTORIALS/flickos-repo-tutorial` takes Hello the rest of the way: the
design doc, History, the Settings tile, a boot-test check, the docs and the
commits, in a copy of the repo.

## 14. Traps

1. **Testing "no display" by unsetting `WAYLAND_DISPLAY`.** GTK then falls back
   to `wayland-0` in your runtime folder, **which is your real desktop**. While
   writing this guide that opened a Hello window on your screen. Use an empty
   runtime folder instead:
   `env -u WAYLAND_DISPLAY -u DISPLAY XDG_RUNTIME_DIR=$(mktemp -d) usr/bin/flickos-hello show`
   gives `flickos-hello: can't open the window (no display)` and exit 1.
2. **`py_compile` or a plain `python3 -m unittest` leaves `__pycache__`** next
   to the program or the tests. Use `python3 -B`, and never let a
   `__pycache__` get into a package.
3. **A test that passes because a file is missing** (step 6). Run
   `leak-check.py` whenever you add tests.
4. **Writing `~/.config` by hand** instead of `XDG_CONFIG_HOME`. The sandbox,
   the tests and the harness all stop working.
5. **A selectable label first in the window** opens fully selected (step 7).
6. **A control that doesn't match what's saved** after a failure (step 7).
7. **Warnings repeated** because something is read several times. The first
   window read `hello.conf` three times and printed a broken file's warning
   three times. It now reads the machine's greeting once.
8. **configparser's multi-line errors.** Take the first line (TXT-7: one line
   per message).
9. **`dch` with a message that starts with `-`**, from the ship tutorial:
   `"--big …"` is read as an option.
10. **Killing a harness window while a popup is open** crashed labwc there
    (step 8).
11. **Changing an id that's already shipped.** Someone's file holds it. Add a
    new row, and keep understanding the old one (as `greeting_id()` does for
    1.0's texts).

## 15. Cheat sheet

```sh
# sandbox while developing
export XDG_CONFIG_HOME=/tmp/hello-home FLICKOS_HELLO_PREFIX=/tmp/hello-root
unset XDG_CONFIG_HOME FLICKOS_HELLO_PREFIX              # back to normal

# the program
usr/bin/flickos-hello [say NAME] | show | greeting list|current|set ID|default | --help

# compare with a stage
diff ../../stages/3/flickos-hello usr/bin/flickos-hello

# tests
python3 -B -m unittest discover -s tests -v
python3 -B -m unittest tests.test_hello.CommandTest.test_set_and_current   # one test
$TUTORIALS/flickos-code-tutorial/leak-check.py PACKAGE_FOLDER

# checks
desktop-file-validate FILE.desktop
time usr/bin/flickos-hello greeting list
python3 -X importtime usr/bin/flickos-hello greeting list 2>&1 >/dev/null | sort -t'|' -k2 -n | tail
env -u WAYLAND_DISPLAY -u DISPLAY XDG_RUNTIME_DIR=$(mktemp -d) usr/bin/flickos-hello show   # really no display

# harness
cd $TUTORIALS/flickos-headless-labwc && ./start.sh [--flickos]
./run.sh PROGRAM show &   ./shot.sh NAME   ./run.sh ./first-frame.py PROGRAM show   ./stop.sh

# package
dch -v 2.0 -D trixie "…"
$TUTORIALS/flickos-deb-tutorial/build-and-check.sh work/flickos-hello
```

## 16. Clean up

```sh
cd $TUTORIALS/flickos-code-tutorial
rm -rf work out /tmp/hello-home /tmp/hello-root
```

`stages/`, `finished/` and `leak-check.py` stay for next time.
