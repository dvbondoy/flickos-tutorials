# Building a .deb, step by step

> Set `TUTORIALS` to the root of the [tutorials repository](https://github.com/dvbondoy/flickos-tutorials) and `FLICKOS` to your clone of [FlickOS](https://github.com/dvbondoy/FlickOS). Paths below use those two variables. Scripts read the FlickOS checkout from `FLICKOS_REPO` or `FLICKOS`.

You will make a small package, **flickos-hello**, from nothing. You build it,
look inside it, fix what lintian finds, install it, bring out version 1.1,
see what happens to a settings file you changed, and remove it again. Then you
map each step onto how the FlickOS repo does the same thing for its 13
packages.

Every command here was run while writing this guide, and the outputs shown are
the real ones.

- **Time:** about an hour.
- **What it touches:** nothing in the FlickOS repo. The only thing installed on
  your computer is flickos-hello (step 13), and step 16 removes it again.

## What's in this folder

| Path | What it is |
|---|---|
| `README.md` | This guide |
| `finished/flickos-hello/` | The answer key: the package as it looks at the end of step 12 (version 1.0). Compare your work with it when something doesn't build |
| `build-and-check.sh` | A helper you can reuse for any package folder, the repo's too. It builds from a copy and prints the control fields, the file list and lintian's verdict |
| `work/` | Created by you in step 3: your own copy, which you build up file by file |
| `out/` | Created in step 10: the built `.deb`s |

## Contents

0. [What a .deb is](#0-what-a-deb-is)
1. [The tools](#1-the-tools)
2. [The hard way first: dpkg-deb alone](#2-the-hard-way-first-dpkg-deb-alone)
3. [The program to package](#3-the-program-to-package)
4. [debian/source/format](#4-debiansourceformat)
5. [debian/changelog](#5-debianchangelog)
6. [debian/control](#6-debiancontrol)
7. [debian/rules](#7-debianrules)
8. [debian/install](#8-debianinstall)
9. [debian/copyright](#9-debiancopyright)
10. [Build it](#10-build-it)
11. [Look inside](#11-look-inside)
12. [lintian](#12-lintian)
13. [Install it and try it](#13-install-it-and-try-it)
14. [Change a setting the package owns](#14-change-a-setting-the-package-owns)
15. [Version 1.1](#15-version-11)
16. [Remove and purge](#16-remove-and-purge)
17. [Clean up](#17-clean-up)
18. [The same thing in the FlickOS repo](#18-the-same-thing-in-the-flickos-repo)
19. [Traps](#19-traps)
20. [Cheat sheet](#20-cheat-sheet)
21. [Going further](#21-going-further)

---

## 0. What a .deb is

A `.deb` is an **ar archive**, an old and simple format like a plain zip,
holding exactly three members:

```
flickos-hello_1.0_all.deb
├── debian-binary     the text "2.0": the format version
├── control.tar.xz    information ABOUT the package: control (name, version,
│                     Depends, description), md5sums, conffiles, and any
│                     maintainer scripts (postinst …)
└── data.tar.xz       the files themselves, with paths from / (./usr/bin/…)
```

When you install it, **dpkg** does three things:
1. It unpacks `data.tar.xz` onto `/`.
2. It writes down each file it placed, in `/var/lib/dpkg/info/NAME.list`.
3. It records the package's state in `/var/lib/dpkg/status`.

apt is the layer above dpkg: it finds packages in repositories, works out
dependencies, downloads, and then calls dpkg.

The name follows a fixed pattern: `NAME_VERSION_ARCH.deb`.
- `all` means the same file works on every architecture (scripts, config, images).
- `amd64` means it holds compiled machine code (FlickOS has one: sfwbar).

Look at a real one now. apt keeps the `.deb` files it downloaded:

```sh
ls /var/cache/apt/archives/*.deb | head      # may be empty if apt cleaned up
deb=$(ls /var/cache/apt/archives/*.deb | head -1)
ar t "$deb"                 # the three members
dpkg-deb -I "$deb"          # control information (-I = info)
dpkg-deb -c "$deb" | head   # the file list (-c = contents)
```

If that folder is empty, use one of FlickOS's own packages:
`$FLICKOS/config/packages.chroot/*.deb` (after
`sh packages/build.sh`).

**The tool chain you will use**, from top to bottom:

```
dch                  writes debian/changelog (the version comes from there)
dpkg-buildpackage    the one command you run to build
 └─ debian/rules     a makefile inside your package that says how to build
     └─ dh           debhelper: runs ~50 small dh_* tools in a fixed order
         └─ dpkg-deb --build   finally packs the .deb
lintian              checks the finished .deb against Debian's rules
apt / dpkg           install, upgrade, remove
```

## 1. The tools

They are already on your computer (FlickOS's build host needs them), but here
is what each package gives you:

| Package | Gives you | Used for |
|---|---|---|
| `dpkg-dev` | `dpkg-buildpackage`, `dpkg-genchanges`, … | the build command |
| `debhelper` | `dh` and all the `dh_*` tools | doing the build's steps for you |
| `build-essential` | gcc, make, … | `make` runs `debian/rules`. The compiler matters only for compiled packages |
| `devscripts` | `dch`, `debdiff`, `debc`, … | the changelog and comparing versions |
| `lintian` | `lintian` | checking the result |
| `dpkg` | `dpkg`, `dpkg-deb`, `dpkg-query` | installing and looking inside |

Check:

```sh
dpkg -l dpkg-dev debhelper build-essential devscripts lintian | tail -5
```

All five lines should start with `ii` (installed). If one doesn't:
`sudo apt install dpkg-dev debhelper build-essential devscripts lintian`.

**dch needs to know who you are.** It reads two variables, which your
`~/.bashrc` already sets (lines 116–117):

```sh
echo "$DEBFULLNAME <$DEBEMAIL>"      # Jon <dvbondoy@gmail.com>
```

That name and address go into every changelog entry, and must match
`Maintainer:` in `debian/control`.

## 2. The hard way first: dpkg-deb alone

Before using the helpers, make a package with nothing but `dpkg-deb`. That
shows you what a package really needs, and in the end what the helpers do
for you.

```sh
cd $TUTORIALS/flickos-deb-tutorial
mkdir -p raw/pkg/DEBIAN raw/pkg/usr/bin
printf '#!/bin/sh\necho "Hello from a hand-made package"\n' > raw/pkg/usr/bin/hello-by-hand
chmod 755 raw/pkg/usr/bin/hello-by-hand
cat > raw/pkg/DEBIAN/control <<'EOF'
Package: hello-by-hand
Version: 0.1
Architecture: all
Maintainer: Jon <dvbondoy@gmail.com>
Description: a package made with dpkg-deb alone
EOF
dpkg-deb --build --root-owner-group raw/pkg raw/hello-by-hand_0.1_all.deb
```

- `raw/pkg/` is a pretend root filesystem. Whatever is inside it (except
  `DEBIAN/`) ends up at the same path on the system.
- `DEBIAN/control` is the information that lands in `control.tar.xz`.
- `--root-owner-group` makes the files owned by root in the archive, not by
  you. Without it the installed files would belong to UID 1000.

That is a working `.deb` (you could install it). But ask lintian:

```sh
lintian raw/hello-by-hand_0.1_all.deb
```

```
E: hello-by-hand: extended-description-is-empty
E: hello-by-hand: no-changelog usr/share/doc/hello-by-hand/changelog.gz (native package)
E: hello-by-hand: no-copyright-file
W: hello-by-hand: description-synopsis-starts-with-article
W: hello-by-hand: no-manual-page [usr/bin/hello-by-hand]
W: hello-by-hand: non-standard-dir-perm 0775 != 0755 [usr/]
W: hello-by-hand: non-standard-dir-perm 0775 != 0755 [usr/bin/]
W: hello-by-hand: recommended-field hello-by-hand_0.1_all.deb Priority
W: hello-by-hand: recommended-field hello-by-hand_0.1_all.deb Section
```

Each line is a job you would have to do by hand:
- compress the changelog into `/usr/share/doc/NAME/`;
- copy the copyright file there;
- fix permissions;
- write md5sums;
- mark files in `/etc` as conffiles;
- and more.

debhelper does all of that, from the files in `debian/` that the next steps
write. That's why every real package, and every FlickOS package, is built with
`dpkg-buildpackage` + `dh`.

```sh
rm -rf raw
```

## 3. The program to package

This guide is about packaging, not about writing the program, so copy the
program from the answer key and delete its `debian/` folder. Steps 4–9 write
that folder again, file by file.

```sh
cd $TUTORIALS/flickos-deb-tutorial
mkdir -p work
cp -r finished/flickos-hello work/
rm -r work/flickos-hello/debian
cd work/flickos-hello
find . -type f | sort
```

```
./etc/xdg/flickos/hello.conf
./tests/test_hello.py
./usr/bin/flickos-hello
```

**The layout mirrors the installed system.** `usr/bin/flickos-hello` will
become `/usr/bin/flickos-hello`. Every FlickOS package is laid out like this,
and it makes it obvious where each file ends up.

- `usr/bin/flickos-hello`: a Python 3 program (stdlib only) that prints
  "Hello, NAME!". The greeting is read from `/etc/xdg/flickos/hello.conf`,
  then from `~/.config/flickos/hello`, and the last one wins. That's the same
  pattern as flickos-phone, flick-tiler and the others: a system default under
  `/etc/xdg/flickos/`, and the user's own file in `~/.config/flickos/`.
- `etc/xdg/flickos/hello.conf`: the system default. Because it is under
  `/etc`, dpkg will treat it as a **conffile**, a file the administrator may
  edit. Step 14 shows what that means.
- `tests/test_hello.py`: unit tests, which will run during every build. They
  import the program by its path, the same way FlickOS's tests do.

Run it and its tests right here, before any packaging:

```sh
./usr/bin/flickos-hello              # Hello, jon!  (no /etc/xdg/flickos/hello.conf yet → the built-in default)
./usr/bin/flickos-hello Ana          # Hello, Ana!
python3 -m unittest discover -s tests -v
```

**The rule:** make the program work before you package it. Packaging never
fixes a program, and it makes a broken one slower to debug.

## 4. debian/source/format

```sh
mkdir -p debian/source
echo '3.0 (native)' > debian/source/format
```

This says what kind of *source package* this is:
- **native** means the code is written for Debian itself, which is true of all
  FlickOS packages. The version is just `1.0`, `1.1`, …
- The other kind, `3.0 (quilt)`, is for someone else's program that Debian
  packages. It has an upstream tarball, and versions like `2.4-1`, where `-1`
  is Debian's packaging revision.

**That is why FlickOS versions never have a `-1`** (CLAUDE.md: "no `-1`
suffix"). waypaper and sfwbar are third-party code, but they are packaged as
native too, with versions like `2.7+flickos1`.

## 5. debian/changelog

**Never write this file by hand.** Its format is strict, and `dch` writes it
for you:

```sh
dch --create --package flickos-hello --newversion 1.0 -D trixie "First version: says hello."
cat debian/changelog
```

It may print `libdistro-info-perl is not installed, … release names are not
known.` That is harmless: it only means dch can't check that "trixie" is a real
release name.

```
flickos-hello (1.0) trixie; urgency=medium

  * First version: says hello.

 -- Jon <dvbondoy@gmail.com>  Mon, 28 Sep 2026 00:03:18 +0800
```

What each part means:

| Part | Meaning |
|---|---|
| `flickos-hello` | the source package's name. It must match `Source:` in `debian/control` |
| `(1.0)` | **the package's version. This is the only place it is set.** The .deb's `Version:` field, its file name and what apt compares all come from here |
| `trixie` | the distribution it is meant for. `UNRELEASED` would mean "work in progress". FlickOS never ships that (`dch -i` without `-D trixie` gives it) |
| `urgency=medium` | for Debian's migration between releases; unused by FlickOS |
| `  * …` | the entries: what changed, for the people reading it later |
| ` -- Name <mail>  date` | who and when. It starts with **one space** and has **two spaces** before the date. This is why you let dch write it |

The date matters too. dpkg-buildpackage sets every file's time in the `.deb`
to this date (`SOURCE_DATE_EPOCH`), so building the same source twice gives
the same package: a *reproducible build*. You'll see it in step 11.

## 6. debian/control

This file holds everything apt shows about the package. Create it with your
editor (`nano debian/control`), or copy the version below:

```
Source: flickos-hello
Section: utils
Priority: optional
Maintainer: Jon <dvbondoy@gmail.com>
Build-Depends: debhelper-compat (= 13),
               python3
Standards-Version: 4.7.0
Rules-Requires-Root: no

Package: flickos-hello
Architecture: all
Depends: python3,
         ${misc:Depends}
Description: says hello (example package)
 A tiny program that greets you, made as the example of FlickOS's
 tutorial on building a .deb. It shows the usual parts of a package:
 a program, a configuration file under /etc and unit tests that run
 while the package builds.
```

There are two blocks, called *stanzas*, separated by one empty line.

**The first stanza is about the source: how to build it.**

| Field | Meaning |
|---|---|
| `Source:` | the source package's name (the same as in the changelog) |
| `Section:` | a category for package managers: `utils`, `x11`, `admin`, … |
| `Priority:` | `optional` for almost everything |
| `Maintainer:` | who answers for it (the same as the changelog's trailer) |
| `Build-Depends:` | what must be installed **to build** it. `debhelper-compat (= 13)` picks debhelper's behaviour level 13, which all FlickOS packages use. `python3` is there because the tests run during the build |
| `Standards-Version:` | which version of Debian Policy the package claims to follow |
| `Rules-Requires-Root: no` | the build doesn't need to run as root or under fakeroot. The files still come out owned by root in the .deb |

**The second stanza is about one binary package: what gets installed.** A
single source can make several binary packages, but every FlickOS source
makes exactly one.

| Field | Meaning |
|---|---|
| `Package:` | the name you `apt install` |
| `Architecture:` | `all` (scripts, data) or `any` (compiled: one .deb per architecture) |
| `Depends:` | what must be installed **to run** it. apt installs these first, and refuses to keep the package without them |
| `${misc:Depends}` | a placeholder, a *substvar*, that debhelper fills in with anything its own tools need. It is usually empty, but always include it |
| `Description:` | the first line is the short summary (no article, no full stop, under ~80 characters). The following lines are the long description, and **each starts with one space**. An empty line inside it is written ` .` |

Other relation fields you'll meet in FlickOS's `control` files:

| Field | Meaning |
|---|---|
| `Recommends:` | installed by default with apt, but not in FlickOS's image (`--apt-recommends false`) and not on installed systems (the `00recommends` apt config). That's why CLAUDE.md says "use Depends" |
| `Suggests:` | never installed automatically |
| `Breaks: pkg (<< 1.7)` | "I don't work with that old a version of pkg": apt upgrades pkg too |
| `Conflicts:` | the two can never be installed together |

In FlickOS's `control` files you'll also see `#` comment lines above
`Depends:` that say why each dependency is there. dpkg ignores those lines.

## 7. debian/rules

This is a **makefile**: dpkg-buildpackage runs `debian/rules clean`, then
`debian/rules binary`.

```sh
cat > debian/rules <<'EOF'
#!/usr/bin/make -f

# No bytecode (__pycache__) next to the files that get installed.
export PYTHONDONTWRITEBYTECODE = 1

%:
	dh $@

# Skipped with DEB_BUILD_OPTIONS=nocheck.
override_dh_auto_test:
	python3 -m unittest discover -s tests -v
EOF
chmod +x debian/rules
```

Line by line:
- `#!/usr/bin/make -f` means the file is run by make. It **must be executable**.
- `export …` is an environment variable for every step. Here it stops Python
  from leaving `__pycache__` folders around.
- `%:` followed by `dh $@` means: for any target (clean, build, binary …), run
  `dh` with that target's name. The line with `dh` **starts with a TAB, not
  spaces**, because make requires it. Spaces give `*** missing separator. Stop.`
- `override_dh_auto_test:` means: when dh reaches its `dh_auto_test` step, run
  this instead. `dh_auto_test` would otherwise guess what the tests are from a
  Makefile or setup.py, and this package has neither. Every FlickOS package
  with tests has this same override.

To see which steps dh will run and in what order, without running them:

```sh
dh binary --no-act
```

It lists about 50 `dh_*` tools. Most find nothing to do here and stay silent
(`dh_installsystemd` when there is no service, `dh_installcron` when there is
no cron file …). The ones that matter for this package:

| Step | What it does here |
|---|---|
| `dh_auto_test` → your override | runs the unit tests. **A failure stops the build** |
| `dh_prep` | empties the staging folder `debian/flickos-hello/` |
| `dh_install` | copies the files listed in `debian/install` into `debian/flickos-hello/` |
| `dh_installdocs` | copies `debian/copyright` to `/usr/share/doc/flickos-hello/` |
| `dh_installchangelogs` | copies `debian/changelog` to the same folder |
| `dh_installman` | installs the manual page (from step 12 on) |
| `dh_compress` | gzips the changelog and man pages |
| `dh_fixperms` | sets permissions to 0755/0644 (the non-standard-dir-perm warning from step 2) |
| `dh_installdeb` | marks every file under `/etc` as a conffile, and adds any maintainer scripts |
| `dh_gencontrol` | writes `DEBIAN/control`, filling in the substvars and `Installed-Size` |
| `dh_md5sums` | writes `DEBIAN/md5sums` (so `debsums` can check installed files) |
| `dh_builddeb` | runs `dpkg-deb --build` on the staging folder, as you did by hand in step 2 |

Each tool has a manual page (`man dh_install`), and `man dh` explains
overrides.

## 8. debian/install

This tells `dh_install` which files go where:

```sh
cat > debian/install <<'EOF'
usr/bin/flickos-hello           usr/bin/
etc/xdg/flickos/hello.conf      etc/xdg/flickos/
EOF
```

Each line has **what to copy** (relative to the package folder, and wildcards
work) and **which folder to copy it into** (relative to `/`). The `tests/`
folder isn't listed, so it isn't installed. That is how a package keeps
build-only files out of the `.deb`.

**This is the file you forget.** Add a new file or folder to the package
without adding it here, and the build succeeds, but the file isn't in the
`.deb`. That's why FlickOS's "Shipping a change" says "new top-level folder in
the package? add it to debian/install".

When one package makes several binary packages, the file is called
`debian/PACKAGE.install`. Plain `debian/install` means "the only package".

## 9. debian/copyright

This says who wrote what, and under which licence. It uses a machine-readable
format called **DEP-5**. Copy it from the answer key, since it is the same text
as every FlickOS package's except the name:

```sh
cp ../../finished/flickos-hello/debian/copyright debian/
head -8 debian/copyright
```

```
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: flickos-hello
Upstream-Contact: Jon <dvbondoy@gmail.com>
Source: https://github.com/dvbondoy/FlickOS

Files: *
Copyright: 2026 Jon <dvbondoy@gmail.com>
License: GPL-3+
```

- `Files: *` covers everything by default: FlickOS's own work, GPL-3+.
- Each file from somewhere else gets its own `Files:` stanza under it. An
  example is flickos-layouts' Unsplash wallpapers (CLAUDE.md, "License").
- The `License: GPL-3+` stanza at the bottom holds the licence's text, or
  points to `/usr/share/common-licenses/GPL-3`.

Your `debian/` folder is now complete:

```sh
find debian | sort
```

```
debian
debian/changelog
debian/control
debian/copyright
debian/install
debian/rules
debian/source
debian/source/format
```

## 10. Build it

Still in `work/flickos-hello`:

```sh
dpkg-buildpackage -us -uc -b
```

| Option | Meaning |
|---|---|
| `-b` | binary only: make the `.deb` and not a source package (`.dsc` + `.tar.xz`), which FlickOS never publishes |
| `-us -uc` | **u**nsigned **s**ource, **u**nsigned **c**hanges: don't try to sign with a GPG key. The apt repo is signed later by `repo/publish.sh` instead |

Read the output from the top:

```
dpkg-buildpackage: info: source package flickos-hello
dpkg-buildpackage: info: source version 1.0              ← from debian/changelog
 debian/rules clean                                      ← clean first
dh clean
   dh_clean
 debian/rules binary                                     ← then build
dh binary
   dh_update_autotools_config
   dh_autoreconf
   debian/rules override_dh_auto_test                    ← your override
python3 -m unittest discover -s tests -v
test_no_files_gives_the_default ... ok
test_the_last_file_wins ... ok
test_the_shipped_file_says_hello ... ok
…
OK
   create-stamp debian/debhelper-build-stamp
   dh_prep
   dh_auto_install --destdir=debian/flickos-hello/
   dh_install                                            ← debian/install
   dh_installdocs                                        ← copyright
   dh_installchangelogs                                  ← changelog
   dh_perl
   dh_link
   dh_strip_nondeterminism
   dh_compress
   dh_fixperms
   dh_missing
   dh_installdeb                                         ← conffiles
   dh_gencontrol                                         ← DEBIAN/control
   dh_md5sums
   dh_builddeb
dpkg-deb: building package 'flickos-hello' in '../flickos-hello_1.0_all.deb'.
 dpkg-genbuildinfo --build=binary -O../flickos-hello_1.0_amd64.buildinfo
 dpkg-genchanges --build=binary -O../flickos-hello_1.0_amd64.changes
```

**The results go into the parent folder** (`work/`):

```sh
ls ..
```

| File | What it is |
|---|---|
| `flickos-hello_1.0_all.deb` | **the package** |
| `flickos-hello_1.0_amd64.buildinfo` | what was installed on the computer that built it (for reproducing the build) |
| `flickos-hello_1.0_amd64.changes` | a summary for uploading to a Debian-style archive. FlickOS's reprepro takes the `.deb` directly and ignores it |

The two extra files say `amd64` because they describe the computer the
package was built on, not the package.

**The build also leaves things in the source folder:**

```sh
ls -a debian
```

```
.debhelper  debhelper-build-stamp  files  flickos-hello  flickos-hello.substvars  …
```

`debian/flickos-hello/` is the staging folder, the pretend root that became
the `.deb`, just like `raw/pkg/` in step 2. The rest is debhelper's
bookkeeping. `debian/rules clean` (which runs `dh clean`) removes all of it,
and the next build begins with it anyway. In the FlickOS repo this is why
`packages/build.sh` builds from a copy: so nothing ends up in git by mistake.

From now on, build with the helper. It works the same way as `build.sh` (from
a copy), and shows you the result:

```sh
cd $TUTORIALS/flickos-deb-tutorial
rm -f work/*.deb work/*.buildinfo work/*.changes
(cd work/flickos-hello && debian/rules clean)
./build-and-check.sh work/flickos-hello
```

The `.deb` is now in `out/`, and the full build output is in
`out/flickos-hello.build.log`.

## 11. Look inside

```sh
deb=out/flickos-hello_1.0_all.deb
ar t $deb
```

```
debian-binary
control.tar.xz
data.tar.xz
```

```sh
dpkg-deb -I $deb
```

```
 new Debian package, version 2.0.
 size 2540 bytes: control archive=696 bytes.
      28 bytes,     1 lines      conffiles
     433 bytes,    13 lines      control
     203 bytes,     3 lines      md5sums
 Package: flickos-hello
 Version: 1.0
 Architecture: all
 Maintainer: Jon <dvbondoy@gmail.com>
 Installed-Size: 16
 Depends: python3
 …
```

What to notice:
- `Depends: python3`: `${misc:Depends}` was empty, and it disappeared.
- `Installed-Size: 16` is in KB, calculated by dh_gencontrol. It's what apt
  shows as "After this operation, 16 kB of additional disk space will be used".
- `conffiles`: dh_installdeb found a file under `/etc`.

```sh
dpkg-deb -c $deb
```

```
drwxr-xr-x root/root         0 2026-09-28 00:03 ./
drwxr-xr-x root/root         0 2026-09-28 00:03 ./etc/
…
-rw-r--r-- root/root       149 2026-09-28 00:03 ./etc/xdg/flickos/hello.conf
-rwxr-xr-x root/root      1074 2026-09-28 00:03 ./usr/bin/flickos-hello
-rw-r--r-- root/root       144 2026-09-28 00:03 ./usr/share/doc/flickos-hello/changelog.gz
-rw-r--r-- root/root       898 2026-09-28 00:03 ./usr/share/doc/flickos-hello/copyright
```

Here too:
- The owner is `root/root`, although you built it as yourself.
- Permissions are 0755/0644 (`dh_fixperms`).
- Every file's time is the changelog entry's date (step 5): that's
  `SOURCE_DATE_EPOCH` at work.
- There is no `tests/`, because `debian/install` didn't list it.

To read one file of the control part, or to unpack all of it without
installing anything:

```sh
dpkg-deb -f $deb Version Depends        # single control fields
dpkg-deb -I $deb conffiles              # one member of control.tar.xz
dpkg-deb -x $deb /tmp/look && find /tmp/look -type f && rm -r /tmp/look   # data.tar.xz → a folder
```

`tools/package-cost.py out/flickos-hello_1.0_all.deb`, run in the FlickOS
repo, would show what the package adds to the image: here only itself,
because python3 is already there.

## 12. lintian

`build-and-check.sh` already ran lintian. Run it by hand, with `-i` to have
each finding explained:

```sh
lintian -i out/flickos-hello_1.0_all.deb
```

```
W: flickos-hello: no-manual-page [usr/bin/flickos-hello]
N:
N:   Each binary in /usr/bin, /usr/sbin, /bin, /sbin or /usr/games should have
N:   a manual page
…
```

How to read lintian:

| Letter | Meaning | What to do |
|---|---|---|
| `E:` | error: breaks Debian policy | fix it |
| `W:` | warning: probably wrong | fix it, or override it with a reason |
| `I:` | information (only shown with `-I`) | read it |
| `P:` | pedantic (only with `--pedantic`) | optional |
| `N:` | the explanation of the line above (from `-i`) | |

The tag name (`no-manual-page`) is searchable, and `lintian-explain-tags
no-manual-page` prints the explanation on its own.

FlickOS's packages carry this same warning, and `docs/04-packages.md` calls it
"expected for small distro packages". There are two honest answers to any
warning, and FlickOS uses both. Here, fix it, since it's worth knowing how.

**Answer 1: fix it by writing a manual page.** Man pages are written in
*roff*, a markup from the 1970s. Copy the answer key's page and read it next
to its output:

```sh
cp finished/flickos-hello/debian/flickos-hello.1 work/flickos-hello/debian/
man -l work/flickos-hello/debian/flickos-hello.1     # -l: read this file, not an installed page
echo 'debian/flickos-hello.1' > work/flickos-hello/debian/manpages
```

`debian/manpages` lists the man pages for `dh_installman`. It reads the
section from the file name (`.1` = user commands), installs the page into
`/usr/share/man/man1/`, and `dh_compress` gzips it.

Rebuild. A package that has never been released can be rebuilt at the same
version as often as you like. Only a version that someone else has installed,
or that has gone to the apt repo, is frozen (step 15).

```sh
./build-and-check.sh work/flickos-hello
```

```
--- files
-rw-r--r-- ./etc/xdg/flickos/hello.conf
-rwxr-xr-x ./usr/bin/flickos-hello
-rw-r--r-- ./usr/share/doc/flickos-hello/changelog.gz
-rw-r--r-- ./usr/share/doc/flickos-hello/copyright
-rw-r--r-- ./usr/share/man/man1/flickos-hello.1.gz

--- lintian
(nothing to report)
```

**Answer 2: override it with a written reason**, when the finding is
deliberate. For example, flickos-welcome puts a marker in `/etc/skel`, which
lintian warns about. It keeps it with the file
`debian/flickos-welcome.lintian-overrides`:

```
# The first-login marker (flickos-welcome first-run) is meant only for accounts
# created after installation, which is exactly what /etc/skel does.
package-contains-file-in-etc-skel [etc/skel/.config/*]
```

The comment is the point: it tells the next reader why.

Your `work/flickos-hello` should now match `finished/flickos-hello` (apart
from the changelog's time):

```sh
diff -r finished/flickos-hello work/flickos-hello
```

## 13. Install it and try it

```sh
sudo apt install ./out/flickos-hello_1.0_all.deb
```

- **The `./` matters.** Without a slash, apt treats the argument as a package
  *name* to find in its repositories, and fails with `Unable to locate package`.
- **apt, not `dpkg -i`:** apt installs the package's Depends first (python3 is
  already there, but a new package's dependencies usually aren't). `dpkg -i`
  only installs the one file and leaves the package half-configured if
  something is missing.
- apt may end with
  `N: Download is performed unsandboxed as root as file '…' couldn't be accessed by user '_apt'. - pkgAcquire::Run (13: Permission denied)`.
  That's because your home folder is private (`drwx------`) and apt's
  download user can't read it, so root reads it instead. It's harmless.

Now try it, and ask the system about it:

```sh
flickos-hello                        # Hello, jon!
man flickos-hello
dpkg -l flickos-hello                # ii = wanted: install, state: installed
dpkg -L flickos-hello                # every file it installed (from /var/lib/dpkg/info/flickos-hello.list)
dpkg -S /usr/bin/flickos-hello       # which package owns this file?
apt-cache policy flickos-hello       # installed version, and where versions come from
apt-cache show flickos-hello         # the control fields as apt sees them
cat /var/lib/dpkg/info/flickos-hello.conffiles
ls /usr/share/doc/flickos-hello/
```

Try the user's own setting, the file that wins over the system's:

```sh
mkdir -p ~/.config/flickos
printf '[Hello]\nGreeting=Howdy\n' > ~/.config/flickos/hello
flickos-hello                        # Howdy, jon!
rm ~/.config/flickos/hello
```

## 14. Change a setting the package owns

`/etc/xdg/flickos/hello.conf` is a conffile. That is dpkg's promise to the
administrator: **"I'll never silently overwrite changes you made to this
file."** Make a change, as an administrator would:

```sh
sudo sed -i 's/^Greeting=Hello/Greeting=Hi/' /etc/xdg/flickos/hello.conf
flickos-hello                        # Hi, jon!
```

dpkg saved the file's md5 at install time
(`grep -A1 Conffiles: /var/lib/dpkg/status` shows them for all packages).
That's how it knows you changed it. Step 15 ships a new version of this file
and shows what dpkg does about it.

## 15. Version 1.1

Version 1.0 is now installed on a computer, so **it is frozen.** Any change,
however small, needs a new version:
- apt only ever upgrades to a *higher* version. The same version with other
  content looks "already installed" and never arrives.
- FlickOS's apt repo (reprepro) refuses a different file at a version it
  already has.

**First, bump the version:**

```sh
cd work/flickos-hello
dch -i -D trixie "The greeting is Mabuhay."
head -5 debian/changelog
```

```
flickos-hello (1.1) trixie; urgency=medium

  * The greeting is Mabuhay.

 -- Jon <dvbondoy@gmail.com>  …
```

`-i` means increment: 1.0 → 1.1. `-D trixie` avoids `UNRELEASED`. This is the
exact command CLAUDE.md asks for with every FlickOS package change.

**Next, make the change:**

```sh
sed -i 's/^Greeting=Hello/Greeting=Mabuhay/' etc/xdg/flickos/hello.conf
cd ../..
./build-and-check.sh work/flickos-hello
```

**The build fails.** That's on purpose:

```
test_the_shipped_file_says_hello (…) ... FAIL
…
AssertionError: 'Mabuhay' != 'Hello'
…
make[1]: *** [debian/rules:11: override_dh_auto_test] Error 1
dpkg-buildpackage: error: debian/rules binary subprocess returned exit status 2
==> the build failed; the whole log is …/out/flickos-hello.build.log
```

A test checked what the shipped file says. You changed the file, so the test
stopped the build before a `.deb` existed. This is the reason FlickOS's tests
run in `override_dh_auto_test`: **a package with failing tests can't be
built, and so can't be published.** When you changed the behaviour on
purpose, update the test to match:

```sh
sed -i 's/test_the_shipped_file_says_hello/test_the_shipped_file_says_mabuhay/;
        s/"etc\/xdg\/flickos\/hello.conf")]), "Hello")/"etc\/xdg\/flickos\/hello.conf")]), "Mabuhay")/' \
    work/flickos-hello/tests/test_hello.py
./build-and-check.sh work/flickos-hello
```

(To try a build quickly without the tests:
`DEB_BUILD_OPTIONS=nocheck ./build-and-check.sh work/flickos-hello`. Never do
that for a build you'll publish.)

**Compare the two versions:**

```sh
debdiff out/flickos-hello_1.0_all.deb out/flickos-hello_1.1_all.deb
```

```
File lists identical (after any substitutions)

Control files: lines which differ (wdiff format)
------------------------------------------------
Version: [-1.0-] {+1.1+}
```

debdiff compares *which* files there are and the control fields, not what the
files contain. To see the content changes, unpack both and diff them:

```sh
mkdir -p /tmp/cmp
dpkg-deb -x out/flickos-hello_1.0_all.deb /tmp/cmp/1.0
dpkg-deb -x out/flickos-hello_1.1_all.deb /tmp/cmp/1.1
diff -r /tmp/cmp/1.0 /tmp/cmp/1.1; rm -r /tmp/cmp
```

```
diff -r 1.0/etc/xdg/flickos/hello.conf 1.1/etc/xdg/flickos/hello.conf
4c4
< Greeting=Hello
---
> Greeting=Mabuhay
Binary files 1.0/usr/share/doc/flickos-hello/changelog.gz and 1.1/…/changelog.gz differ
```

Do this before publishing any FlickOS package: it's how you catch a file that
went missing, or one that changed by accident.

**Upgrade:**

```sh
sudo apt install ./out/flickos-hello_1.1_all.deb
```

The package ships a new `hello.conf`, and you changed yours in step 14, so
dpkg stops and asks:

```
Configuration file '/etc/xdg/flickos/hello.conf'
 ==> Modified (by you or by a script) since installation.
 ==> Package distributor has shipped an updated version.
   What would you like to do about it ?  Your options are:
    Y or I  : install the package maintainer's version
    N or O  : keep your currently-installed version
      D     : show the differences between the versions
      Z     : start a shell to examine the situation
 The default action is to keep your current version.
*** hello.conf (Y/I/N/O/D/Z) [default=N] ?
```

Press `D` to see the difference, then `N` to keep yours. Then look:

```sh
flickos-hello                        # Hi, jon!  (yours was kept)
ls /etc/xdg/flickos/hello.conf*      # hello.conf  hello.conf.dpkg-dist
cat /etc/xdg/flickos/hello.conf.dpkg-dist    # the package's new version, for you to compare
```

The outcome depends on who changed the file:

| You changed it? | The package changed it? | dpkg does |
|---|---|---|
| no | no | nothing |
| no | yes | replaces it silently ("Installing new version of config file …") |
| yes | no | keeps yours silently |
| yes | yes | **asks** (above). With `N`, the new one lands next to yours as `.dpkg-dist`; with `Y`, yours is kept as `.dpkg-old` |

**Why this matters for FlickOS:**
- Every file under `/etc` in a FlickOS package is a conffile:
  `/etc/xdg/flickos/*.conf`, labwc's `rc.xml` in `/etc/xdg`, and the rest.
- A user who edited one of them stops getting your changes to it. On an
  unattended upgrade, dpkg keeps their version.
- That's one reason FlickOS keeps user choices in `~/.config/flickos/`
  (written by the program), and generated config in `$XDG_RUNTIME_DIR`, and
  never asks users to edit `/etc`.
- Files under `/usr` are never conffiles. dpkg always replaces them, which is
  why FlickOS's defaults that must keep up with upgrades live in
  `/usr/share/flickos/`.

## 16. Remove and purge

```sh
sudo apt remove flickos-hello
dpkg -l flickos-hello                # rc = removed, config files remain
ls /etc/xdg/flickos/hello.conf*      # still there
```

**remove** deletes the program but keeps the conffiles, so reinstalling gives
the administrator their settings back.

```sh
sudo apt purge flickos-hello
dpkg -l flickos-hello                # no packages found
ls /etc/xdg/flickos/hello.conf*      # gone, .dpkg-dist too
```

**purge** also deletes the conffiles and forgets the package.

Neither of them touches your home folder: `~/.config/flickos/hello` (if you
left one) is yours to delete. Packages never write into `$HOME`, which is the
same rule as FlickOS's "never copy FlickOS config into `$HOME`".

To find packages that were removed but never purged:
`dpkg -l | grep '^rc'`.

## 17. Clean up

```sh
cd $TUTORIALS/flickos-deb-tutorial
rm -rf work out
```

`finished/` and `build-and-check.sh` stay for next time.

## 18. The same thing in the FlickOS repo

Everything above is how the repo works. The table maps each step onto it:

| This guide | The FlickOS repo |
|---|---|
| `work/flickos-hello/` | `packages/NAME/` (the folder name is the package name) |
| `./build-and-check.sh work/flickos-hello` | `sh packages/build.sh` builds **all** packages, each from a copy in `packages/.build/`. It fails when two packages contain the same file (dpkg would say "trying to overwrite" deep inside `lb build`), then copies the `.deb`s to `config/packages.chroot/`, where the ISO build takes them |
| `dch -i -D trixie "…"` before a change | the same, and CLAUDE.md requires it for every content change. Never `UNRELEASED`, never `-1` |
| a package's tests in `override_dh_auto_test` | the same in flickos-layouts, -control, -menu, -phone, -shortcuts, -welcome, flick-tiler |
| `sudo apt install ./out/…deb` to try it | `sudo apt install ./config/packages.chroot/NAME_*.deb` on your own FlickOS, then reload the panel or labwc, or log out and in (docs/09 "Shipping a change") |
| a `.deb` in `out/` | `repo/publish.sh && repo/upload.sh` put it in the signed apt repo, **the only way installed systems get it**. The ISO is only a snapshot for new installs |

**Changing an existing FlickOS package:**

```sh
cd $FLICKOS/packages/flickos-welcome
dch -i -D trixie "What changed."
# edit files; a new top-level folder → debian/install
cd ../.. && sh packages/build.sh
lintian config/packages.chroot/flickos-welcome_*.deb
sudo apt install ./config/packages.chroot/flickos-welcome_*.deb   # try it on your desktop
```

You can also use this folder's helper on any repo package, because it builds
from a copy and never touches the repo:

```sh
$TUTORIALS/flickos-deb-tutorial/build-and-check.sh packages/flickos-welcome
```

**If the change adds a dependency**, bump the package that depends on it too
(CLAUDE.md, "Package versions").

**If the change adds a new program to Depends**, check its cost first with
`tools/package-cost.py PKG` (HIG PERF-7).

**A new FlickOS package** (docs/04 "Creating a new package") is steps 3–12 of
this guide, plus:
1. Copy a similar package's `debian/` rather than writing from nothing:
   - flickos-welcome for one Python file with GTK;
   - flickos-phone for stdlib-only Python;
   - flickos-archive-keyring for pure data.
2. Replace the name in `control`, `install`, `copyright` and any
   `*.lintian-overrides`, and start a fresh changelog with `dch --create`.
3. Add it to flickos-desktop's `Depends:` (and bump flickos-desktop). Nothing
   installs a package that nothing depends on.
4. If FlickOS is broken without it, add it to `REQUIRED` in
   `config/hooks/normal/0010-sanity.hook.chroot`.
5. If it's user-visible, add a boot-test check to `CHECKS` in
   `tools/boot-test.py`.
6. Document it: its line in CLAUDE.md, `docs/01` and `docs/04`, and its HIG
   checklist (`docs/hig/checklist.md`).

**Testing a local build that has the same version as the published one:**
- Say you built flickos-welcome 1.4 locally with extra changes, installed it,
  and later publish a different 1.4.
- apt thinks you already have 1.4, and never replaces your local build.
- Always `dch -i` before you install a changed build. If you reused a version
  number (`dch -a`), check `repo/public/pool/` first to see whether that
  version was published already.

## 19. Traps

1. **A file isn't in the .deb.** You forgot `debian/install`. The build
   doesn't complain. Check with `dpkg-deb -c`, or read `build-and-check.sh`'s
   file list every time.
2. **`*** missing separator. Stop.`** `debian/rules` has spaces where make
   needs a TAB.
3. **`debian/rules: Permission denied`.** It lost its executable bit:
   `chmod +x debian/rules`. git keeps the bit, but some copy tools don't.
4. **apt doesn't upgrade, or reprepro refuses.** The version wasn't bumped.
   Same version plus different content never works.
5. **`UNRELEASED` in the changelog.** `dch -i` without `-D trixie`. Fix it with
   `dch -r -D trixie ""`, which marks the top entry released.
6. **`Unable to locate package out/…`.** You wrote `apt install out/x.deb`
   instead of `apt install ./out/x.deb`.
7. **`dpkg -i` left a package half-installed** (`iU` in `dpkg -l`) because a
   dependency was missing. `sudo apt -f install` finishes the job, fetching the
   dependency.
8. **It works on your computer but not on a fresh install.** A dependency is
   missing from `Depends:`, and your desktop happened to have it installed.
   `dpkg-deb -I` shows what the package actually asks for. The QEMU boot test
   (`tools/boot-test.py`) catches this, because the image has only what's
   declared.
9. **Tests pass here, fail in CI (or the other way round).** The tests read
   something from your desktop: your `~/.config`, running programs, installed
   packages. CI's container has none of that. Tests should use fake paths.
10. **Build leftovers in git.** You built with `dpkg-buildpackage` inside
    `packages/NAME/`. Run `debian/rules clean`, and delete the `../*.deb`,
    `.buildinfo` and `.changes` files, or build with `packages/build.sh` or
    `build-and-check.sh`, which use copies.
11. **Two packages ship the same file.** dpkg refuses the second one
    ("trying to overwrite …"). `packages/build.sh` checks your own packages.
    For files of Debian's packages, check with `dpkg -S PATH` before adding one
    (docs/09 "Three rules").
12. **Your change to an `/etc` file never reaches a user.** They edited it,
    so dpkg keeps their version (step 15). Put defaults that must keep up with
    upgrades under `/usr/share/…`, and keep user choices in a separate file.

## 20. Cheat sheet

```sh
# write the changelog
dch --create --package NAME --newversion 1.0 -D trixie "First version."   # new package
dch -i -D trixie "What changed."        # next version (1.0 → 1.1)
dch -a "Another change."                # add a line to the top entry (unreleased version only!)

# build (in the package folder)
dpkg-buildpackage -us -uc -b            # → ../NAME_VERSION_all.deb
DEB_BUILD_OPTIONS=nocheck dpkg-buildpackage -us -uc -b   # without the tests
debian/rules clean                      # remove the build's leftovers
dh binary --no-act                      # which dh_* steps would run

# build from a copy and check (this folder's helper)
./build-and-check.sh PACKAGE_FOLDER [OUT_FOLDER]

# look inside a .deb
ar t FILE.deb                           # debian-binary, control.tar.xz, data.tar.xz
dpkg-deb -I FILE.deb                    # control information
dpkg-deb -f FILE.deb Version Depends    # single fields
dpkg-deb -c FILE.deb                    # file list
dpkg-deb -x FILE.deb DIR                # unpack the files
lintian -i FILE.deb                     # check, with explanations
debdiff OLD.deb NEW.deb                 # file list + control changes between versions

# install and ask
sudo apt install ./FILE.deb             # the ./ matters
dpkg -l NAME                            # state: ii installed, rc removed with config left
dpkg -L NAME                            # files it installed
dpkg -S /path/to/file                   # which package owns a file
apt-cache policy NAME                   # versions and where they come from
sudo apt remove NAME                    # keep conffiles
sudo apt purge NAME                     # delete conffiles too

# the FlickOS repo
sh packages/build.sh                    # all packages → config/packages.chroot/
repo/publish.sh && repo/upload.sh       # to installed systems
tools/package-cost.py FILE.deb          # what it adds to the image
```

## 21. Going further

These are things this example didn't need, and where to find them in FlickOS
when you do:

- **Symlinks:** `debian/links`, with lines like
  `usr/share/X usr/share/Y`. See flickos-layouts, which links each layout's
  wallpaper into `/usr/share/backgrounds/flickos/`.
- **Maintainer scripts** (`debian/NAME.postinst`, `prerm`, `postrm`,
  `preinst`) run as root during install and remove. They are powerful and easy
  to get wrong. FlickOS has exactly one package with hand-written ones:
  flickos-branding, with its `postinst` and a `.triggers` file for dpkg file
  triggers. Prefer the declarative helpers:
  - `debian/NAME.sysusers` creates a group (flickos-greeter's `autologin`);
  - `debian/links` for symlinks;
  - `debian/NAME.maintscript` with `rm_conffile /etc/old.conf 1.2~` deletes a
    conffile a new version no longer ships. Without it, the old file stays
    forever on upgraded systems.
- **Compiled packages:** `Architecture: any`. `dh_auto_configure` and
  `dh_auto_build` find meson, cmake or autotools by themselves, and the build
  needs the libraries' `-dev` packages in `Build-Depends`. See sfwbar.
- **Clean builds:** `sbuild` or `pbuilder` build in an empty chroot that has
  only the `Build-Depends`, which proves the list is complete. FlickOS's CI
  gets the same guarantee from its fresh `debian:trixie` container.
- **Reading:**
  - `man dh`, `man dh_install`, `man deb-control`, `man deb-changelog`,
    `man dpkg-buildpackage`, `man debhelper` (compat levels);
  - the *Guide for Debian Maintainers* (`sudo apt install debmake-doc`, then
    `/usr/share/doc/debmake-doc/`);
  - the Debian Policy Manual (`sudo apt install debian-policy`), for when
    lintian cites a section.
