/// The address a FlickOS computer sends to continue a note (the design's
/// section 4, docs/design/flickos-notes.md in FlickOS):
///
///     flicknotes://continue?v=1&d=BASE64URL(ZLIB(JSON))
///
/// with the JSON {v, origin, path, modified, sha256, text, cursor}. Any web
/// page or app can open such an address, so everything in it is checked
/// here and nothing in it is ever run or fetched.
library;

import 'dart:convert';
import 'dart:io' show ZLibDecoder;

import 'package:crypto/crypto.dart';

/// The address versions this app understands.
const knownVersion = 1;

/// The longest address read. The computer sends at most 48 KB (Linux takes
/// no longer argument than 131,071 bytes); more is refused unread.
const maxAddressLength = 256 * 1024;

/// The longest text an address may unpack to: zlib can turn 48 KB into
/// 48 MB of one repeated letter.
const maxTextBytes = 4 * 1024 * 1024;

/// What a valid address carries.
class Continuation {
  Continuation({
    required this.origin,
    required this.path,
    required this.modified,
    required this.sha256,
    required this.text,
    required this.cursor,
  });

  /// The computer's name, as it calls itself.
  final String origin;

  /// The note's file in that computer's notes folder ("Work/Plan.md").
  final String path;

  /// When the file was last changed there (ISO 8601, as sent).
  final String modified;

  /// sha256 of [text]'s UTF-8 bytes, checked.
  final String sha256;

  /// The note's file, exactly.
  final String text;

  /// The cursor in [text] in UTF-16 code units (Dart's String indexes),
  /// converted from the code points the computer counts.
  final int cursor;
}

/// Why an address can't be used, in words for the user.
class AddressError implements Exception {
  AddressError(this.message, {this.update = false});

  final String message;

  /// The address is from a newer Notes: the user should update this app.
  final bool update;

  @override
  String toString() => message;
}

bool isNotesAddress(String link) => link.startsWith('flicknotes:');

Continuation decodeAddress(String address) {
  if (address.length > maxAddressLength) {
    throw AddressError('This note is too long to open here.');
  }
  final uri = Uri.tryParse(address);
  if (uri == null || uri.scheme != 'flicknotes' || uri.host != 'continue') {
    throw AddressError('This isn’t a note from a FlickOS computer.');
  }
  final version = int.tryParse(uri.queryParameters['v'] ?? '');
  if (version == null) {
    throw AddressError('This isn’t a note from a FlickOS computer.');
  }
  if (version != knownVersion) {
    throw AddressError('Update Notes to open this note.', update: true);
  }
  final data = uri.queryParameters['d'] ?? '';
  final Map<String, dynamic> json;
  try {
    final packed = base64Url.decode(base64Url.normalize(data));
    final decoded = jsonDecode(utf8.decode(inflate(packed)));
    if (decoded is! Map<String, dynamic>) throw const FormatException('not an object');
    json = decoded;
  } on AddressError {
    rethrow;
  } on FormatException {
    throw AddressError('This note arrived damaged. Send it again from the computer.');
  }
  String field(String name) {
    final value = json[name];
    if (value is! String) throw AddressError('This note arrived damaged. Send it again from the computer.');
    return value;
  }

  if (json['v'] != knownVersion) throw AddressError('Update Notes to open this note.', update: true);
  final text = field('text');
  final sum = field('sha256').toLowerCase();
  if (sha256Of(text) != sum) {
    throw AddressError('This note arrived damaged. Send it again from the computer.');
  }
  final path = field('path');
  if (path.isEmpty || path.contains('\u0000')) {
    throw AddressError('This note arrived damaged. Send it again from the computer.');
  }
  final cursor = json['cursor'];
  return Continuation(
    origin: field('origin'),
    path: path,
    modified: field('modified'),
    sha256: sum,
    text: text,
    cursor: utf16Offset(text, cursor is int ? cursor : 0),
  );
}

/// zlib's inflate, refusing to unpack more than [maxTextBytes].
List<int> inflate(List<int> packed) {
  final out = _LimitedSink(maxTextBytes);
  final sink = ZLibDecoder().startChunkedConversion(out);
  try {
    sink
      ..add(packed)
      ..close();
  } on AddressError {
    rethrow;
  } on Exception {
    throw const FormatException('not zlib');
  }
  return out.bytes;
}

class _LimitedSink implements Sink<List<int>> {
  _LimitedSink(this.limit);

  final int limit;
  final bytes = <int>[];

  @override
  void add(List<int> chunk) {
    if (bytes.length + chunk.length > limit) throw AddressError('This note is too long to open here.');
    bytes.addAll(chunk);
  }

  @override
  void close() {}
}

String sha256Of(String text) => sha256.convert(utf8.encode(text)).toString();

/// Code points (Python's and GtkTextBuffer's offsets) to UTF-16 code units
/// (Dart's): an emoji counts one there and two here. Clamped to the text.
int utf16Offset(String text, int codePoints) {
  if (codePoints <= 0) return 0;
  var units = 0;
  var seen = 0;
  for (final rune in text.runes) {
    if (seen == codePoints) return units;
    units += rune > 0xFFFF ? 2 : 1;
    seen++;
  }
  return text.length;
}
