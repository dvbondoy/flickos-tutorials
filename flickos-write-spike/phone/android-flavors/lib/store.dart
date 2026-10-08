/// The phone's notes: Markdown files in the app's private storage, and an
/// index of where each came from (the design's ADR-005).
///
///     ROOT/notes/ID.md     a note's text
///     ROOT/trash/ID.md     a deleted note's, kept for [trashDays] days
///     ROOT/index.json      {v, notes: {ID: {...}}, trash: {ID: {...}}}
///
/// A note continued from a computer is known by that computer's name and its
/// path there. Continued again, it replaces the phone's copy only while that
/// copy is unchanged here, ticks aside (ADR-006); the old text goes to the
/// trash. A copy edited here is never overwritten: the new one is kept next to
/// it as "TITLE (from COMPUTER)".
library;

import 'dart:convert';
import 'dart:io';

import 'address.dart';
import 'markdown.dart';

const trashDays = 30;
const _indexVersion = 1;

class Note {
  Note({
    required this.id,
    required String text,
    required this.modified,
    this.origin,
    this.path,
    this.base,
    this.fromLabel = false,
  }) : _text = text,
       info = parse(text);

  final String id;
  String _text;
  NoteInfo info;
  DateTime modified;

  /// The computer it was continued from, and its file there; null for a
  /// note written on the phone (or a copy edited here that a newer one
  /// replaced as the computer's).
  String? origin;
  String? path;

  /// sha256 of the text last received, ticks left out: the copy is
  /// unchanged while its own text gives the same.
  String? base;

  /// Shown as "TITLE (from ORIGIN)": kept next to a copy edited here.
  bool fromLabel;

  String get text => _text;

  set text(String value) {
    _text = value;
    info = parse(value);
  }

  String get title {
    final title = info.title.isEmpty ? untitled : info.title;
    return fromLabel && origin != null ? '$title (from $origin)' : title;
  }

  bool get unchangedSinceReceived => base != null && sha256Of(withoutTicks(_text)) == base;

  Map<String, dynamic> toJson() => {
    'modified': modified.toUtc().toIso8601String(),
    if (origin != null) 'origin': origin,
    if (path != null) 'path': path,
    if (base != null) 'base': base,
    if (fromLabel) 'from_label': true,
  };

  static Note fromJson(String id, Map<String, dynamic> json, String text) => Note(
    id: id,
    text: text,
    modified: DateTime.tryParse(json['modified'] as String? ?? '')?.toLocal() ?? DateTime.now(),
    origin: json['origin'] as String?,
    path: json['path'] as String?,
    base: json['base'] as String?,
    fromLabel: json['from_label'] == true,
  );
}

class Trashed {
  Trashed(this.note, this.deleted);

  final Note note;
  final DateTime deleted;
}

enum Received {
  /// A note not here before.
  added,

  /// The unchanged copy was replaced; its text is in the trash.
  replaced,

  /// The same text again: only opened.
  same,

  /// The copy here was edited, so the new one is kept next to it.
  keptBoth,
}

class NoteStore {
  NoteStore._(this.root);

  final Directory root;
  final notes = <String, Note>{};
  final trash = <String, Trashed>{};
  int _counter = 0;

  Directory get _notesDir => Directory('${root.path}/notes');
  Directory get _trashDir => Directory('${root.path}/trash');
  File get _index => File('${root.path}/index.json');

  /// Read the notes, and empty the trash of what is older than [trashDays].
  static Future<NoteStore> open(Directory root, {DateTime? now}) async {
    final store = NoteStore._(root);
    await store._notesDir.create(recursive: true);
    await store._trashDir.create(recursive: true);
    Map<String, dynamic> index = {};
    try {
      final decoded = jsonDecode(await store._index.readAsString());
      if (decoded is Map<String, dynamic>) index = decoded;
    } on FileSystemException {
      // a new app
    } on FormatException {
      // a damaged index: the texts are still read, as notes written here
    }
    final known = (index['notes'] as Map<String, dynamic>?) ?? {};
    final trashed = (index['trash'] as Map<String, dynamic>?) ?? {};
    // Every text file is a note, even one the index doesn't know.
    await for (final file in store._notesDir.list()) {
      final id = _idOf(file);
      if (id == null) continue;
      final meta = (known[id] as Map<String, dynamic>?) ?? {};
      store.notes[id] = Note.fromJson(id, meta, await (file as File).readAsString());
    }
    final limit = (now ?? DateTime.now()).subtract(const Duration(days: trashDays));
    var purged = false;
    await for (final file in store._trashDir.list()) {
      final id = _idOf(file);
      if (id == null) continue;
      final meta = (trashed[id] as Map<String, dynamic>?) ?? {};
      final deleted = DateTime.tryParse(meta['deleted'] as String? ?? '')?.toLocal() ?? DateTime.now();
      if (deleted.isBefore(limit)) {
        await file.delete();
        purged = true;
        continue;
      }
      store.trash[id] = Trashed(Note.fromJson(id, meta, await (file as File).readAsString()), deleted);
    }
    if (purged) await store._writeIndex();
    return store;
  }

