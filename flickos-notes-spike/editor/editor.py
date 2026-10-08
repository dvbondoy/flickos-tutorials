#!/usr/bin/python3
"""Spike 3: the Notes editor in GtkSourceView 4.

    ./editor.py [--lang stock|own] [FILE]        a window to type in
    ./editor.py --snapshot OUT.png [--lang …]     draw it offscreen, no window
    ./editor.py --selftest                        checklist behaviour + undo

GTK_THEME=Arc ./editor.py … shows the Light style's theme, Arc-Dark the Dark.
Throwaway code: it answers phase 0's questions, it isn't phase 1.
"""
import argparse
import os
import re
import sys

import gi
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GtkSource", "4")
from gi.repository import GLib, Gdk, Gtk, GtkSource  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEME_DIR = os.path.join(HERE, "generated")

SAMPLE = """# Groceries
#home #errands

Things for the weekend, **before** Saturday. Ask *Ana* about the 🍰 cake.

- [ ] milk
- [x] bread
- [ ] eggs, the brown ones
  - [ ] a dozen

## Notes
- see [the shop](https://example.com/shop) and https://example.com
- page.html#top is not a tag, # Heading needs its space
1. numbered
2. [ ] numbered item

### Code
Run `flickos-phone send` here:

```
flickos-notes continue Groceries.md
```

> a quote with #tag
"""

# list line: indent, marker, spaces; then maybe a checkbox
ITEM = re.compile(r"^([ \t]*)([-*+]|\d+[.)])([ \t]+)(\[[ xX]\] ?)?")


def theme_colors(widget):
    """(text, base, accent) of the running GTK theme, as #rrggbb."""
    ctx = widget.get_style_context()

    def color(name, fallback):
        ok, rgba = ctx.lookup_color(name)
        return rgba if ok else fallback

    text = color("theme_text_color", ctx.get_color(Gtk.StateFlags.NORMAL))
    base = color("theme_base_color", Gdk.RGBA(1, 1, 1, 1))
    accent = color("theme_selected_bg_color", text)
    return text, base, accent


def hexcolor(rgba):
    return "#%02x%02x%02x" % tuple(round(c * 255) for c in (rgba.red, rgba.green, rgba.blue))


def mix(a, b, t):
    return Gdk.RGBA(a.red * (1 - t) + b.red * t, a.green * (1 - t) + b.green * t,
                    a.blue * (1 - t) + b.blue * t, 1)


def write_scheme(widget):
    """A scheme made at run time from the theme's own colors.

    A scheme file can only hold fixed colors, so "dimmed" (text halfway to
    the background) and the accent are computed from the theme and the file
    written where GtkSourceView looks. Nothing here is a FlickOS color."""
    text, base, accent = theme_colors(widget)
    dim = hexcolor(mix(text, base, 0.5))
    acc = hexcolor(accent)
    styles = {
        # stock markdown.lang maps to def:*, ours to flickos-notes:*
        "def:heading": 'bold="true" scale="1.35"',
        "def:strong-emphasis": 'bold="true"',
        "def:emphasis": 'italic="true"',
        "def:list-marker": f'foreground="{dim}"',
        "def:link-destination": f'foreground="{dim}"',
        "def:link-text": f'foreground="{acc}"',
        "flickos-notes:heading1": 'bold="true" scale="1.6"',
        "flickos-notes:heading2": 'bold="true" scale="1.3"',
        "flickos-notes:heading3": 'bold="true" scale="1.1"',
        "flickos-notes:markup": f'foreground="{dim}"',
        "flickos-notes:tag": f'foreground="{acc}"',
        "flickos-notes:checkbox": f'foreground="{acc}" bold="true"',
        "flickos-notes:task-done": f'foreground="{dim}" strikethrough="true"',
        "flickos-notes:strong": 'bold="true"',
        "flickos-notes:emphasis": 'italic="true"',
        "flickos-notes:link": f'foreground="{acc}" underline="single"',
    }
    lines = "\n".join(f'  <style name="{k}" {v}/>' for k, v in styles.items())
    os.makedirs(SCHEME_DIR, exist_ok=True)
    path = os.path.join(SCHEME_DIR, "flickos-notes.xml")
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<style-scheme id="flickos-notes" name="Notes" version="1.0">\n'
                f"{lines}\n</style-scheme>\n")
    os.replace(tmp, path)
    manager = GtkSource.StyleSchemeManager.get_default()
    if SCHEME_DIR not in manager.get_search_path():
        manager.prepend_search_path(SCHEME_DIR)
    manager.force_rescan()
    return manager.get_scheme("flickos-notes")


