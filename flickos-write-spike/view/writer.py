#!/usr/bin/python3
"""Spike 2: Write's writing view in GtkSourceView 4.

    ./writer.py [FILE]                         a window to type in
    ./writer.py --fullscreen [FILE]            the writing session's page
    ./writer.py --focus sentence|paragraph     dim all but the current one
    ./writer.py --bench [FILE]                 time keystrokes and cursor moves, print a table
    ./writer.py --shot OUT.png [--fullscreen]  grim the screen once it's drawn, then quit
    ./writer.py --at 0.5 …                     start with the cursor in the middle

Other options: --no-typewriter, --naive (focus retags the whole chapter on
every move, to compare), --width N (characters), --font NAME, --size WxH.
GTK_THEME=Arc ./writer.py shows the Light style; GDK_DPI_SCALE=1.5 bigger text.
Throwaway code: it answers phase 0's questions, it isn't phase 1.
"""
import argparse
import os
import re
import statistics
import subprocess
import sys
import time

import gi
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GtkSource", "4")
from gi.repository import GLib, Gdk, Gtk, GtkSource, Pango  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEME_DIR = os.path.join(HERE, "generated")
START = time.perf_counter()

# where a sentence ends: . ! ? … then closing quotes, then a space
SENTENCE_END = re.compile(r"[.!?…][\"”’)\]]*\s+")


def ms(seconds):
    return seconds * 1000


def theme_colors(widget):
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
    """Notes' run-time scheme, cut down: dimmed markup from the theme."""
    text, base, accent = theme_colors(widget)
    dim = hexcolor(mix(text, base, 0.5))
    acc = hexcolor(accent)
    styles = {
        "flickos-notes:heading1": 'bold="true" scale="1.6"',
        "flickos-notes:heading2": 'bold="true" scale="1.3"',
        "flickos-notes:heading3": 'bold="true" scale="1.1"',
        "flickos-notes:markup": f'foreground="{dim}"',
        "flickos-notes:tag": f'foreground="{acc}"',
        "flickos-notes:strong": 'bold="true"',
        "flickos-notes:emphasis": 'italic="true"',
        "flickos-notes:link": f'foreground="{acc}" underline="single"',
    }
    lines = "\n".join(f'  <style name="{k}" {v}/>' for k, v in styles.items())
    os.makedirs(SCHEME_DIR, exist_ok=True)
    path = os.path.join(SCHEME_DIR, "flickos-write.xml")
    with open(path + ".tmp", "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<style-scheme id="flickos-write" name="Write" version="1.0">\n'
                f"{lines}\n</style-scheme>\n")
    os.replace(path + ".tmp", path)
    manager = GtkSource.StyleSchemeManager.get_default()
    if SCHEME_DIR not in manager.get_search_path():
        manager.prepend_search_path(SCHEME_DIR)
    manager.force_rescan()
    return manager.get_scheme("flickos-write"), dim


