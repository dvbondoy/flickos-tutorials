import 'dart:io';

import 'package:flutter/material.dart';

import 'app.dart';
import 'store.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  const platform = Platform();
  runApp(NotesApp(
    platform: platform,
    openStore: () async => NoteStore.open(Directory(await platform.filesDir())),
  ));
}
