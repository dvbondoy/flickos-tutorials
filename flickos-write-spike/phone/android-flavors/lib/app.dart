/// Notes on the phone: the list, a note (boxes to tap, or Markdown to edit),
/// the trash, and notes continued from a FlickOS computer (the design's
/// phase 2, docs/design/flickos-notes.md in FlickOS).
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'address.dart';
import 'markdown.dart';
import 'store.dart';

/// Arc's selection blue, the color FlickOS's tags and boxes have on the computer.
const seed = Color(0xFF5294E2);
const saveDelay = Duration(seconds: 1);

/// Where addresses come from and text goes to: Android, through
/// MainActivity's channel; tests give their own.
class Platform {
  const Platform();

  static const _channel = MethodChannel('flickos_notes/links');

  Future<String?> initialLink() => _channel.invokeMethod<String>('initialLink');

  /// The app's private folder (Android's filesDir).
  Future<String> filesDir() async => (await _channel.invokeMethod<String>('filesDir'))!;

  void onLink(void Function(String) handler) => _channel.setMethodCallHandler((call) async {
    if (call.method == 'link' && call.arguments is String) handler(call.arguments as String);
  });

  Future<void> share(String title, String text) => _channel.invokeMethod('share', {'title': title, 'text': text});
}

class NotesApp extends StatelessWidget {
  const NotesApp({super.key, required this.openStore, this.platform = const Platform()});

  final Future<NoteStore> Function() openStore;
  final Platform platform;

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Notes',
    theme: ThemeData(colorSchemeSeed: seed),
    darkTheme: ThemeData(colorSchemeSeed: seed, brightness: Brightness.dark),
    home: HomePage(openStore: openStore, platform: platform),
  );
}

// --- The list ---

class HomePage extends StatefulWidget {
  const HomePage({super.key, required this.openStore, required this.platform});

  final Future<NoteStore> Function() openStore;
  final Platform platform;

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  NoteStore? store;
  Object? failure;
  final search = TextEditingController();
  final pending = <String>[];        // addresses that came before the store was open

  @override
  void initState() {
    super.initState();
    widget.platform.onLink(receive);
    widget.openStore().then((s) {
      setState(() => store = s);
      for (final link in pending) {
        receive(link);
      }
      pending.clear();
    }, onError: (Object e) => setState(() => failure = e));
    widget.platform.initialLink().then((link) {
      if (link != null) receive(link);
    });
    search.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    search.dispose();
    super.dispose();
  }

  Future<void> receive(String link) async {
    final store = this.store;
    if (store == null) {
      pending.add(link);
      return;
    }
    final Continuation continuation;
    try {
      continuation = decodeAddress(link);
    } on AddressError catch (e) {
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Couldn’t open the note'),
          content: Text(e.message),
          actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('OK'))],
        ),
      );
      return;
    }
    final (note, what) = await store.receive(continuation);
    if (!mounted) return;
    final navigator = Navigator.of(context);
    navigator.popUntil((route) => route.isFirst);
    await navigator.push(MaterialPageRoute<void>(
      builder: (_) => NotePage(
        store: store,
        note: note,
        platform: widget.platform,
        arrival: what,
        cursor: continuation.cursor,
      ),
    ));
    if (mounted) setState(() {});
  }

  Future<void> open(Note note, {bool editing = false}) async {
    await Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => NotePage(store: store!, note: note, platform: widget.platform, editing: editing),
    ));
    if (mounted) setState(() {});
  }

  Future<void> newNote() async {
    final note = await store!.create('');
    await open(note, editing: true);
  }

  @override
  Widget build(BuildContext context) {
    final store = this.store;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Notes'),
        actions: [
          IconButton(
            tooltip: 'Trash',
            icon: const Icon(Icons.delete_outline),
            onPressed: store == null
                ? null
                : () async {
                    await Navigator.of(context).push(MaterialPageRoute<void>(
                      builder: (_) => TrashPage(store: store, platform: widget.platform),
                    ));
                    if (mounted) setState(() {});
                  },
          ),
        ],
      ),
      floatingActionButton: store == null
          ? null
          : FloatingActionButton.extended(onPressed: newNote, icon: const Icon(Icons.add), label: const Text('New Note')),
      body: failure != null
          ? Center(child: Padding(padding: const EdgeInsets.all(24), child: Text('Couldn’t read the notes: $failure')))
          : store == null
          ? const Center(child: CircularProgressIndicator())
          : _list(context, store),
    );
  }

  Widget _list(BuildContext context, NoteStore store) {
    final query = search.text.trim();
    final notes = store.sorted.where((n) => matches(n, query)).toList();
    final tags = tagCounts(store.notes.values);
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
          child: SearchBar(
            controller: search,
            hintText: 'Search notes or #tags',
            leading: const Icon(Icons.search),
            trailing: [
              if (query.isNotEmpty)
                IconButton(tooltip: 'Clear the search', icon: const Icon(Icons.close), onPressed: search.clear),
            ],
          ),
        ),
        if (tags.isNotEmpty)
          SizedBox(
            height: 48,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12),
              children: [
                for (final (tag, count) in tags)
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 4),
                    child: FilterChip(
                      label: Text('#$tag $count'),
                      selected: query == '#$tag',
                      onSelected: (on) => search.text = on ? '#$tag' : '',
                    ),
                  ),
              ],
            ),
          ),
        Expanded(
          child: notes.isEmpty
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(32),
                    child: Text(
                      query.isNotEmpty
                          ? 'No note has “$query”.'
                          : 'No notes yet.\n\nOn your FlickOS computer, open a note in Notes and click '
                                'Continue on Phone. Or tap New Note.',
                      textAlign: TextAlign.center,
                    ),
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.only(bottom: 88),
                  itemCount: notes.length,
                  itemBuilder: (context, i) {
                    final note = notes[i];
                    return ListTile(
                      title: Text(note.title, maxLines: 1, overflow: TextOverflow.ellipsis),
                      subtitle: Text(details(context, note)),
                      onTap: () => open(note),
                    );
                  },
                ),
        ),
      ],
    );
  }
}

