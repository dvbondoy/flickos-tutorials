import 'dart:io';

import 'package:flickos_notes/address.dart';
import 'package:flickos_notes/store.dart';
import 'package:flutter_test/flutter_test.dart';

Continuation continuation(String text, {String origin = 'jon-x555ld', String path = 'Groceries.md'}) =>
    Continuation(origin: origin, path: path, modified: '2026-10-02T10:15:00+0800', sha256: sha256Of(text),
        text: text, cursor: 0);

void main() {
  late Directory root;
  setUp(() => root = Directory.systemTemp.createTempSync('notes-store-'));
  tearDown(() => root.deleteSync(recursive: true));

  test('a new note is added, and kept after reopening', () async {
    final store = await NoteStore.open(root);
    final (note, what) = await store.receive(continuation('# Groceries\n- [ ] milk\n'));
    expect(what, Received.added);
    expect(note.title, 'Groceries');
    expect(note.info.left, 1);
    final again = await NoteStore.open(root);
    expect(again.notes.keys, [note.id]);
    expect(again.notes[note.id]!.origin, 'jon-x555ld');
    expect(again.notes[note.id]!.text, '# Groceries\n- [ ] milk\n');
  });

  test('again, unchanged here: replaced, the old text in the trash', () async {
    final store = await NoteStore.open(root);
    final (first, _) = await store.receive(continuation('# Groceries\n- [ ] milk\n'));
    final (second, what) = await store.receive(continuation('# Groceries\n- [ ] milk\n- [ ] eggs\n'));
    expect(what, Received.replaced);
    expect(second.id, first.id);
    expect(store.notes, hasLength(1));
    expect(store.trash.values.single.note.text, '# Groceries\n- [ ] milk\n');
  });

  test('ticked in the shop is still unchanged (ADR-006)', () async {
    final store = await NoteStore.open(root);
    final (note, _) = await store.receive(continuation('# Groceries\n- [ ] milk\n- [x] bread\n'));
    await store.save(note, '# Groceries\n- [x] milk\n- [ ] bread\n');
    final (_, what) = await store.receive(continuation('# Groceries\n- [ ] butter\n'));
    expect(what, Received.replaced);
    expect(store.notes.values.single.title, 'Groceries');
  });

  test('edited here: both kept, the new one says where it is from', () async {
    final store = await NoteStore.open(root);
    final (note, _) = await store.receive(continuation('# Groceries\n- [ ] milk\n'));
    await store.save(note, '# Groceries\n- [ ] milk\n- [ ] typed on the phone\n');
    final (newer, what) = await store.receive(continuation('# Groceries\n- [ ] butter\n'));
    expect(what, Received.keptBoth);
    expect(store.notes, hasLength(2));
    expect(newer.title, 'Groceries (from jon-x555ld)');
    expect(note.title, 'Groceries');
    expect(note.text, contains('typed on the phone'), reason: 'nothing typed is overwritten');
    expect(store.trash, isEmpty);
    // The next one compares with the newer copy.
    final (third, again) = await store.receive(continuation('# Groceries\n- [ ] cheese\n'));
    expect((third.id, again), (newer.id, Received.replaced));
  });

  test('the same text again only opens it', () async {
    final store = await NoteStore.open(root);
    final (note, _) = await store.receive(continuation('# Plan\n'));
    final (same, what) = await store.receive(continuation('# Plan\n'));
    expect((same.id, what), (note.id, Received.same));
    expect(store.trash, isEmpty);
  });

  test('another computer or path is another note', () async {
    final store = await NoteStore.open(root);
    await store.receive(continuation('# Plan\n'));
    await store.receive(continuation('# Plan\n', origin: 'office'));
    await store.receive(continuation('# Plan\n', path: 'Work/Plan.md'));
    expect(store.notes, hasLength(3));
  });

  test('trash: delete, restore, and gone after 30 days', () async {
    final store = await NoteStore.open(root);
    final note = await store.create('# Written here\n');
    await store.delete(note);
    expect(store.notes, isEmpty);
    expect(store.trashSorted.single.note.title, 'Written here');
    await store.restore(store.trashSorted.single);
    expect(store.notes.values.single.text, '# Written here\n');
    await store.delete(store.notes.values.single);
    final later = await NoteStore.open(root, now: DateTime.now().add(const Duration(days: 29)));
    expect(later.trash, hasLength(1));
    final much = await NoteStore.open(root, now: DateTime.now().add(const Duration(days: 31)));
    expect(much.trash, isEmpty);
    expect(Directory('${root.path}/trash').listSync(), isEmpty);
  });

  test('a damaged index loses no text', () async {
    final store = await NoteStore.open(root);
    await store.create('# Kept\n');
    File('${root.path}/index.json').writeAsStringSync('{not json');
    final again = await NoteStore.open(root);
    expect(again.notes.values.single.text, '# Kept\n');
  });

  test('no temporary files left', () async {
    final store = await NoteStore.open(root);
    await store.create('x');
    final names = root.listSync(recursive: true).map((f) => f.uri.pathSegments.last);
    expect(names.where((n) => n.startsWith('.')), isEmpty);
  });
}
