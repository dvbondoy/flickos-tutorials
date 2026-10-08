import 'dart:convert';
import 'dart:io';

final _fixtures = jsonDecode(File('test/fixtures/addresses.json').readAsStringSync()) as Map<String, dynamic>;

String _address(String name) =>
    ((_fixtures['cases'] as List).cast<Map<String, dynamic>>().firstWhere((c) => c['name'] == name))['address']
        as String;

/// "# Groceries 🍰\n#home\n\n- [ ] milk\n- [x] bread\n" from jon-x555ld, Home/Groceries.md.
final groceriesAddress = _address('a note, cursor after an emoji');
final damagedAddress = _address('text changed on the way');