/// Every word of the query starts a word of the note, every #tag is one of
/// its tags (#project also finds #project/flickos), as on the computer.
bool matches(Note note, String query) {
  if (query.isEmpty) return true;
  final words = ' ${fold(note.text).split(RegExp(r'[^\p{L}\p{N}_]+', unicode: true)).join(' ')}';
  for (final part in query.split(RegExp(r'\s+'))) {
    if (part.startsWith('#')) {
      final tag = fold(part.substring(1));
      if (tag.isNotEmpty && !note.info.tags.any((t) => t == tag || t.startsWith('$tag/'))) return false;
    } else {
      for (final word in fold(part).split(RegExp(r'[^\p{L}\p{N}_]+', unicode: true))) {
        if (word.isNotEmpty && !words.contains(' $word')) return false;
      }
    }
  }
  return true;
}

List<(String, int)> tagCounts(Iterable<Note> notes) {
  final counts = <String, int>{};
  for (final note in notes) {
    for (final tag in note.info.tags) {
      counts[tag] = (counts[tag] ?? 0) + 1;
    }
  }
  return counts.entries.map((e) => (e.key, e.value)).toList()
    ..sort((a, b) => a.$2 != b.$2 ? b.$2.compareTo(a.$2) : a.$1.compareTo(b.$1));
}

String shortDate(BuildContext context, DateTime when, {DateTime? now}) {
  final l = MaterialLocalizations.of(context);
  now ??= DateTime.now();
  if (when.year == now.year && when.month == now.month && when.day == now.day) {
    return l.formatTimeOfDay(TimeOfDay.fromDateTime(when), alwaysUse24HourFormat: MediaQuery.alwaysUse24HourFormatOf(context));
  }
  return when.year == now.year ? l.formatShortMonthDay(when) : l.formatShortDate(when);
}

String details(BuildContext context, Note note) => [
  shortDate(context, note.modified),
  if (note.info.items > 0) note.info.left == 0 ? 'Done' : '${note.info.left} left',
  if (note.origin != null) 'from ${note.origin}',
].join(' · ');

// --- A note ---

class NotePage extends StatefulWidget {
  const NotePage({
    super.key,
    required this.store,
    required this.note,
    required this.platform,
    this.arrival,
    this.cursor,
    this.editing = false,
  });

  final NoteStore store;
  final Note note;
  final Platform platform;

  /// How it arrived from the computer, when it just did.
  final Received? arrival;

  /// Where the computer's cursor was (UTF-16), when it just arrived.
  final int? cursor;
  final bool editing;

  @override
  State<NotePage> createState() => _NotePageState();
}

class _NotePageState extends State<NotePage> with WidgetsBindingObserver {
  late final MarkdownController controller;
  late final FocusNode focus;
  late bool editing;
  Timer? saveTimer;
  bool deleted = false;

