# Notes (flickos-notes) phase 0: results

Date: 2026-10-02  Design doc: `docs/design/flickos-notes.md`  Machine: `machine.txt`
(i3-4030U, 4 CPUs, FlickOS 2.1)

## Questions

Riskiest first. Spikes 1 and 2 need the Flutter app and the phone; 3 and 4
were run on the computer.

| # | Question | Why it matters | Prediction | Result | Evidence |
|---|---|---|---|---|---|
| Q1 (spike 1) | Does a Flutter app that claims `flicknotes` get the address on a cold start, a warm start, phone locked and unlocked? | ADR-004 rests on it | yes, through `app_links`; locked: after unlocking | **yes** (2026-10-02, HMD CREST): one tap on KDE Connect's notification opened the app, no chooser; cold start, warm start, and locked (after unlocking) all intact | runs 8–11; our own Kotlin channel instead of `app_links` |
| Q2 (spike 2) | Largest address that arrives intact? | section 4's 48 KB limit | 8 and 32 KB fine; 128 KB maybe; 512 KB fails (Android's 1 MB Binder limit, and an intent's string is UTF-16) | **everything the computer can send:** 8, 32 and 128 KB (131,059 characters) arrived intact. 512 KB can't be sent at all | Linux caps one argument at 131,071 bytes (`MAX_ARG_STRLEN`, 32 pages): passing `./make-address.py --size 512` to any program gives "Argument list too long" |
| Q3 (spike 3) | Can GtkSourceView 4 show Markdown in both styles without fixed colors? | ADR-002, VIS-1/2 | yes with the stock language | **yes, but not with the stock language**: needs our own language file and a scheme made at run time | `editor/own-*.png`, `editor/stock-*.png` |
| Q3a | Is `#work` at the start of a line a tag, not a heading? | ADR-003 tags | no: the stock rule is `^#+.+` | stock: **heading** (confirmed). Own language (headings need `# `): **tag** | `stock-Arc-Dark.png`, line 2 |
| Q3b | Can markup be dimmed with no color in the scheme? | ADR-002 says "dimmed" | no | **no** (a scheme holds only fixed colors), **but** a scheme written at run time from the theme's own text, base and selected colors works, and is rewritten on a style switch | `write_scheme()`; a live switch Arc-Dark → Arc → Arc-Dark printed the new colors each time |
| Q3c | Code in monospace? | ADR-002 | needs a tag | a scheme can't set a font, **but** the language's context class `code` is a GtkTextTag named `gtksourceview:context-classes:code`, and setting its `family` once is enough | `on_highlight()` |
| Q3d | Checklists (ADR-006): click on `[ ]`, Enter continues, Ctrl+L, one undo step each | ADR-006 | yes with `begin/end_user_action` | **yes, 16/16 checks** | `./editor.py --selftest` |
| Q4 (spike 4) | Index 5,000 notes: time and memory | PERF-2/3: the window must not wait | < 1 s, < 20 MB | **about 1.0 s, +6.4 MB** (the first try took 1.8 s); each query takes about 7 ms | `search/index.py notes` |

## Cost (HIG PERF-7)

| What | Number | How measured |
|---|---|---|
| disk: packages and KB added to the image | 1 package, 83 KB (19 KB download): `gir1.2-gtksource-4`; the library is already in the image | `tools/package-cost.py gir1.2-gtksource-4` |
| memory: search index of 5,000 notes (4.7 MB of text) | +6.4 MB RSS; whole process 10.3 MB PSS | `index.py`'s RSS, `/proc/PID/smaps_rollup` while held |
| time: index of 5,000 notes | 1.0 s (read 0.17, words 0.45, tags 0.05, items 0.07) | `index.py`, one step at a time |
| time: one search | 7 ms | `index.py notes QUERY…` |
| memory: the window | not measured: the editor spike isn't the window | phase 1 |

## Runs

| Run | Command | Prediction | Result | Notes |
|---|---|---|---|---|
| 1 | `editor/editor.py --selftest` | pass | 16/16 | |
| 2 | `GTK_THEME=Arc-Dark editor/editor.py --lang stock --snapshot OUT.png` | `#home` a heading | it is | |
| 3 | `… --lang own --snapshot …`, both styles | right | right | |
| 4 | `search/index.py notes …`, first version | < 1 s | 1.8 s | folding accents character by character over the whole text |
| 5 | fold only distinct non-ASCII words | | 1.16 s | |
| 6 | tags: check the character before `#` instead of a lookbehind | | 1.0 s | same results |
| 7 | `address/make-address.py --size 8/32/128/512` | all made | 8, 32, 128 KB made and decode intact; 512 KB: "Argument list too long" | |
| 8 | cold start: app force-stopped, `groceries.md --cursor 20` | opens | opened by one tap, intact, cursor 21 (the emoji is 2 UTF-16 units) | |
| 9 | warm start (app in the background), 8 KB | opens | intact | |
| 10 | phone locked, 32 KB | after unlocking | intact after unlocking and tapping | lock screen: private contents hidden on this phone (`lock_screen_allow_private_notifications=0`) |
| 11 | 128 KB (131,059 characters) | maybe | intact | the computer's argument limit is the only limit |

## Options compared (spike 3)

| | Stock `markdown.lang` + scheme | Own `notes-markdown.lang` + scheme made at run time |
|---|---|---|
| `#tag` at line start | styled as a heading | a tag |
| heading sizes | one size for all | three |
| checkboxes, ticked items | not recognized | own styles, struck through |
| colors | could only be fixed | the theme's, follow a style switch |
| license | GtkSourceView's LGPL file | written from scratch: ours |
| code to write | none | about 150 lines of XML |

**Decision:** our own language file (written from scratch, so a
proprietary package can ship it) and a scheme generated at run time from
the theme's colors. The stock one styles every line-start tag as a heading.

## New questions found on the way

- **PyGObject: `Buffer.iter_forward_to_context_class_toggle` crashes**
  (segfault after "Invalid text buffer iterator"): the binding passes an
  uninitialized iter. Don't use it; the context class tags avoid it.
- **PyGObject returns `(found, iter)`** for GtkSourceView's in-out iters,
  and leaves the iter passed in unchanged.
- **Setting a style scheme restyles the view**, which emits
  `style-updated` again: rewrite the scheme only when the colors changed, or
  it loops forever.
- **The address limit is 131,071 bytes on the computer**, before the phone
  is even asked. The 48 KB proposal is under it. A real 40 KB note became
  a 14 KB address (text compresses about 3×), so 48 KB is roughly a 140 KB
  note. Passing the address on stdin would lift the limit, but
  `flickos-phone send` takes it as an argument today.
- The index on a cold disk cache wasn't measured (that needs root to drop
  caches). The list can show file names and dates from `os.scandir` at
  once, and titles, tags and *N left* fill in when the index thread is
  done.

## Found with the phone (2026-10-02)

- **KDE Connect makes the whole address the notification's title** ("Tap to
  open" under it). Where a phone shows notification contents in full, also
  on the lock screen, that is the note as compressed base64: not readable at
  a glance, but decodable. The HMD CREST hides private contents when locked.
- **The phone takes all the computer can send**, so the computer's limit is
  set to 127 KB (about a 380 KB note), under Linux's 131,071 bytes.

## Cleanup

- [ ] `search/notes/` (22 MB of generated notes) deleted
- [ ] `editor/generated/` deleted
- [ ] results written into the design doc
