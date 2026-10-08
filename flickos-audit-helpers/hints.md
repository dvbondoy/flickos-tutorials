# Hints

Take one hint at a time. Hint 1 is a nudge, hint 2 names the technique, and
hint 3 is almost the answer. If you need hint 3, write down *why* you didn't
see it. That note is the most useful thing you'll write in this tutorial.

---

## Exercise 1: surface-map.py

**1.1** Policy files are XML. `xml.etree.ElementTree` reads them. Every
`<action>` has `<defaults>` (three children) and `<annotate key="…">`
elements. Use `glob` to find the files, and make the pattern skip
`packages/.build/` and `packages/*/debian/PKG/` (build copies of the same
files).

**1.2** To get the verbs without importing, run `ast.parse(source)` and walk
`tree.body` for an `ast.Assign` whose target is `Name(id="VERBS")` and whose
value is an `ast.Dict`. Its `keys` are `ast.Constant` nodes. `READ_ONLY` is
an `ast.Tuple` of constants. Then match verbs to actions by the
`org.freedesktop.policykit.exec.argv1` annotation.

**1.3** For part 2, one regex per mechanism is enough:
`^\s*(Exec\w*)=(.+)$` and `^\s*User=` in units (systemd drop-ins live in
`*.service.d/*.conf`, and dh_installsystemd units live in
`debian/*.service`), and the file names `debian/*.{preinst,postinst,prerm,postrm,config,triggers}`,
`etc/apt/apt.conf.d/*` (look for `Invoke`), `etc/sudoers.d/*`,
`polkit-1/rules.d/*`, udev `RUN+=`, `dbus-1/system-services/*`,
`etc/profile.d/*`. No `User=` means root.

## Exercise 3: sinks.py

**3.1** Start small: for one function, `ast.walk` it, keep the `ast.Call`
nodes, and turn `call.func` into a dotted name (`subprocess.run`,
`os.replace`). Print the ones in a set of known sinks. `ast.unparse(node)`
turns any expression back into readable source.

**3.2** A call graph is a dict `{function name: names it calls}`. Walk it
breadth-first from `VERBS[verb]`. For wrappers, loop until nothing changes:
a function is a wrapper if one of its own parameter names appears inside the
arguments of a sink call, or of a call to an already-known wrapper. That's a
*fixed-point* iteration, the same idea as taint analysis.

**3.3** Three details make the output right. (1) `gpasswd(*args)` and
`ufw(*args)` have `args.vararg` and no positional args, so each call
argument is one argv word. (2) `run_tool(cmd, stdin)`: the second argument
is stdin. (3) Functions passed as values (`undo_plan(…, simulate=simulate)`)
and parameter defaults (`def undo_plan(t, simulate=simulate)`) are edges in
the call graph too. If `VERBS` maps to data instead of a function name
(countme-helper), start from `main`.

## Exercise 5: harness.py

**5.1** `importlib.machinery.SourceFileLoader(name, path)` plus
`importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader))`
and `loader.exec_module(module)` load a file without `.py`. Then
`unittest.mock.patch.object(module, "KEYBOARD_DEFAULTS", fake_path)`
redirects one constant. Loop over `vars(module)` for the uppercase string
constants that start with `/etc/`, `/var/` or `/run/`.

**5.2** For the guard: `sys.addaudithook(hook)` calls `hook(event, args)` for
`"open"` (args: path, mode, flags), `"os.remove"`, `"os.rename"`,
`"os.mkdir"`, `"os.chmod"`, `"subprocess.Popen"`, `"os.exec"`,
`"os.posix_spawn"` and `"os.system"`. Raising in the hook aborts the
operation. A write is `mode` containing `w`, `a`, `x` or `+`, or `flags`
with `O_WRONLY|O_RDWR|O_CREAT|O_TRUNC`. Allow only paths under your fake roots.