  Note get note => widget.note;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    controller = MarkdownController(text: note.text);
    previous = note.text;
    focus = FocusNode();
    // A list with open items arrives to be ticked off; anything else to go on typing.
    editing = widget.editing || (widget.arrival != null && note.info.left == 0);
    final cursor = widget.cursor;
    if (cursor != null) controller.selection = TextSelection.collapsed(offset: cursor.clamp(0, note.text.length));
    controller.addListener(changed);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    save();
    controller.dispose();
    focus.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed) save();     // leaving the app keeps the typing
  }

  String previous = '';

  void changed() {
    final text = controller.text;
    if (text == note.text) return;
    // Enter at the end of a list line continues the list (ADR-006).
    final sel = controller.selection;
    if (text.length == previous.length + 1 && sel.isCollapsed && sel.start > 0 && text[sel.start - 1] == '\n' &&
        previous.isNotEmpty) {
      final before = text.substring(0, sel.start - 1);
      final lineStart = before.lastIndexOf('\n') + 1;
      final line = before.substring(lineStart);
      final after = text.substring(sel.start);
      if (after.isEmpty || after.startsWith('\n')) {
        final next = continued(line);
        if (next != null) {
          previous = text;
          if (next.isEmpty) {
            // An empty item ends the list: the marker goes, no new line.
            controller.value = TextEditingValue(
              text: before.substring(0, lineStart) + after,
              selection: TextSelection.collapsed(offset: lineStart),
            );
          } else {
            controller.value = TextEditingValue(
              text: '$before\n$next$after',
              selection: TextSelection.collapsed(offset: sel.start + next.length),
            );
          }
          return;
        }
      }
    }
    previous = controller.text;
    saveTimer?.cancel();
    saveTimer = Timer(saveDelay, save);
    setState(() {});
  }

  void save() {
    saveTimer?.cancel();
    if (deleted) return;
    if (controller.text != note.text) widget.store.save(note, controller.text);
  }

  void toggle(int line) {
    final text = toggleLine(note.text, line);
    controller.text = text;
    widget.store.save(note, text);
    setState(() {});
  }

  void startEditing({int? offset}) {
    setState(() => editing = true);
    if (offset != null) controller.selection = TextSelection.collapsed(offset: offset);
    focus.requestFocus();
  }

  Future<void> delete() async {
    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);
    save();
    deleted = true;
    if (note.text.trim().isEmpty) {
      // Nothing to keep: an empty note isn't put in the trash.
      await widget.store.delete(note);
      await widget.store.deleteForever(widget.store.trash[note.id]!);
      navigator.pop();
      return;
    }
    await widget.store.delete(note);
    navigator.pop();
    messenger.showSnackBar(SnackBar(
      content: Text('Moved “${note.title}” to the trash.'),
      action: SnackBarAction(label: 'Undo', onPressed: () => widget.store.restore(widget.store.trash[note.id]!)),
    ));
  }

  @override
  Widget build(BuildContext context) => PopScope(
    onPopInvokedWithResult: (didPop, _) {
      if (didPop && !deleted && note.text.trim().isEmpty && note.origin == null) {
        // A new note left empty leaves nothing behind.
        deleted = true;
        widget.store.delete(note).then((_) => widget.store.deleteForever(widget.store.trash[note.id]!));
      }
    },
    child: Scaffold(
      appBar: AppBar(
        title: Text(note.title, maxLines: 1, overflow: TextOverflow.ellipsis),
        actions: [
          IconButton(
            tooltip: editing ? 'Done' : 'Edit',
            icon: Icon(editing ? Icons.check : Icons.edit_outlined),
            onPressed: () {
              if (editing) {
                save();
                focus.unfocus();
                setState(() => editing = false);
              } else {
                startEditing();
              }
            },
          ),
          IconButton(
            tooltip: 'Share',
            icon: const Icon(Icons.share_outlined),
            onPressed: () {
              save();
              widget.platform.share(note.title, controller.text);
            },
          ),
          IconButton(tooltip: 'Move to Trash', icon: const Icon(Icons.delete_outline), onPressed: delete),
        ],
      ),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (note.origin != null) _origin(context),
          Expanded(child: editing ? _editor(context) : _reader(context)),
        ],
      ),
    ),
  );

  Widget _origin(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final arrived = switch (widget.arrival) {
      Received.replaced => ' The older copy is in the trash.',
      Received.keptBoth => ' You had changed this note here, so both are kept.',
      _ => '',
    };
    return Container(
      color: widget.arrival != null ? scheme.secondaryContainer : scheme.surfaceContainerHighest,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Text(
        '${widget.arrival != null ? 'Continued from' : 'From'} ${note.origin} · ${note.path}.$arrived',
        style: TextStyle(color: widget.arrival != null ? scheme.onSecondaryContainer : scheme.onSurfaceVariant),
      ),
    );
  }

  Widget _editor(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(horizontal: 16),
    child: TextField(
      controller: controller,
      focusNode: focus,
      autofocus: true,
      expands: true,
      maxLines: null,
      keyboardType: TextInputType.multiline,
      textCapitalization: TextCapitalization.sentences,
      decoration: const InputDecoration(border: InputBorder.none, hintText: 'Type your note. A first line is its title.'),
    ),
  );

  Widget _reader(BuildContext context) {
    final lines = note.text.split('\n');
    final theme = Theme.of(context);
    final widgets = <Widget>[];
    var offset = 0;
    var inCode = false;
    for (var i = 0; i < lines.length; i++) {
      final line = lines[i];
      final start = offset;
      offset += line.length + 1;
      final fence = RegExp(r'^ {0,3}(```|~~~)').hasMatch(line);
      if (fence || inCode) {
        if (fence) inCode = !inCode;
        widgets.add(GestureDetector(
          onTap: () => startEditing(offset: start),
          child: Text(line, style: theme.textTheme.bodyMedium?.copyWith(fontFamily: 'monospace')),
        ));
        continue;
      }
      final column = boxColumn(line);
      if (column != null) {
        final ticked = isTicked(line);
        final indent = item.firstMatch(line)!.group(1)!.replaceAll('\t', '    ').length;
        widgets.add(InkWell(
          onTap: () => toggle(i),
          child: Padding(
            padding: EdgeInsets.only(left: indent * 8.0),
            child: Row(children: [
              Checkbox(value: ticked, onChanged: (_) => toggle(i)),
              Expanded(
                child: Text.rich(
                  inlineSpans(line.substring(column + 3).trimLeft(), theme),
                  style: ticked
                      ? TextStyle(decoration: TextDecoration.lineThrough, color: theme.colorScheme.onSurfaceVariant)
                      : null,
                ),
              ),
            ]),
          ),
        ));
        continue;
      }
      final heading = RegExp(r'^(#{1,6})[ \t]+').firstMatch(line);
      final style = heading == null
          ? theme.textTheme.bodyLarge
          : [theme.textTheme.headlineSmall, theme.textTheme.titleLarge, theme.textTheme.titleMedium][
                  (heading.group(1)!.length - 1).clamp(0, 2)]
              ?.copyWith(fontWeight: FontWeight.bold);
      widgets.add(GestureDetector(
        onTap: () => startEditing(offset: start + line.length),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 2),
          child: line.trim().isEmpty
              ? const SizedBox(height: 12, width: double.infinity)
              : Text.rich(inlineSpans(heading == null ? line : line.substring(heading.end), theme), style: style),
        ),
      ));
    }
    return ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 32), children: widgets);
  }
}

