# FlickOS tutorials

Worked guides for taking a FlickOS feature from an idea to a release. The example is **flickos-hello**. The same four core guides are published on the website, under [Learn](https://flickos.net/learn/).

```sh
export TUTORIALS="$HOME/flickos-tutorials"   # this repository
export FLICKOS="$HOME/FlickOS"               # your FlickOS checkout
```

Paths in the guides use those two variables. Scripts read the FlickOS checkout from `FLICKOS_REPO` or `FLICKOS`, and otherwise look in `~/Documents/Projects/FlickOS`.

| Folder | What it is |
|---|---|
| `flickos-deb-tutorial` | Build a `.deb` by hand, then with debhelper |
| `flickos-code-tutorial` | Rewrite flickos-hello as a FlickOS program, with unit tests |
| `flickos-ship-tutorial` | QEMU, the boot test, a local apt repo, upgrades, publishing |
| `flickos-repo-tutorial` | Design doc, HIG review, wiring the package into the repo |
| `flickos-headless-labwc` | An isolated labwc for repeatable window tests |
| `flickos-snip-spike` | A spike from questions to a design |
| `flickos-spike-kit` | A starting folder for the next spike |
| `flickos-phone-spike` | A finished spike, told afterwards |

Answer keys live next to each guide (`finished/`, `stages/`, `versions/`). Compare your work with them when a step does not build.

## Not in this repository

The phone spike's private key, paired-phone certificate, session log, received photos, and the vendored kdeconnect-kde sources stay on the machine where that spike was run. `flickos-phone-spike/README.md` says what each one was for.