class Writer:
    def __init__(self, args):
        self.args = args
        self.buffer = GtkSource.Buffer()
        self.view = GtkSource.View(buffer=self.buffer)
        self.view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.view.set_pixels_inside_wrap(4)
        self.view.set_top_margin(48)
        self.view.get_style_context().add_class("writer")
        css = Gtk.CssProvider()
        css.load_from_data(
            f'textview.writer {{ font-family: "{args.font}"; font-size: 13pt; }}'.encode())
        self.view.get_style_context().add_provider(
            css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        manager = GtkSource.LanguageManager.get_default()
        manager.set_search_path([HERE] + manager.get_search_path())
        self.buffer.set_language(manager.get_language("flickos-notes"))

        self.dim = self.buffer.create_tag("unfocused")
        self.range = None            # (start mark, end mark) left bright
        self.colors = None
        self.last_size = None
        self.loading = False

        self.view.connect("style-updated", self.on_style)
        self.view.connect("size-allocate", self.on_size)
        self.buffer.connect("highlight-updated", self.on_highlight)
        self.buffer.connect_after("changed", self.on_changed)
        self.buffer.connect_after("mark-set", self.on_mark_set)

    # --- looks ---------------------------------------------------------

    def on_style(self, view):
        key = tuple(hexcolor(c) for c in theme_colors(view))
        if key == self.colors:
            return
        self.colors = key
        scheme, dim = write_scheme(view)
        self.buffer.set_style_scheme(scheme)
        self.dim.set_property("foreground", dim)
        self.last_size = None
        self.on_size(view, view.get_allocation())

    def on_highlight(self, *_):
        # GtkSourceView makes its style tags while it highlights, after
        # ours, and a later tag wins: keep the dimming tag on top
        table = self.buffer.get_tag_table()
        if self.dim.get_priority() != table.get_size() - 1:
            self.dim.set_priority(table.get_size() - 1)

    def column_width(self):
        ctx = self.view.get_pango_context()
        font = self.view.get_style_context().get_property("font", Gtk.StateFlags.NORMAL)
        metrics = ctx.get_metrics(font, None)
        return metrics.get_approximate_char_width() / Pango.SCALE * self.args.width

    def on_size(self, view, alloc):
        size = (alloc.width, alloc.height)
        if size == self.last_size:
            return
        self.last_size = size
        side = max(24, int((alloc.width - self.column_width()) / 2))
        view.set_left_margin(side)
        view.set_right_margin(side)
        if not self.args.no_typewriter:
            view.set_bottom_margin(alloc.height // 2)

    # --- typewriter and focus ------------------------------------------

    def on_changed(self, buffer):
        # only after the writer's own changes: a scroll queued while the
        # text is loaded lands before the line heights are known
        if not self.args.no_typewriter and not self.loading:
            self.view.scroll_to_mark(buffer.get_insert(), 0, True, 0, 0.5)
        self.update_focus()

    def on_mark_set(self, buffer, where, mark):
        if mark == buffer.get_insert():
            self.update_focus()

    def paragraph(self, at):
        """Start and end iters of the block of non-blank lines at `at`."""
        def blank(it):
            end = it.copy()
            if not end.ends_line():
                end.forward_to_line_end()
            return not self.buffer.get_text(it, end, True).strip()

        start = self.buffer.get_iter_at_line(at.get_line())
        while start.get_line() > 0:
            prev = start.copy()
            prev.backward_line()
            if blank(prev):
                break
            start = prev
        end = self.buffer.get_iter_at_line(at.get_line())
        while True:
            nxt = end.copy()
            if not nxt.forward_line() or blank(nxt):
                break
            end = nxt
        if not end.ends_line():
            end.forward_to_line_end()
        return start, end

    def sentence(self, at):
        start, end = self.paragraph(at)
        text = self.buffer.get_text(start, end, True)
        here = at.get_offset() - start.get_offset()
        a, b = 0, len(text)
        for m in SENTENCE_END.finditer(text):
            if m.end() <= here:
                a = m.end()
            else:
                b = m.end()
                break
        base = start.get_offset()
        return self.buffer.get_iter_at_offset(base + a), self.buffer.get_iter_at_offset(base + b)

    def update_focus(self):
        if self.args.focus == "off":
            return
        at = self.buffer.get_iter_at_mark(self.buffer.get_insert())
        find = self.paragraph if self.args.focus == "paragraph" else self.sentence
        start, end = find(at)
        buf = self.buffer
        if self.args.naive or self.range is None:
            buf.apply_tag(self.dim, *buf.get_bounds())
            buf.remove_tag(self.dim, start, end)
            if self.range is None:
                self.range = (buf.create_mark(None, start, True),
                              buf.create_mark(None, end, False))
            else:
                buf.move_mark(self.range[0], start)
                buf.move_mark(self.range[1], end)
            return
        old_s = buf.get_iter_at_mark(self.range[0])
        old_e = buf.get_iter_at_mark(self.range[1])
        if old_s.equal(start) and old_e.equal(end):
            return
        buf.apply_tag(self.dim, old_s, old_e)     # the old range goes dim…
        buf.remove_tag(self.dim, start, end)      # …and only the new one is bright
        buf.move_mark(self.range[0], start)
        buf.move_mark(self.range[1], end)


def build(args):
    win = Gtk.Window(title="Write spike")
    w, h = (int(n) for n in args.size.split("x"))
    win.set_default_size(w, h)
    writer = Writer(args)
    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.add(writer.view)
    win.add(scroll)
    win.connect("destroy", Gtk.main_quit)
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            text = f.read()
    else:
        text = "# The Storm\n\nThe rain had not stopped since Tuesday. Mara had stopped counting the boats.\n"
    t0 = time.perf_counter()
    writer.loading = True
    writer.buffer.begin_not_undoable_action()
    writer.buffer.set_text(text)
    writer.buffer.end_not_undoable_action()
    writer.loading = False
    if args.at:
        it = writer.buffer.get_iter_at_offset(int(writer.buffer.get_char_count() * args.at))
        it.forward_sentence_end()
        writer.buffer.place_cursor(it)
        GLib.idle_add(lambda: writer.view.scroll_to_mark(writer.buffer.get_insert(), 0, True, 0, 0.5) and False)
    else:
        writer.buffer.place_cursor(writer.buffer.get_start_iter())
    writer.loaded = time.perf_counter() - t0
    if args.fullscreen:
        win.fullscreen()
    win.show_all()
    writer.view.grab_focus()
    return win, writer


# --- measuring ------------------------------------------------------------

class Bench:
    """Synthetic typing: each step is timed from the change to the frame
    that shows it (GdkFrameClock's after-paint), 40 ms apart like fast
    typing. The paint wait includes waiting for the screen's next refresh,
    so up to 16.7 ms of it is vsync, not work."""

    STEPS = 60

    def __init__(self, writer):
        self.w = writer
        self.rows = []
        self.queue = []
        self.samples = None

    def start(self):
        clock = self.w.view.get_frame_clock()
        clock.connect("after-paint", self.on_paint)
        self.pending = None
        b = self.w.buffer
        chars = b.get_char_count()
        for name, frac in (("start", 0.02), ("middle", 0.5), ("end", 0.98)):
            self.queue.append(("place", name, frac))
            self.queue += [("type", name)] * self.STEPS
            self.queue.append(("report", f"type at {name}"))
            self.queue += [("down", name)] * self.STEPS
            self.queue.append(("report", f"Down arrow at {name}"))
        self.queue += [("jump", "") for _ in range(10)]
        self.queue.append(("report", "jump start↔end"))
        self.queue.append(("done", ""))
        self.chars = chars
        GLib.timeout_add(40, self.step)

    def place(self, frac):
        b = self.w.buffer
        it = b.get_iter_at_offset(int(self.chars * frac))
        # inside a paragraph, not on a blank line
        while it.ends_line() and it.starts_line() and it.forward_line():
            pass
        if not it.ends_line():
            it.forward_to_line_end()
        b.place_cursor(it)
        self.w.view.scroll_to_mark(b.get_insert(), 0, True, 0, 0.5)

    def step(self):
        if not self.queue:
            return False
        kind, arg, *rest = self.queue.pop(0)
        b, v = self.w.buffer, self.w.view
        if kind == "place":
            self.place(rest[0])
            self.samples = []
            GLib.timeout_add(300, self.step)       # let it settle
            return False
        if kind == "report":
            self.rows.append((arg, self.samples))
            self.samples = []
            GLib.timeout_add(40, self.step)
            return False
        if kind == "done":
            self.print()
            Gtk.main_quit()
            return False
        t0 = time.perf_counter()
        if kind == "type":
            b.begin_user_action()
            # a space every 6 letters, a full stop every 40: sentences change
            n = len(self.samples)
            ch = ". " if n % 40 == 39 else (" " if n % 6 == 5 else "a")
            b.insert_interactive_at_cursor(ch, -1, True)
            b.end_user_action()
        elif kind == "down":
            v.emit("move-cursor", Gtk.MovementStep.DISPLAY_LINES, 1, False)
        elif kind == "jump":
            it = b.get_start_iter() if b.get_iter_at_mark(b.get_insert()).get_offset() > self.chars / 2 \
                else b.get_end_iter()
            b.place_cursor(it)
            v.scroll_to_mark(b.get_insert(), 0, True, 0, 0.5)
        t1 = time.perf_counter()
        self.pending = (t0, t1)
        GLib.timeout_add(500, self.timeout, self.pending)
        return False

    def on_paint(self, clock):
        if self.pending is None:
            return
        t0, t1 = self.pending
        self.pending = None
        self.samples.append((ms(t1 - t0), ms(time.perf_counter() - t0)))
        GLib.timeout_add(40, self.step)

    def timeout(self, pending):
        if self.pending is pending:          # nothing was painted
            self.pending = None
            t0, t1 = pending
            self.samples.append((ms(t1 - t0), None))
            GLib.timeout_add(40, self.step)
        return False

    def print(self):
        a = self.w.args
        print(f"chapter: {self.chars:,} characters, {len(self.w.buffer.get_text(*self.w.buffer.get_bounds(), True).split()):,} words;"
              f" focus {a.focus}{' (naive)' if a.naive else ''}; typewriter {'off' if a.no_typewriter else 'on'};"
              f" window {self.w.view.get_allocated_width()}×{self.w.view.get_allocated_height()}")
        print(f"set_text: {ms(self.w.loaded):.0f} ms; first frame {ms(self.w.first_frame):.0f} ms after start")
        print(f"{'':24} {'work (ms) median / max':>24} {'to the screen (ms) median / max':>34}  no paint")
        for name, samples in self.rows:
            work = [s[0] for s in samples]
            paint = [s[1] for s in samples if s[1] is not None]
            missing = sum(1 for s in samples if s[1] is None)
            p = f"{statistics.median(paint):6.1f} / {max(paint):6.1f}" if paint else "-"
            print(f"{name:24} {statistics.median(work):11.2f} / {max(work):6.2f}       {p:>24}  {missing}")
        with open("/proc/self/smaps_rollup") as f:
            for line in f:
                if line.startswith(("Rss:", "Pss:")):
                    print(line.strip())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("file", nargs="?")
    p.add_argument("--fullscreen", action="store_true")
    p.add_argument("--focus", choices=("off", "sentence", "paragraph"), default="off")
    p.add_argument("--naive", action="store_true")
    p.add_argument("--no-typewriter", action="store_true")
    p.add_argument("--width", type=int, default=66)
    p.add_argument("--font", default="DejaVu Serif")
    p.add_argument("--size", default="1000x700")
    p.add_argument("--bench", action="store_true")
    p.add_argument("--shot")
    p.add_argument("--at", type=float, help="start with the cursor this far in (0.5 = the middle)")
    args = p.parse_args()

    win, writer = build(args)
    writer.first_frame = None

    def first(*_):
        if writer.first_frame is None:
            writer.first_frame = time.perf_counter() - START
            if args.bench:
                GLib.timeout_add(1500, lambda: Bench(writer).start() and False)
            if args.shot:
                GLib.timeout_add(1500, shot)
        return False

    def shot():
        subprocess.run(["grim", args.shot], check=True)
        alloc = writer.view.get_allocation()
        print(f"view {alloc.width}×{alloc.height}, left margin {writer.view.get_left_margin()},"
              f" column {writer.column_width():.0f} px")
        Gtk.main_quit()
        return False

    writer.view.connect_after("draw", first)
    Gtk.main()


if __name__ == "__main__":
    main()