final _inline = RegExp(r'`[^`\n]+`|\*\*[^*\n]+\*\*|(?<![\p{L}\p{N}_#])#[\p{L}][\p{L}\p{N}_/-]*', unicode: true);

/// A line's words with code, bold and tags styled; the marks themselves stay.
TextSpan inlineSpans(String text, ThemeData theme) {
  final spans = <InlineSpan>[];
  var at = 0;
  for (final m in _inline.allMatches(text)) {
    if (m.start > at) spans.add(TextSpan(text: text.substring(at, m.start)));
    final s = m.group(0)!;
    spans.add(TextSpan(
      text: s.startsWith('**') ? s.substring(2, s.length - 2) : s,
      style: s.startsWith('`')
          ? const TextStyle(fontFamily: 'monospace')
          : s.startsWith('**')
          ? const TextStyle(fontWeight: FontWeight.bold)
          : TextStyle(color: theme.colorScheme.primary),
    ));
    at = m.end;
  }
  if (at < text.length) spans.add(TextSpan(text: text.substring(at)));
  return TextSpan(children: spans);
}

/// The editor's text with headings, ticked items and tags styled, every
/// character kept (the text is the file).
class MarkdownController extends TextEditingController {
  MarkdownController({super.text});

  @override
  TextSpan buildTextSpan({required BuildContext context, TextStyle? style, required bool withComposing}) {
    final theme = Theme.of(context);
    final dim = TextStyle(color: theme.colorScheme.onSurfaceVariant);
    final spans = <InlineSpan>[];
    final lines = text.split('\n');
    for (var i = 0; i < lines.length; i++) {
      final line = lines[i];
      final heading = RegExp(r'^(#{1,6})([ \t]+)').firstMatch(line);
      if (heading != null) {
        final size = [1.4, 1.2, 1.1][(heading.group(1)!.length - 1).clamp(0, 2)];
        final strong = TextStyle(fontWeight: FontWeight.bold, fontSize: (style?.fontSize ?? 16) * size);
        spans
          ..add(TextSpan(text: heading.group(0), style: strong.merge(dim)))
          ..add(TextSpan(text: line.substring(heading.end), style: strong));
      } else if (isTicked(line)) {
        spans.add(TextSpan(text: line, style: dim.copyWith(decoration: TextDecoration.lineThrough)));
      } else {
        final column = boxColumn(line);
        if (column != null) {
          spans
            ..add(TextSpan(text: line.substring(0, column), style: dim))
            ..add(TextSpan(text: line.substring(column, column + 3),
                style: TextStyle(color: theme.colorScheme.primary, fontWeight: FontWeight.bold)))
            ..add(inlineMarks(line.substring(column + 3), theme));
        } else {
          spans.add(inlineMarks(line, theme));
        }
      }
      if (i < lines.length - 1) spans.add(const TextSpan(text: '\n'));
    }
    return TextSpan(style: style, children: spans);
  }
}

