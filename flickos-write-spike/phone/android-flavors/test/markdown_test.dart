import 'dart:convert';
import 'dart:io';

import 'package:flickos_notes/markdown.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('the same as the computer', () {
    final fixtures = jsonDecode(File('test/fixtures/addresses.json').readAsStringSync()) as Map<String, dynamic>;
    for (final c in (fixtures['parse'] as List).cast<Map<String, dynamic>>()) {
      test(jsonEncode(c['text']), () {
        final info = parse(c['text'] as String);
        expect(info.title, c['title']);
        expect(info.tags.toList()..sort(), c['tags']);
        expect(info.items, c['items']);
        expect(info.left, c['left']);
      });
    }
  });

  test('toggle', () {
    const text = '# Groceries\n- [ ] milk\n  2. [X] bread\nplain';
    expect(toggleLine(text, 1), '# Groceries\n- [x] milk\n  2. [X] bread\nplain');
    expect(toggleLine(text, 2), '# Groceries\n- [ ] milk\n  2. [ ] bread\nplain');
    expect(toggleLine(text, 3), text);
    expect(isTicked('- [x] a'), isTrue);
    expect(isTicked('- [ ] a'), isFalse);
    expect(boxColumn('- 🍰 [ ] cake'), isNull);
  });

  test('ticking isn’t typing (ADR-006)', () {
    expect(withoutTicks('- [x] milk\n- [X] bread\nx [x] no'), '- [ ] milk\n- [ ] bread\nx [x] no');
  });

  test('Enter continues a list', () {
    expect(continued('- [x] bread'), '- [ ] ');
    expect(continued('  3. three'), '  4. ');
    expect(continued('- [ ] '), '');
    expect(continued('milk'), isNull);
  });

  test('fold', () {
    expect(fold('Café NAÏVE straße'), 'cafe naive straße');
  });
}
