# Notes for Android (flickos-notes-android)

The phone half of FlickOS's sold *Notes* app: a note opened on the computer
with *Continue on Phone* arrives here, with the cursor where it was. Free of
charge (it does nothing useful without Notes on a FlickOS computer), but
proprietary like the computer's app, so it lives in its own private
repository (the design's ADR-001).

Design, decisions and phases: FlickOS's `docs/design/flickos-notes.md`. The
address format in its section 4 is the contract between the two apps; the
computer's side is `../flickos-notes`.

| Phase | State |
|---|---|
| 0 Spikes 1 and 2 (the address arrives; the largest that does) | done 2026-10-02 on the HMD CREST: cold, warm and locked all open with one tap; 8, 32 and 128 KB intact |
| 2 The app (version 1) | built 2026-10-02: receive, list with search and tags, boxes to tap, editor, trash, Share; receiving and ticking tried on the HMD CREST |
| 3 Release (Google Play or an APK) | open (design Q2) |

What is where:

- `lib/address.dart`: reads and checks a `flicknotes://` address. Anything
  can open one, so its size, fields and sha256 are checked, and nothing in
  it is run or fetched.
- `lib/markdown.dart`: titles, tags and checklist items, by the same rules
  as the computer's.
- `lib/store.dart`: the notes in the app's private storage, and what
  happens when one is continued again (ADR-005, ADR-006).
- `lib/app.dart`: the screens.
- `lib/main.dart`: starts `NotesApp` with the notes in Android's private
  folder for the app.
- `android/.../MainActivity.kt`: claims `flicknotes://continue`, hands the
  address to Dart, opens Android's share sheet, and tells Dart the app's
  private folder. No plugin: `path_provider` on Android now pulls in
  `package:jni`, which compiles C with the NDK.
- `test/`: unit and widget tests. `test/fixtures/addresses.json` is made by
  `tool/make-fixtures.py` with the computer's own encoder and parser, so the
  tests check what the computer really sends; run it again after changing
  the format or the Markdown rules on either side.

## Build and test

```sh
flutter test
flutter build apk --release --split-per-abi --target-platform android-arm64
# build/app/outputs/flutter-apk/app-arm64-v8a-release.apk
```

The release build is signed with the debug key for now (Flutter's default);
a release key is phase 3's.

Gradle's wrapper uses the `-bin` distribution with its sha256
(`android/gradle/wrapper/gradle-wrapper.properties`). On 2026-10-02 GitHub's
downloads, where services.gradle.org sends the wrapper, ran at a few KB/s
here; the same file came from a mirror in seconds and was put where the
wrapper looks after checking it against gradle.org's sha256.

## Installing on the phone

With *Wireless debugging* on (the phone is already paired with this
computer's adb key):

```sh
adb mdns services                                   # the phone's _adb-tls-connect address
adb connect 192.168.88.172:PORT
adb install -r build/app/outputs/flutter-apk/app-arm64-v8a-release.apk
```

Use the Android SDK's adb (`~/Android/Sdk/platform-tools/adb`): Debian's has
no mDNS.