/// Like [inlineSpans], but keeping every character (for the editor).
TextSpan inlineMarks(String text, ThemeData theme) {
  final spans = <InlineSpan>[];
  var at = 0;
  for (final m in _inline.allMatches(text)) {
    if (m.start > at) spans.add(TextSpan(text: text.substring(at, m.start)));
    final s = m.group(0)!;
    spans.add(TextSpan(
      text: s,
      style: s.startsWith('`')
          ? const TextStyle(fontFamily: 'monospace')
          : s.startsWith('**')
          ? const TextStyle(fontWeight: FontWeight.bold)
          : TextStyle(color: theme.colorScheme.primary),
    ));
    at = m.end;
  }
  if (at < text.length) spans.add(TextSpan(text: text.substring(at)));
  return TextSpan(children: spans);
}

// --- The trash ---

class TrashPage extends StatefulWidget {
  const TrashPage({super.key, required this.store, required this.platform});

  final NoteStore store;
  final Platform platform;

  @override
  State<TrashPage> createState() => _TrashPageState();
}

class _TrashPageState extends State<TrashPage> {
  Future<void> emptyTrash() async {
    final sure = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Empty the trash?'),
        content: Text('${widget.store.trash.length == 1 ? 'The note' : 'All ${widget.store.trash.length} notes'} '
            'in the trash will be deleted. This can’t be undone.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: Theme.of(context).colorScheme.error),
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Empty Trash'),
          ),
        ],
      ),
    );
    if (sure == true) {
      await widget.store.emptyTrash();
      setState(() {});
    }
  }

  Future<void> choose(Trashed item) async {
    final action = await showModalBottomSheet<String>(
      context: context,
      builder: (context) => SafeArea(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          ListTile(title: Text(item.note.title, style: Theme.of(context).textTheme.titleMedium)),
          ListTile(
            leading: const Icon(Icons.restore),
            title: const Text('Put Back'),
            onTap: () => Navigator.pop(context, 'restore'),
          ),
          ListTile(
            leading: const Icon(Icons.delete_forever_outlined),
            title: const Text('Delete Now'),
            onTap: () => Navigator.pop(context, 'delete'),
          ),
        ]),
      ),
    );
    if (action == 'restore') {
      await widget.store.restore(item);
    } else if (action == 'delete') {
      await widget.store.deleteForever(item);
    }
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final items = widget.store.trashSorted;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Trash'),
        actions: [if (items.isNotEmpty) TextButton(onPressed: emptyTrash, child: const Text('Empty Trash'))],
      ),
      body: items.isEmpty
          ? const Center(child: Text('The trash is empty.'))
          : ListView(children: [
              const Padding(
                padding: EdgeInsets.all(16),
                child: Text('Notes in the trash are deleted after $trashDays days.'),
              ),
              for (final item in items)
                ListTile(
                  title: Text(item.note.title, maxLines: 1, overflow: TextOverflow.ellipsis),
                  subtitle: Text('Deleted ${shortDate(context, item.deleted)}'),
                  onTap: () => choose(item),
                ),
            ]),
    );
  }
}