class Editor:
    def __init__(self, lang):
        self.buffer = GtkSource.Buffer()
        self.view = GtkSource.View(buffer=self.buffer)
        self.view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.view.set_left_margin(16)
        self.view.set_right_margin(16)
        self.view.set_top_margin(12)
        self.view.set_pixels_below_lines(2)

        manager = GtkSource.LanguageManager.get_default()
        if lang == "own":
            manager.set_search_path([HERE] + manager.get_search_path())
            self.buffer.set_language(manager.get_language("flickos-notes"))
        else:
            self.buffer.set_language(manager.get_language("markdown"))

        # code in the monospace font: a scheme can't set a font, but each
        # context class is a named tag (made while highlighting), which can
        self.buffer.connect("highlight-updated", self.on_highlight)
        self.view.connect("style-updated", self.on_style)
        self.view.connect("button-press-event", self.on_click)
        self.view.connect("key-press-event", self.on_key)
        self.view.connect("motion-notify-event", self.on_motion)

    def on_style(self, view):
        # setting a scheme restyles the view, which emits style-updated
        # again: rewrite it only when the theme's colors changed
        key = tuple(hexcolor(c) for c in theme_colors(view))
        if key != getattr(self, "colors", None):
            self.colors = key
            self.buffer.set_style_scheme(write_scheme(view))

    def on_highlight(self, buffer, start, end):
        tag = buffer.get_tag_table().lookup("gtksourceview:context-classes:code")
        if tag and not tag.props.family_set:
            tag.props.family = "monospace"

    # checklists (ADR-006)

    def line_text(self, line):
        start = self.buffer.get_iter_at_line(line)
        end = start.copy()
        if not end.ends_line():
            end.forward_to_line_end()
        return start, self.buffer.get_text(start, end, True)

    def checkbox_at(self, it):
        """(line, column of "[") when iter `it` is on a line's checkbox."""
        line = it.get_line()
        _, text = self.line_text(line)
        m = ITEM.match(text)
        if not m or not m.group(4):
            return None
        col = m.start(4)
        if col <= it.get_line_offset() <= col + 3:
            return line, col
        return None

    def toggle(self, line, col):
        start = self.buffer.get_iter_at_line_offset(line, col + 1)
        end = start.copy()
        end.forward_char()
        new = " " if self.buffer.get_text(start, end, True) in "xX" else "x"
        self.buffer.begin_user_action()
        self.buffer.delete(start, end)
        self.buffer.insert(self.buffer.get_iter_at_line_offset(line, col + 1), new)
        self.buffer.end_user_action()

    def iter_at_pointer(self, event):
        x, y = self.view.window_to_buffer_coords(Gtk.TextWindowType.TEXT,
                                                 int(event.x), int(event.y))
        ok, it = self.view.get_iter_at_location(x, y)
        return it if ok else None

    def on_click(self, view, event):
        if event.button != 1 or event.type != Gdk.EventType.BUTTON_PRESS:
            return False
        it = self.iter_at_pointer(event)
        box = it and self.checkbox_at(it)
        if not box:
            return False
        self.toggle(*box)
        return True

    def on_motion(self, view, event):
        it = self.iter_at_pointer(event)
        window = view.get_window(Gtk.TextWindowType.TEXT)
        name = "pointer" if it and self.checkbox_at(it) else "text"
        window.set_cursor(Gdk.Cursor.new_from_name(window.get_display(), name))
        return False

    def on_key(self, view, event):
        ctrl = event.state & Gdk.ModifierType.CONTROL_MASK
        if event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and not ctrl \
                and not event.state & Gdk.ModifierType.SHIFT_MASK:
            return self.enter()
        if ctrl and event.keyval in (Gdk.KEY_l, Gdk.KEY_L):
            self.checklist()
            return True
        return False

    def enter(self):
        """Enter in a list: continue it, or end it on an empty item."""
        if self.buffer.get_has_selection():
            return False
        cursor = self.buffer.get_iter_at_mark(self.buffer.get_insert())
        start, text = self.line_text(cursor.get_line())
        if cursor.get_line_offset() != len(text):
            return False
        m = ITEM.match(text)
        if not m:
            return False
        self.buffer.begin_user_action()
        if m.end() == len(text.rstrip()) or text[m.end():].strip() == "":
            # empty item: drop its marker, the list ends
            self.buffer.delete(start, cursor)
        else:
            marker = m.group(2)
            if marker[0].isdigit():
                marker = f"{int(marker[:-1]) + 1}{marker[-1]}"
            box = "[ ] " if m.group(4) else ""
            self.buffer.insert_at_cursor(f"\n{m.group(1)}{marker}{m.group(3)}{box}")
        self.buffer.end_user_action()
        self.view.scroll_mark_onscreen(self.buffer.get_insert())
        return True

    def checklist(self):
        """Ctrl+L: the selected lines become items, or plain again."""
        bounds = self.buffer.get_selection_bounds()
        if bounds:
            first, last = bounds[0].get_line(), bounds[1].get_line()
            if bounds[1].starts_line() and last > first:
                last -= 1
        else:
            first = last = self.buffer.get_iter_at_mark(self.buffer.get_insert()).get_line()
        lines = [self.line_text(n)[1] for n in range(first, last + 1)]
        all_items = all((m := ITEM.match(t)) and m.group(4) for t in lines if t.strip())
        self.buffer.begin_user_action()
        for n, text in zip(range(first, last + 1), lines):
            if not text.strip():
                continue
            m = ITEM.match(text)
            if all_items:
                new = m.group(1) + text[m.end():]
            elif m and m.group(4):
                continue
            elif m:
                new = text[:m.end()] + "[ ] " + text[m.end():]
            else:
                indent = text[:len(text) - len(text.lstrip())]
                new = f"{indent}- [ ] {text.lstrip()}"
            start, _ = self.line_text(n)
            end = start.copy()
            if not end.ends_line():
                end.forward_to_line_end()
            self.buffer.delete(start, end)
            self.buffer.insert(self.buffer.get_iter_at_line(n), new)
        self.buffer.end_user_action()


