# Write phase 0 spikes

Phase 0 of `docs/design/flickos-write.md` (section 5): four questions to
answer before Write is built. Answers go in `results.md`; the kit's own
guide is `KIT-README.md` and the empty sheet `results-template.md`.

```
view/      spike 2: the writing view (typewriter scrolling, focus, full screen)
export/    spike 4: ODT and EPUB with the standard library, DOCX/PDF via soffice
phone/     spikes 1 and 3: the phone (make-return.py, android-flavors/)
shots/     screenshots taken by the runs
```

## Spike 2: the writing view (done, except typing by hand)

```sh
cd view
./gen-chapter.py > chapter.md                 # 20,000 words of made-up prose, the same every time
./writer.py chapter.md                        # a window to type in
./writer.py --fullscreen --focus sentence chapter.md   # the writing session's page; Escape won't close it: Alt+F4
./writer.py --bench --focus paragraph chapter.md       # times 60 keystrokes and Down arrows at the start, middle, end
./writer.py --bench --focus sentence --naive chapter.md   # the slow way, to compare
GTK_THEME=Arc ./writer.py …                   # the Light style
GDK_DPI_SCALE=1.5 ./writer.py …               # bigger text (A11Y-7)
```

How `--bench` measures: it changes the text (or moves the cursor) itself,
40 ms apart, and times from the change to the moment GTK has painted the
frame that shows it (the frame clock's `after-paint` signal). A screen
refreshes every 16.7 ms, so anything under that is "the next frame". Don't
use the desktop while it runs: a window the compositor isn't drawing gets
no frames, and those keystrokes show as "no paint".

**Still to do, by you:** type in `./writer.py --fullscreen --focus sentence
chapter.md` for a minute near the middle (Ctrl+End, then Page Up a few
times) and say whether anything feels late: the letters, the dimming
moving to the next sentence, the page scrolling up as lines fill.

What the code shows (phase 1 copies the ideas, not the code):
- `Writer.on_size`: the column is `width` characters of the font, measured
  with Pango's approximate character width; the rest is margin.
- `Writer.update_focus`: one tag dims everything; only the old and new
  sentence are retagged when the cursor moves.
- `Writer.on_highlight`: GtkSourceView makes its own tags while it
  highlights, and the newest tag wins, so the dimming tag is moved to the
  top each time.
- `Writer.on_changed`: the typewriter scroll, skipped while loading.

## Spike 4: export (done, except the e-reader)

```sh
cd export
./export.py "The Lighthouse" --to odt  --author "A. Writer" --output out/lighthouse.odt
./export.py "The Lighthouse" --to epub --author "A. Writer" --output out/lighthouse.epub
./export.py "The Lighthouse" --to docx --output out/lighthouse.docx   # through soffice
./export.py "The Lighthouse" --to pdf  --output out/lighthouse.pdf
xdg-open out/lighthouse.odt                   # look at it in LibreOffice Writer
pdftoppm -r 60 -f 1 -l 3 -png out/lighthouse.pdf out/page   # the first pages as pictures
```

`The Lighthouse/` is a project: `01 Arrival.md` (every kind of Markdown
Write knows, plus a table it doesn't), `02 The Keeper.md` (3,000 words),
`03 The Storm.md` (the 20,000-word chapter).

Checking the EPUB (Java is already installed for Android builds; the
checker comes from PyPI with its jar inside, in a throwaway folder):

```sh
python3 -m venv /tmp/epubcheck && /tmp/epubcheck/bin/pip install epubcheck
java -jar /tmp/epubcheck/lib/python3.13/site-packages/epubcheck/epubcheck.jar out/lighthouse.epub
```

**Still to do:** open `out/lighthouse.epub` in an e-reader app on the
phone (with the phone spikes), and open the ODT and DOCX in Writer by hand.

## Spikes 1 and 3: the phone (done)

Needs the HMD CREST with KDE Connect open and Wireless debugging on. The
port changes every time it's turned on; the phone's Wireless debugging
screen shows it (its mDNS announcement can be stale).

```sh
A="$HOME/Android/Sdk/platform-tools/adb -s 192.168.88.172:PORT"
$HOME/Android/Sdk/platform-tools/adb connect 192.168.88.172:PORT

# spike 3: the Notes repository as two flavors (a copy: android-flavors/)
cd android-flavors
flutter build apk --release --split-per-abi --target-platform android-arm64 --flavor notes -t lib/main_notes.dart
flutter build apk --release --flavor write -t lib/main_write.dart
$A install -r build/app/outputs/flutter-apk/app-arm64-v8a-notes-release.apk   # updates Notes, notes kept
$A install build/app/outputs/flutter-apk/app-write-release.apk                 # Write next to it
$A shell cmd package query-activities -a android.intent.action.VIEW -c android.intent.category.BROWSABLE -d 'flickwrite://continue?v=1'

# spike 1: in the Write (spike) app tap Share 8/32/127 KB, then the computer
flickos-phone received --json        # kind "text", the whole address
./make-return.py --decode @FILE      # "intact": the text's sha256 matches
```

What changed in the copy (`android-flavors/`): `android/app/build.gradle.kts`
(`productFlavors`, `buildConfig`), the manifest's `${appLabel}` and
`${linkScheme}`, `MainActivity.kt` (`BuildConfig.LINK_SCHEME`, `shareTo`),
`lib/main_notes.dart` (= `main.dart`) and `lib/main_write.dart` (the test
screen). The real `flickos-notes-android` repository is untouched.

On the phone now: Notes is the flavor build (the same app), and *Write*
is the test screen. Remove it with `$A uninstall io.github.dvbondoy.flickos_write`.

## Cleaning up

```sh
rm -rf view/generated export/out shots phone/android-flavors/build
```