**5.3** My first harness left a `harness-root-*` folder in `/tmp` after every
run, and the guard caused it. `shutil.rmtree` deletes with **`dir_fd`**: the
audit event's path is a bare name like `"etc"`, relative to an open
directory, not to the current directory. So `os.path.realpath("etc")`
pointed outside the fake root, the guard refused it, and `rmtree(…,
ignore_errors=True)` hid the refusal. Fix: when the last argument is a
`dir_fd` (an int ≥ 0), resolve the name against `os.readlink(f"/proc/self/fd/{dir_fd}")`.
Also remove the fake root from the allowed list only *after* deleting it.
Lesson: a guard that fails silently is a bug too, so test the cleanup, not
only the blocking.

## Exercise 6: attack.py

**6.1** "Refuse" means three things: exit code not 0, `result.commands`
empty, and `result.changed` empty. A helper that prints an error *after*
running `adduser` has not refused.

**6.2** For "accept" cases, check the output, not the exit code. Keyboard:
every `XKB…=` line matches `^XKB[A-Z]+="[A-Za-z0-9_:(),.+-]*"$`. chpasswd:
exactly one stdin line, starting with `name:`. adduser: the word after
`--comment` doesn't start with `-`.

**6.3** For packages-undo: `setup=lambda fake: open(fake("/var/log/apt/history.log"), "w").write(LOG)`
with a stanza like:

```
Start-Date: 2030-01-01  10:00:00
Commandline: apt-get install hello
Install: hello:amd64 (2.10-3), -oAPT::Get::Show-Versions=1:amd64 (1.0)
End-Date: 2030-01-01  10:00:05
```

The responder must say `amd64` for `dpkg --print-architecture`, list the
asked names as `NAME\tinstalled` for `dpkg-query`, and answer `apt-get -s
remove …` with `Remv NAME [1.0]` lines. Patch `live_system` to return
False, or the helper reads `/proc/cmdline`.

## Exercise 7: fuzz.py

**7.1** Seeds: one valid argv per verb (with a valid stdin for the
password verbs). One mutation per run: pick the argument position or stdin,
then pick a payload and where it goes (replace, prefix, suffix, middle). Use
`random.Random(seed)`, never the global `random`.

**7.2** The rules the reference uses: R1 no crash; R2 an argv word that
starts with `-` must be one of the helper's own string constants (collect
them with `ast.walk`, keeping every `ast.Constant` whose value is a str); R3
no control characters in argv; R4 a program's stdin is exactly one line; R5
a *new* line in a written file has no control characters and no `$( ` ; | &`
outside `"…"`, unless it's a comment.

**7.3** If R5 floods you with the logind file's header comment (`Power & Idle`),
you're checking comment lines and lines that were already there. Compare
with `result.before` and skip `#`, `//`, `;` lines. If R2 reports `-` alone
for adduser, that's a triage question (README Q9.5), not a fuzzer bug.

## Exercise 4: the hard questions

**Q6.4** Python's `re` documentation for `$`: "Matches the end of the string
**or just before the newline at the end of the string**". Try
`re.match(r"^[a-z]+$", "ann\n")`. Then `re.fullmatch(r"[a-z]+", "ann\n")`.

**Q6.5** `grep -n "comment" /usr/sbin/adduser` shows `'comment:s'`. In
Getopt::Long, `=s` is a mandatory value and `:s` an optional one. With an
optional value, a following word that looks like an option is *not* taken as
the value. Test:

```sh
perl -MGetopt::Long -e '@ARGV=("--comment","--system","ann");
  GetOptions("comment:s"=>\$c,"system"=>\$s); print "comment=[$c] system=[$s] rest=[@ARGV]\n"'
```

**Q6.9** Use the regex from the helper in `python3`:
`re.findall(r"([^\s,()]+):([A-Za-z0-9-]+) \(([^)]*)\)", "-oX::Y=1:amd64 (1.0)")`.
