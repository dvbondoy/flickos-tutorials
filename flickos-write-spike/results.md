# Write (flickos-write) phase 0: results

Date: 2026-10-04  Design doc: `docs/design/flickos-write.md`  Machine: `machine.txt`
(i3-4030U, 4 CPUs, FlickOS 2.1, one 1920×1080 screen)

## Questions

Spikes 2 and 4 ran on the computer; 1 and 3 on the phone (HMD CREST, Android 14, KDE Connect 1.35.17).

| # | Question | Why it matters | Prediction | Result | Evidence |
|---|---|---|---|---|---|
| Q1 (spike 1) | What reaches flickos-phone when the phone shares a `flickwrite://return?…` address of 8, 32, 128 KB to KDE Connect: a `url` or `text`, intact? Can the share go straight to KDE Connect? | what the flickos-phone change in ADR-007 matches on; section 4's size limit | `text` (KDE Connect sends a share as a url only for http/https); 8 and 32 KB intact; 128 KB maybe | **`text`, intact at 8, 32 and 127 KB** (8,128 / 32,680 / 129,980 characters, sha256 of the text matches). An `ACTION_SEND` with `setPackage("org.kde.kdeconnect_tp")` opens KDE Connect's *Send to Device* list directly (no Android chooser): one tap on the computer | runs 20–23, `shots/phone-share-8.png` |
| Q2 (spike 2) | Typewriter scrolling and focus in GtkSourceView 4 with a 20,000-word chapter: time per keystroke and cursor move | ADR-003; PERF: must feel instant on the i3 | under one frame (16.7 ms) with only two ranges retagged; the whole chapter retagged misses frames | **yes**: under 2 ms of work, ~10 ms to the screen (one refresh) at the start, middle and end, with focus off, sentence or paragraph, same as a 389-word text. Retagging the whole chapter: ~26 ms to the screen, every keystroke misses a frame | runs 1–9 |
| Q2a | Does full screen cover the panel in Redmond, Cupertino (dock) and Traditional? | ADR-005 says the panel needs nothing | yes: labwc hides the top layer under a full-screen window | **yes** in all three: the strips where the bars are show only the page | run 13, `shots/live-*-full.png` vs `live-*-panel.png` |
| Q2b | The column at 1366×768 and at text scale 1.5 | A11Y-7 | fits | **fits**: 66 characters of DejaVu Serif 13 pt = 601 px (margins 382 px); at 1.5 = 901 px (margins 232 px); an 800 px window keeps 99 px margins | `shots/full-1366*.png`, `window-800.png` |
| Q2c | Does it feel instant when typing by hand? | the numbers above are synthetic | yes | **not done yet**: needs you at the keyboard (see README) | |
| Q3 (spike 3) | Two flavors from one Flutter repository installed side by side, each opening only its scheme; the Notes flavor updates the installed Notes with its notes kept | ADR-008 | yes, if the Notes flavor keeps the application id and signing key (debug key today) | **yes**, once the Notes flavor is built like Notes was (`--split-per-abi`, version code 2001): it updated the installed Notes in place, 7 notes and 2 tags kept. Each scheme resolves only to its own app; `flickwrite://continue` sent by `flickos-phone send` opened Write with all 326 characters | runs 24–28, `shots/phone-notes-*.png`, `phone-write-continue.png` |
| Q4 (spike 4) | ODT written with the standard library opens in LibreOffice; DOCX and PDF from `soffice --convert-to` look right; EPUB passes epubcheck and opens in an e-reader | ADR-006 | ODT and EPUB yes; DOCX/PDF fine | **yes** for ODT, DOCX, PDF and epubcheck; the e-reader on the phone is not tried (no e-reader app on it) | runs 14–19, `export/out/` |
| Q4a | Italic in the PDF and in the writing view | a manuscript is full of italics | real italics | **no real italic serif in the image**: fonts-dejavu-core has DejaVu Serif Book and Bold only, so italics are DejaVu Serif slanted by the computer, in the view and in the PDF (only Book and Bold are embedded) | `fc-list`, `pdffonts`, `out/page-02.png` |

## Cost (HIG PERF-7)

| What | Number | How measured |
|---|---|---|
| disk: the writing view | nothing new beyond Notes' `gir1.2-gtksource-4` (83 KB) | Notes phase 0 |
| disk: export | nothing: zipfile + XML text; DOCX/PDF use LibreOffice, already in the image | |
| disk: a real italic serif (choice) | fonts-dejavu-extra 6,733 KB (1,750 KB download); fonts-liberation 4,287 KB (1,440 KB) | `tools/package-cost.py` |
| memory: the view with a 20,000-word chapter | 37 MB PSS (68 MB RSS) live; 33 MB with a 389-word text | `/proc/self/smaps_rollup` at the end of `--bench` |
| time: 116 KB into the buffer | 5–7 ms; first frame 170 ms after the program starts | `--bench` |
| time: export of 23,000 words | ODT 0.03 s, EPUB 0.03 s, DOCX 2.3 s, PDF 2.3 s (LibreOffice starting with a fresh profile) | `export.py` |

## Runs

Synthetic typing: `view/writer.py --bench`, 60 keystrokes or Down arrows at
each place, 40 ms apart; "to the screen" is from the change to the frame
clock's after-paint, so up to 16.7 ms of it is waiting for the screen's
refresh. Live = your desktop (1000×700 window); headless = a private labwc
at 1366×768 drawing in software (pixman), so a few ms slower everywhere.