def snapshot(editor, out):
    win = Gtk.OffscreenWindow()
    scroll = Gtk.ScrolledWindow()
    scroll.add(editor.view)
    win.add(scroll)
    win.set_size_request(760, 820)
    win.show_all()

    def grab():
        b = editor.buffer
        b.ensure_highlight(b.get_start_iter(), b.get_end_iter())
        while Gtk.events_pending():
            Gtk.main_iteration()
        win.get_pixbuf().savev(out, "png", [], [])
        Gtk.main_quit()
        return False
    GLib.timeout_add(700, grab)
    Gtk.main()


def selftest():
    ed = Editor("own")
    b = ed.buffer
    win = Gtk.OffscreenWindow()
    win.add(ed.view)
    win.show_all()
    results = []

    def check(name, got, want):
        ok = got == want
        results.append(ok)
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"\n  got  {got!r}\n  want {want!r}"))

    def text():
        return b.get_text(b.get_start_iter(), b.get_end_iter(), True)

    def put(t, line, col):
        b.begin_not_undoable_action()
        b.set_text(t)
        b.end_not_undoable_action()
        b.place_cursor(b.get_iter_at_line_offset(line, col))

    put("- [ ] milk\n", 0, 3)
    box = ed.checkbox_at(b.get_iter_at_line_offset(0, 3))
    check("checkbox found under the pointer", box, (0, 2))
    check("not a checkbox on the word", ed.checkbox_at(b.get_iter_at_line_offset(0, 7)), None)
    ed.toggle(*box)
    check("click ticks", text(), "- [x] milk\n")
    ed.toggle(*box)
    check("click unticks", text(), "- [ ] milk\n")
    b.undo()
    check("one undo puts the tick back", text(), "- [x] milk\n")
    b.undo()
    check("second undo: open again", text(), "- [ ] milk\n")

    put("- [ ] milk", 0, 10)
    ed.enter()
    check("Enter continues a checklist", text(), "- [ ] milk\n- [ ] ")
    ed.enter()
    check("Enter on an empty item ends it", text(), "- [ ] milk\n")
    b.undo()
    check("undo of the ending", text(), "- [ ] milk\n- [ ] ")
    b.undo()
    check("undo of the new item", text(), "- [ ] milk")

    put("  3. three", 0, 10)
    ed.enter()
    check("numbered list counts on", text(), "  3. three\n  4. ")

    put("milk\n\nbread\n", 0, 0)
    b.select_range(b.get_start_iter(), b.get_end_iter())
    ed.checklist()
    check("Ctrl+L makes items, skips blank lines", text(), "- [ ] milk\n\n- [ ] bread\n")
    b.select_range(b.get_start_iter(), b.get_end_iter())
    ed.checklist()
    check("Ctrl+L again makes them plain", text(), "milk\n\nbread\n")
    b.undo()
    check("one undo for the whole Ctrl+L", text(), "- [ ] milk\n\n- [ ] bread\n")

    put("- 🍰 [ ] cake", 0, 0)
    check("a [ ] later in the line is no box", ed.checkbox_at(b.get_iter_at_line_offset(0, 4)), None)
    put("- [ ] 🍰 cake\n- [ ] x", 1, 3)
    check("emoji before: the box is still found (code points)",
          ed.checkbox_at(b.get_iter_at_line_offset(1, 3)), (1, 2))
    print(f"{sum(results)}/{len(results)} passed")
    return 0 if all(results) else 1


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--lang", choices=("stock", "own"), default="own")
    p.add_argument("--snapshot", metavar="OUT.png")
    p.add_argument("--selftest", action="store_true")
    p.add_argument("file", nargs="?")
    a = p.parse_args()
    if a.selftest:
        return selftest()
    ed = Editor(a.lang)
    if a.file:
        with open(a.file, encoding="utf-8") as f:
            ed.buffer.set_text(f.read())
    else:
        ed.buffer.set_text(SAMPLE)
    ed.buffer.place_cursor(ed.buffer.get_start_iter())
    if a.snapshot:
        snapshot(ed, a.snapshot)
        return 0
    win = Gtk.Window(title=f"Notes editor spike ({a.lang})")
    win.set_default_size(760, 820)
    scroll = Gtk.ScrolledWindow()
    scroll.add(ed.view)
    win.add(scroll)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
