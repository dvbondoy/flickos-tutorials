# Notes phase 0 spikes

Phase 0 of `docs/design/flickos-notes.md` (section 5): four questions to
answer before Notes is built. Answers go in `results.md`; the kit's own
guide is `KIT-README.md` and the empty sheet `results-template.md`.

```
editor/    spike 3: GtkSourceView editor, own Markdown language, checklists
search/    spike 4: the search index over 5,000 generated notes
address/   spikes 1 and 2: make and check flicknotes:// addresses
```

## Spike 3: the editor (done)

```sh
cd editor
./editor.py                         # a window with a sample note: type in it
./editor.py --lang stock            # GtkSourceView's own Markdown, to compare
GTK_THEME=Arc ./editor.py           # the Light style's theme
./editor.py --selftest              # checklist clicks, Enter, Ctrl+L, undo
./editor.py --snapshot out.png      # draw it offscreen, no window opens
```

What to look at in the window:
- line 2 `#home #errands`: a tag (blue) in `own`, a big heading in `stock`;
- click a `[ ]`: it ticks, the line is struck through, Ctrl+Z puts it back;
- the pointer becomes a hand over a checkbox;
- Enter at the end of `- [ ] eggs…` starts `- [ ] `, Enter again ends the list;
- select a few plain lines, Ctrl+L: they become items; Ctrl+L again: plain;
- switch *Settings → Desktop Layout & Style* to Light while it's open: the
  dimmed markup and blue tags follow (the scheme is written at run time
  from the theme's colors into `editor/generated/`).

`notes-markdown.lang` is the language file, written from scratch:
headings need a space after the `#`s, so `#work` is a tag.

## Spike 4: search (done)

```sh
cd search
./gen-notes.py                      # 5,000 notes into notes/ (22 MB on disk)
./index.py notes cafe "#work bank" ñandu
```

`cafe` finds *café*, `ñandu` finds *Ñandú* (case and accents folded),
`#project` finds `#project/flickos`, and nothing in `.obsidian/` counts.

## Spikes 1 and 2: the phone (not run yet)

They need a Flutter build of a tiny receiver app, so this computer needs,
first (about 3 GB of downloads):
- a JDK: `sudo apt install openjdk-21-jdk-headless`;
- the Flutter SDK (unpacked in your home folder, no root);
- Android's command-line tools, platform and build tools (`sdkmanager`);
- the phone with USB debugging, or `adb` over Wi-Fi as in the phone
  screen spike, to install the app.

The addresses are ready:

```sh
cd address
./make-address.py groceries.md --cursor 25        # a real note's address
./make-address.py --decode "$(./make-address.py groceries.md)"
flickos-phone send "$(./make-address.py --size 32)"   # spike 2, 8/32/128 KB
```

512 KB can't be tried: Linux refuses any single argument over 131,071
bytes ("Argument list too long"), so that is the limit of
`flickos-phone send ADDRESS` whatever the phone does.

## Cleaning up

```sh
rm -rf search/notes editor/generated
```