  static String? _idOf(FileSystemEntity file) {
    final name = file.uri.pathSegments.last;
    return file is File && name.endsWith('.md') && !name.startsWith('.') ? name.substring(0, name.length - 3) : null;
  }

  /// Newest first.
  List<Note> get sorted => notes.values.toList()..sort((a, b) => b.modified.compareTo(a.modified));

  List<Trashed> get trashSorted => trash.values.toList()..sort((a, b) => b.deleted.compareTo(a.deleted));

  String _newId() => '${DateTime.now().microsecondsSinceEpoch.toRadixString(36)}${(_counter++).toRadixString(36)}';

  Future<Note> create(String text) async {
    final note = Note(id: _newId(), text: text, modified: DateTime.now());
    notes[note.id] = note;
    await _writeText(_notesDir, note);
    await _writeIndex();
    return note;
  }

  Future<void> save(Note note, String text) async {
    if (text == note.text) return;
    note
      ..text = text
      ..modified = DateTime.now();
    await _writeText(_notesDir, note);
    await _writeIndex();
  }

  /// Into the trash; [restore] brings it back.
  Future<void> delete(Note note) async {
    notes.remove(note.id);
    trash[note.id] = Trashed(note, DateTime.now());
    await File('${_notesDir.path}/${note.id}.md').rename('${_trashDir.path}/${note.id}.md');
    await _writeIndex();
  }

  Future<Note> restore(Trashed item) async {
    trash.remove(item.note.id);
    final note = item.note;
    // A copy the computer's note replaced meanwhile isn't its copy any more.
    if (note.origin != null && notes.values.any((n) => n.origin == note.origin && n.path == note.path)) {
      note
        ..origin = null
        ..path = null
        ..base = null;
    }
    notes[note.id] = note;
    await File('${_trashDir.path}/${note.id}.md').rename('${_notesDir.path}/${note.id}.md');
    await _writeIndex();
    return note;
  }

  Future<void> deleteForever(Trashed item) async {
    trash.remove(item.note.id);
    await File('${_trashDir.path}/${item.note.id}.md').delete();
    await _writeIndex();
  }

  Future<void> emptyTrash() async {
    for (final item in trash.values.toList()) {
      await File('${_trashDir.path}/${item.note.id}.md').delete();
    }
    trash.clear();
    await _writeIndex();
  }

  /// A note continued from a computer (ADR-005).
  Future<(Note, Received)> receive(Continuation c) async {
    final base = sha256Of(withoutTicks(c.text));
    final copy = notes.values.where((n) => n.origin == c.origin && n.path == c.path).firstOrNull;
    if (copy == null) {
      final note = Note(id: _newId(), text: c.text, modified: DateTime.now(), origin: c.origin, path: c.path, base: base);
      notes[note.id] = note;
      await _writeText(_notesDir, note);
      await _writeIndex();
      return (note, Received.added);
    }
    if (copy.text == c.text) {
      copy.base = base;
      await _writeIndex();
      return (copy, Received.same);
    }
    if (copy.unchangedSinceReceived) {
      // The old text into the trash, as a note of its own.
      final old = Note(id: _newId(), text: copy.text, modified: copy.modified);
      trash[old.id] = Trashed(old, DateTime.now());
      await _writeText(_trashDir, old);
      copy
        ..text = c.text
        ..base = base
        ..modified = DateTime.now();
      await _writeText(_notesDir, copy);
      await _writeIndex();
      return (copy, Received.replaced);
    }
    // Edited here: it stays as it is, as a note of the phone's own.
    copy
      ..origin = null
      ..path = null
      ..base = null
      ..fromLabel = false;
    final note = Note(
      id: _newId(),
      text: c.text,
      modified: DateTime.now(),
      origin: c.origin,
      path: c.path,
      base: base,
      fromLabel: true,
    );
    notes[note.id] = note;
    await _writeText(_notesDir, note);
    await _writeIndex();
    return (note, Received.keptBoth);
  }

  Future<void> _writeText(Directory dir, Note note) => _writeAtomic(File('${dir.path}/${note.id}.md'), note.text);

  Future<void> _writeIndex() => _writeAtomic(
    _index,
    const JsonEncoder.withIndent(' ').convert({
      'v': _indexVersion,
      'notes': {for (final n in notes.values) n.id: n.toJson()},
      'trash': {
        for (final t in trash.values) t.note.id: {...t.note.toJson(), 'deleted': t.deleted.toUtc().toIso8601String()},
      },
    }),
  );

  /// Through a temporary file and a rename, so a crash never leaves half a note.
  static Future<void> _writeAtomic(File file, String text) async {
    final tmp = File('${file.parent.path}/.${file.uri.pathSegments.last}.tmp');
    await tmp.writeAsString(text, flush: true);
    await tmp.rename(file.path);
  }
}
