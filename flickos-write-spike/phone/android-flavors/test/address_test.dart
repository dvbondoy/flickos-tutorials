// The address format is the contract with the computer: these cases are
// made by the computer's own encoder (tool/make-fixtures.py).
import 'dart:convert';
import 'dart:io';

import 'package:flickos_notes/address.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final fixtures = jsonDecode(File('test/fixtures/addresses.json').readAsStringSync()) as Map<String, dynamic>;
  final errors = {
    'damaged': 'This note arrived damaged. Send it again from the computer.',
    'update': 'Update Notes to open this note.',
    'too long': 'This note is too long to open here.',
    'not a note': 'This isn’t a note from a FlickOS computer.',
  };

  for (final c in (fixtures['cases'] as List).cast<Map<String, dynamic>>()) {
    test(c['name'], () {
      final address = c['address'] as String;
      if (c.containsKey('error')) {
        expect(() => decodeAddress(address),
            throwsA(isA<AddressError>().having((e) => e.message, 'message', errors[c['error']])));
        if (c['error'] == 'update') {
          expect(() => decodeAddress(address), throwsA(isA<AddressError>().having((e) => e.update, 'update', true)));
        }
        return;
      }
      final got = decodeAddress(address);
      final want = c['expect'] as Map<String, dynamic>;
      final fields = {
        'origin': got.origin,
        'path': got.path,
        'modified': got.modified,
        'text': got.text,
        'sha256': got.sha256,
        'cursor': got.cursor,
      };
      for (final key in want.keys) {
        expect(fields[key], want[key], reason: key);
      }
    });
  }

  test('an address longer than the limit is refused unread', () {
    expect(() => decodeAddress('flicknotes://continue?v=1&d=${'A' * maxAddressLength}'), throwsA(isA<AddressError>()));
  });

  test('code points to UTF-16', () {
    expect(utf16Offset('a🍰b', 0), 0);
    expect(utf16Offset('a🍰b', 1), 1);
    expect(utf16Offset('a🍰b', 2), 3);
    expect(utf16Offset('a🍰b', 3), 4);
    expect(utf16Offset('a🍰b', 9), 4);
    expect(utf16Offset('a🍰b', -1), 0);
  });
}
