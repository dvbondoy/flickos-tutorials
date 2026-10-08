/// What a note's Markdown means to Notes, the same rules as on the computer
/// (flickos-notes' parse(); the design's ADR-003 and ADR-006), so the two apps
/// never disagree about a title, a tag or a checklist item.
library;

/// A list line: indent, marker, spaces, then maybe a checklist box.
final item = RegExp(r'^([ \t]*)([-*+]|\d+[.)])([ \t]+)(\[[ xX]\] ?)?');
final _box = RegExp(r'^[ \t]*(?:[-*+]|\d+[.)])[ \t]+\[([ xX])\]', multiLine: true);
final _tag = RegExp(r'#([\p{L}\p{N}_][\p{L}\p{N}_/-]*)', unicode: true);
final _tagName = RegExp(r'^[\p{L}\p{N}_][\p{L}\p{N}_/-]*$', unicode: true);
final _letter = RegExp(r'^\p{L}', unicode: true);
final _fence = RegExp(r'^ {0,3}(```|~~~).*?(?:^ {0,3}\1[ \t]*$|(?![\s\S]))', multiLine: true, dotAll: true);
final _codeSpan = RegExp(r'`[^`\n]+`');
final _frontMatter = RegExp(r'^---[ \t]*\n((?:.*?\n)?)(?:---|\.\.\.)[ \t]*(?:\n|$)', dotAll: true);
final _heading = RegExp(r'^#{1,6}[ \t]+');
final _link = RegExp(r'\[([^\]\n]*)\]\([^)\n]*\)');
const _tagBefore = ' \t\n(';
const untitled = 'Untitled';
const titleChars = 120;

/// What the list, the tags and the search need of a note.
class NoteInfo {
  const NoteInfo(this.title, this.tags, this.items, this.left);

  /// The first line without a heading's #s ('' for an empty note).
  final String title;

  /// Folded (lower case, no accents), without '#'.
  final Set<String> tags;

  /// Checklist items, and how many of them aren't ticked.
  final int items;
  final int left;
}

NoteInfo parse(String text) {
  var body = text;
  final tags = <String>{};
  final front = _frontMatter.firstMatch(text);
  if (front != null) {
    tags.addAll(frontMatterTags(front.group(1) ?? '').map(fold));
    body = text.substring(front.end);
  }
  final title = plainTitle(body.trimLeft().split('\n').first);
  var prose = body;
  if (prose.contains('```') || prose.contains('~~~')) prose = prose.replaceAll(_fence, ' ');
  if (prose.contains('`')) prose = prose.replaceAll(_codeSpan, ' ');
  for (final m in _tag.allMatches(prose)) {
    final name = m.group(1)!;
    if (_letter.hasMatch(name) && (m.start == 0 || _tagBefore.contains(prose[m.start - 1]))) {
      tags.add(fold(name));
    }
  }
  final boxes = _box.allMatches(prose).map((m) => m.group(1)).toList();
  return NoteInfo(title, tags, boxes.length, boxes.where((b) => b == ' ').length);
}

String plainTitle(String line) {
  var title = line.trim().replaceFirst(_heading, '');
  title = title.replaceAllMapped(_link, (m) => m.group(1)!).replaceAll('**', '').replaceAll('__', '').replaceAll('`', '');
  title = title.split(RegExp(r'\s+')).where((w) => w.isNotEmpty).join(' ');
  return title.length > titleChars ? title.substring(0, titleChars).trimRight() : title;
}

List<String> frontMatterTags(String block) {
  final lines = block.split('\n');
  for (var i = 0; i < lines.length; i++) {
    final m = RegExp(r'^tags?[ \t]*:[ \t]*(.*)$').firstMatch(lines[i]);
    if (m == null) continue;
    final value = m.group(1)!.trim();
    List<String> names;
    if (value.isNotEmpty) {
      names = value.replaceAll(RegExp(r'^\[|\]$'), '').split(RegExp(r'[,\s]+'));
    } else {
      names = [];
      for (final line in lines.skip(i + 1)) {
        final im = RegExp(r'^[ \t]*-[ \t]*(.+)$').firstMatch(line);
        if (im == null) break;
        names.add(im.group(1)!);
      }
    }
    return names
        .map((n) => n.trim().replaceAll(RegExp(r'''^['"]|['"]$'''), '').replaceFirst(RegExp(r'^#'), ''))
        .where((n) => _tagName.hasMatch(n) && _letter.hasMatch(n))
        .toList();
  }
  return [];
}

/// Lower case without accents, so cafe finds Café.
String fold(String text) {
  final lower = text.toLowerCase();
  if (!lower.runes.any((r) => r > 0x7F)) return lower;
  return String.fromCharCodes(lower.runes.map((r) => _unaccented[r] ?? r));
}

// The accented letters of the Latin alphabets and their base letters (Dart
// has no Unicode decomposition without a package).
final Map<int, int> _unaccented = () {
  const groups = {
    'a': 'àáâãäåāăą',
    'c': 'çćĉċč',
    'd': 'ďđ',
    'e': 'èéêëēĕėęě',
    'g': 'ĝğġģ',
    'h': 'ĥħ',
    'i': 'ìíîïĩīĭįı',
    'j': 'ĵ',
    'k': 'ķ',
    'l': 'ĺļľŀł',
    'n': 'ñńņňŉ',
    'o': 'òóôõöøōŏő',
    'r': 'ŕŗř',
    's': 'śŝşšș',
    't': 'ţťŧț',
    'u': 'ùúûüũūŭůűų',
    'w': 'ŵ',
    'y': 'ýÿŷ',
    'z': 'źżž',
  };
  final map = <int, int>{};
  groups.forEach((base, letters) {
    for (final r in letters.runes) {
      map[r] = base.codeUnitAt(0);
    }
  });
  return map;
}();

/// The line's box column when it is a checklist item, else null.
int? boxColumn(String line) {
  final m = item.firstMatch(line);
  if (m == null || m.group(4) == null) return null;
  return m.start + m.group(1)!.length + m.group(2)!.length + m.group(3)!.length;
}

bool isTicked(String line) {
  final column = boxColumn(line);
  return column != null && line[column + 1] != ' ';
}

/// The text with line [lineNumber]'s box ticked or unticked.
String toggleLine(String text, int lineNumber) {
  final lines = text.split('\n');
  final column = boxColumn(lines[lineNumber]);
  if (column == null) return text;
  final line = lines[lineNumber];
  final mark = line[column + 1] == ' ' ? 'x' : ' ';
  lines[lineNumber] = line.substring(0, column + 1) + mark + line.substring(column + 2);
  return lines.join('\n');
}

/// Every box open: two texts that differ only in ticks are the same note
/// (ADR-006: ticking isn't typing).
String withoutTicks(String text) =>
    text.split('\n').map((line) {
      final column = boxColumn(line);
      return column == null ? line : '${line.substring(0, column + 1)} ${line.substring(column + 2)}';
    }).join('\n');

/// Enter at the end of [line]: what the next line starts with, '' when the
/// item is empty (the list ends), null when it isn't a list line.
String? continued(String line) {
  final m = item.firstMatch(line);
  if (m == null) return null;
  if (line.substring(m.end).trim().isEmpty) return '';
  var marker = m.group(2)!;
  if (RegExp(r'^\d').hasMatch(marker)) {
    marker = '${int.parse(marker.substring(0, marker.length - 1)) + 1}${marker[marker.length - 1]}';
  }
  return '${m.group(1)}$marker${m.group(3)}${m.group(4) != null ? '[ ] ' : ''}';
}