| Run | Command | Prediction | Result | Notes |
|---|---|---|---|---|
| 1 | `--bench chapter.md` (focus off), live | < 1 frame | work 0.5 ms, screen 10–11 ms median, max 22 | |
| 2 | `--focus sentence`, live | same | work 0.7–1.8 ms, screen ~10 ms; 20 Down arrows drew nothing (max 276 ms) | see run 5 |
| 3 | `--focus paragraph`, live | same | work 0.7–0.9 ms, screen ~10 ms | |
| 4 | `--focus sentence --naive`, live | misses frames | work ~1 ms, screen **26–28 ms** median | the cost is in the redraw: the whole chapter's layout is invalidated |
| 5 | run 2 again, live | | missing frames elsewhere this time (26 keystrokes) | not the code: the window wasn't being drawn (covered or paused by the compositor); runs 6–9 had none |
| 6–9 | runs 1–4 headless, 1366×768 | | off 15–22 ms, sentence 15–23, paragraph 14–23, naive **21–35**; no frame missing except at the chapter's very end (the cursor can't move) | |
| 10 | `--bench --focus sentence short.md` | | same as with 20,000 words | |
| 11 | `--shot … --fullscreen chapter.md` (cursor at the start) | heading at the top | **opened a few paragraphs down** | the typewriter scroll ran while the text was loaded, before line heights were known; fixed by skipping it while loading |
| 12 | `--shot` full screen, `--at 0.5`, Light, scale 1.5, 800 px | | all right; the current line sits at the middle | the mouse pointer stays visible over the page |
| 13 | live full screen in Redmond, Cupertino, Traditional (`flickos-layout set`, then back to Redmond) | covered | covered | added 3 rows to History |
| 14 | `export.py "The Lighthouse" --to odt` | opens | 26 KB, 0.03 s; LibreOffice reads it (14–15 convert it) | |
| 15 | `--to pdf` | right | 74 pages: title page, each chapter on a new page with its title centred, first-line indents, `* * *`, bullets and numbers, page numbers; DejaVu Serif embedded | `out/page-0*.png` |
| 16 | `--to docx` | right | headings are Word's own *Heading 1* with a page break, italic/bold as character styles, 0.5 in first-line indent | `word/styles.xml` |
| 17 | `epubcheck lighthouse.epub` (5.3, from PyPI) | passes | **0 errors, 0 warnings** | |
| 18 | a table in a chapter | reported | exported as plain text and listed by `export.py` | |
| 19 | conversion while a LibreOffice runs with the same profile (headless, then a Writer window) | writes nothing | **writes the file** both times in LibreOffice 25.2 | Write still uses its own profile, so a LibreOffice showing a dialog can't hold up an export |

| 20 | Write spike app: *Share 8 KB* (`ACTION_SEND`, `setPackage` KDE Connect) | chooser or device list | KDE Connect's *Send to Device* list, one computer | |
| 21 | tap jon-x555ld; `flickos-phone received --json` | `text` | `text`, 8,128 characters, intact | the notification's click copies it, as for any text |
| 22–23 | the same with 32 and 127 KB | 127 KB maybe cut | both intact | |
| 24 | `adb install -r app-notes-release.apk` (one APK for all ABIs) | updates | **refused: `INSTALL_FAILED_VERSION_DOWNGRADE`, 1 is older than 2001**; Notes untouched | the installed Notes was built `--split-per-abi`, which adds 1000 × the ABI's number (arm64 = 2) |
| 25 | the Notes flavor built `--split-per-abi --target-platform android-arm64` (2001), `install -r` | updates, notes kept | updated, 7 notes and both tags kept | `phone-notes-before.png`, `phone-notes-after.png` |
| 26 | `adb install app-write-release.apk` | side by side | installed next to Notes | |
| 27 | `cmd package query-activities` for `flicknotes://continue` and `flickwrite://continue` | one app each | one app each | |
| 28 | `flickos-phone send flickwrite://continue?…`, tap the notification | Write opens | Write opened with the address, 326 characters | the scheme comes from `BuildConfig.LINK_SCHEME` |

## What changes in the design

- **ADR-003, typewriter:** never scroll while text is loaded or replaced
  from outside; only after the writer's own changes. The pointer is hidden
  while typing in a session (it shows again when moved, which ends the
  session anyway).
- **ADR-003, focus:** confirmed as written: one tag, only the old and new
  ranges retagged, and its priority raised above GtkSourceView's own tags
  after each highlight pass (`highlight-updated`), or highlighted words keep
  their color.
- **ADR-007, back to the computer:** KDE Connect delivers the address as
  **text**, so the flickos-phone change matches a received *text* that is
  exactly one address of a registered scheme (no spaces, nothing else),
  and turns it into an item that opens with `xdg-open` on a click. The
  phone app shares with `setPackage("org.kde.kdeconnect_tp")` when KDE
  Connect is installed, else Android's chooser.
- **ADR-008:** confirmed, with two rules: the Notes flavor keeps Notes'
  application id, signing key **and version codes** (built
  `--split-per-abi` as before, or Android refuses the update as a
  downgrade); the Kotlin channel takes its scheme from
  `BuildConfig.LINK_SCHEME` (`buildFeatures.buildConfig = true`).
- **ADR-006:** confirmed. `soffice` gets its own temporary profile
  (`-env:UserInstallation`). Decide on italics: ship without (slanted
  DejaVu Serif, in the view and the PDF) or add
  `fonts-dejavu-extra` (6.7 MB) as a Depends of flickos-write only.
