// The screens, with a fake Android side and a store in a temporary folder.
// File I/O runs in tester.runAsync: the test clock doesn't move real I/O.
import 'dart:io';

import 'package:flickos_notes/app.dart';
import 'package:flickos_notes/store.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fixtures.dart';

class FakePlatform extends Platform {
  FakePlatform([this.initial]);

  final String? initial;
  void Function(String)? handler;
  final shared = <(String, String)>[];

  @override
  Future<String?> initialLink() async => initial;

  @override
  void onLink(void Function(String) handler) => this.handler = handler;

  @override
  Future<void> share(String title, String text) async => shared.add((title, text));
}

void main() {
  late Directory root;
  setUp(() => root = Directory.systemTemp.createTempSync('notes-app-'));
  tearDown(() => root.deleteSync(recursive: true));

  // Real time for the file I/O, test time for the frames. Not pumpAndSettle:
  // the spinner shown while the store opens never settles.
  Future<void> settle(WidgetTester tester) async {
    for (var i = 0; i < 40; i++) {
      await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 5)));
      await tester.pump(const Duration(milliseconds: 100));
    }
  }

  testWidgets('a continued checklist opens with boxes, and a tap ticks and saves', (tester) async {
    final platform = FakePlatform(groceriesAddress);
    await tester.pumpWidget(NotesApp(openStore: () => NoteStore.open(root), platform: platform));
    await settle(tester);
    expect(find.text('Continued from jon-x555ld · Home/Groceries.md.'), findsOneWidget);
    expect(find.byType(Checkbox), findsNWidgets(2));
    expect(find.byType(TextField), findsNothing, reason: 'open items: to be ticked, not typed');
    await tester.tap(find.text('milk'));
    await settle(tester);
    final store = await tester.runAsync(() => NoteStore.open(root));
    expect(store!.notes.values.single.text, contains('- [x] milk'));
  });

  testWidgets('a damaged address says so', (tester) async {
    await tester.pumpWidget(NotesApp(openStore: () => NoteStore.open(root), platform: FakePlatform(damagedAddress)));
    await settle(tester);
    expect(find.text('This note arrived damaged. Send it again from the computer.'), findsOneWidget);
  });

  testWidgets('the list: search, tags, details', (tester) async {
    final store = (await tester.runAsync(() async {
      final s = await NoteStore.open(root);
      await s.create('# Plan\nFirst #work item');
      await s.create('# Groceries\n- [ ] milk\n- [x] bread #home');
      return s;
    }))!;
    await tester.pumpWidget(NotesApp(openStore: () async => store, platform: FakePlatform()));
    await settle(tester);
    expect(find.text('Plan'), findsOneWidget);
    expect(find.textContaining('1 left'), findsOneWidget);
    await tester.tap(find.text('#home 1'));
    await tester.pumpAndSettle();
    expect(find.text('Plan'), findsNothing);
    expect(find.text('Groceries'), findsOneWidget);
    await tester.enterText(find.byType(SearchBar), 'fir');
    await tester.pumpAndSettle();
    expect(find.text('Plan'), findsOneWidget);
    expect(find.text('Groceries'), findsNothing);
  });

  testWidgets('editing: Enter continues a checklist, an empty item ends it', (tester) async {
    final store = (await tester.runAsync(() async {
      final s = await NoteStore.open(root);
      await s.create('- [ ] milk');
      return s;
    }))!;
    await tester.pumpWidget(NotesApp(openStore: () async => store, platform: FakePlatform()));
    await settle(tester);
    await tester.tap(find.text('- [ ] milk'));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Edit'));
    await tester.pumpAndSettle();
    final field = find.byType(TextField);
    tester.testTextInput.updateEditingValue(const TextEditingValue(
      text: '- [ ] milk\n',
      selection: TextSelection.collapsed(offset: 11),
    ));
    await tester.pump();
    expect(tester.widget<TextField>(field).controller!.text, '- [ ] milk\n- [ ] ');
    tester.testTextInput.updateEditingValue(const TextEditingValue(
      text: '- [ ] milk\n- [ ] \n',
      selection: TextSelection.collapsed(offset: 18),
    ));
    await tester.pump();
    expect(tester.widget<TextField>(field).controller!.text, '- [ ] milk\n');
  });

  testWidgets('share sends the text', (tester) async {
    final platform = FakePlatform();
    final store = (await tester.runAsync(() async {
      final s = await NoteStore.open(root);
      await s.create('# Plan\ntext');
      return s;
    }))!;
    await tester.pumpWidget(NotesApp(openStore: () async => store, platform: platform));
    await settle(tester);
    await tester.tap(find.text('Plan'));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Share'));
    expect(platform.shared, [('Plan', '# Plan\ntext')]);
  });
}
