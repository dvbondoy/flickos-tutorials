/// Write's flavor, phase 0 only (flickos-write spikes 1 and 3): shows the
/// flickwrite:// address it was opened with, and shares return addresses of
/// 8, 32 and 127 KB straight to KDE Connect. Throwaway code.
library;

import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:crypto/crypto.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

const _channel = MethodChannel('flickos_notes/links');
const kdeConnect = 'org.kde.kdeconnect_tp';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const MaterialApp(title: 'Write', home: SpikePage()));
}

String encodeReturn(String text) {
  final data = {
    'v': 1,
    'origin': 'jon-x555ld',
    'from': 'HMD CREST',
    'ref': 'spike-ref-0000000000000',
    'path': 'Spike/01 Size test.md',
    'base': sha256.convert(utf8.encode('')).toString(),
    'sha256': sha256.convert(utf8.encode(text)).toString(),
    'text': text,
    'cursor': 0,
  };
  final packed = base64Url.encode(ZLibCodec(level: 9).encode(utf8.encode(jsonEncode(data)))).replaceAll('=', '');
  return 'flickwrite://return?v=1&d=$packed';
}

/// An address just under [kb] KB: random letters don't compress.
String sized(int kb) {
  final rnd = Random(kb);
  const letters = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  final want = kb * 1024 - 64;
  var n = want;
  var address = '';
  for (var i = 0; i < 20; i++) {
    final body = String.fromCharCodes(List.generate(n, (_) => letters.codeUnitAt(rnd.nextInt(letters.length))));
    address = encodeReturn('# Size test $kb KB\n\n$body');
    if (address.length <= want && address.length > want - 64) break;
    n = n * want ~/ address.length;
  }
  return address;
}

class SpikePage extends StatefulWidget {
  const SpikePage({super.key});

  @override
  State<SpikePage> createState() => _SpikePageState();
}

class _SpikePageState extends State<SpikePage> {
  final _log = <String>[];

  @override
  void initState() {
    super.initState();
    _channel.invokeMethod<String>('initialLink').then((l) => _got('opened with', l));
    _channel.setMethodCallHandler((call) async {
      if (call.method == 'link') _got('received', call.arguments as String?);
    });
  }

  void _got(String how, String? link) {
    if (link == null) return;
    setState(() => _log.insert(0, '$how: ${link.length} characters, ${link.substring(0, min(48, link.length))}…'));
  }

  Future<void> _share(int kb) async {
    final address = sized(kb);
    try {
      await _channel.invokeMethod('shareTo', {'text': address, 'package': kdeConnect});
      setState(() => _log.insert(0, 'shared $kb KB: ${address.length} characters'));
    } on PlatformException catch (e) {
      setState(() => _log.insert(0, 'share $kb KB failed: ${e.message}'));
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Write (spike)')),
    body: ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Wrap(spacing: 8, children: [
          for (final kb in [8, 32, 127])
            FilledButton(onPressed: () => _share(kb), child: Text('Share $kb KB')),
        ]),
        const SizedBox(height: 16),
        for (final line in _log) Padding(padding: const EdgeInsets.only(bottom: 8), child: Text(line)),
      ],
    ),
  );
}
