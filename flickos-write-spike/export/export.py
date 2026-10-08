#!/usr/bin/python3
"""Spike 4: export a project (a folder of `NN Title.md` chapters) without pandoc.

    ./export.py PROJECT --to odt|epub|docx|pdf [--output FILE] [--title T] [--author A]

ODT and EPUB are written with the standard library (zipfile + XML text);
DOCX and PDF are the ODT converted by `soffice --headless --convert-to`.
Only the Markdown Write writes is understood: headings, paragraphs,
*emphasis*, **strong**, > quotes, lists, and *** scene breaks. Anything else
(tables, images, code) goes out as plain text and is reported.
Throwaway code: it answers phase 0's questions, it isn't phase 1.
"""
import argparse
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile

CHAPTER = re.compile(r"^(\d{2,3}) (.+)\.md$")

# --- Markdown subset -> blocks --------------------------------------------
# A block is (kind, data): ("h", (level, text)), ("p", text), ("quote", text),
# ("list", (ordered, [text…])), ("break", None). Text is still Markdown
# inline; inline() turns it into runs.

SCENE = re.compile(r"^\s*(\*\s*\*\s*\*|-\s*-\s*-|#)\s*$")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
BULLET = re.compile(r"^\s*([-*+])\s+(.*)$")
NUMBER = re.compile(r"^\s*(\d+)[.)]\s+(.*)$")
UNKNOWN = re.compile(r"^\s*(\||!\[|```|<[a-zA-Z])")


def blocks(text, unknown):
    out = []
    para = []

    def flush():
        if para:
            out.append(("p", " ".join(s.strip() for s in para)))
            para.clear()

    for line in text.splitlines():
        if not line.strip():
            flush()
            continue
        if SCENE.match(line):
            flush()
            out.append(("break", None))
            continue
        m = HEADING.match(line)
        if m:
            flush()
            out.append(("h", (len(m.group(1)), m.group(2))))
            continue
        if line.lstrip().startswith(">"):
            flush()
            body = line.lstrip()[1:].strip()
            if out and out[-1][0] == "quote" and body:
                out[-1] = ("quote", out[-1][1] + " " + body)
            elif body:
                out.append(("quote", body))
            continue
        m = BULLET.match(line) or NUMBER.match(line)
        if m and not (para and BULLET.match(line) is None and NUMBER.match(line) is None):
            flush()
            ordered = bool(NUMBER.match(line))
            if out and out[-1][0] == "list" and out[-1][1][0] == ordered:
                out[-1][1][1].append(m.group(2))
            else:
                out.append(("list", (ordered, [m.group(2)])))
            continue
        if UNKNOWN.match(line):
            unknown.add(line.strip()[:40])
        para.append(line)
    flush()
    return out


INLINE = re.compile(r"\*\*(.+?)\*\*|__(.+?)__|\*(.+?)\*|_(.+?)_|\[([^\]]+)\]\([^)]*\)|`([^`]+)`")


def inline(text):
    """Markdown inline -> [(style, text)], style '' 'em' 'strong'."""
    runs, pos = [], 0
    for m in INLINE.finditer(text):
        if m.start() > pos:
            runs.append(("", text[pos:m.start()]))
        strong, strong2, em, em2, link, code = m.groups()
        if strong or strong2:
            runs.append(("strong", strong or strong2))
        elif em or em2:
            runs.append(("em", em or em2))
        else:
            runs.append(("", link or code))
        pos = m.end()
    if pos < len(text):
        runs.append(("", text[pos:]))
    return [(s, t.replace("\\*", "*").replace("\\_", "_")) for s, t in runs]


def read_project(folder):
    names = sorted((n for n in os.listdir(folder) if CHAPTER.match(n)),
                   key=lambda n: int(CHAPTER.match(n).group(1)))
    unknown = set()
    chapters = []
    for name in names:
        with open(os.path.join(folder, name), encoding="utf-8") as f:
            bl = blocks(f.read(), unknown)
        title = CHAPTER.match(name).group(2)
        if bl and bl[0][0] == "h" and bl[0][1][0] == 1:   # the file's own title
            title = bl[0][1][1]
            bl = bl[1:]
        chapters.append((title, bl))
    return chapters, sorted(unknown)


# --- ODT ------------------------------------------------------------------

def esc(text):
    return html.escape(text, quote=False)


def odt_text(text):
    """Escape for ODF: runs of spaces need <text:s/>."""
    return re.sub(r"  +", lambda m: f' <text:s text:c="{len(m.group()) - 1}"/>', esc(text))


def odt_runs(text):
    out = []
    for style, t in inline(text):
        t = odt_text(t)
        out.append(f'<text:span text:style-name="{style}">{t}</text:span>' if style else t)
    return "".join(out)


ODF_NS = ('xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
          'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
          'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
          'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" '
          'xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0" '
          'xmlns:dc="http://purl.org/dc/elements/1.1/" '
          'xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0" '
          'office:version="1.3"')

STYLES = f"""<?xml version="1.0" encoding="UTF-8"?>
<office:document-styles {ODF_NS}>
 <office:font-face-decls xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0">
  <style:font-face style:name="Serif" svg:font-family="'DejaVu Serif'" style:font-family-generic="roman"/>
 </office:font-face-decls>
 <office:styles>
  <style:default-style style:family="paragraph">
   <style:paragraph-properties fo:line-height="150%"/>
   <style:text-properties style:font-name="Serif" fo:font-size="12pt" fo:language="en" fo:country="US"/>
  </style:default-style>
  <style:style style:name="Standard" style:family="paragraph" style:class="text"/>
  <style:style style:name="Text_20_body" style:display-name="Text body" style:family="paragraph" style:parent-style-name="Standard" style:class="text">
   <style:paragraph-properties fo:text-indent="0.5in" fo:margin-top="0in" fo:margin-bottom="0in" fo:text-align="justify"/>
  </style:style>
  <style:style style:name="First_20_paragraph" style:display-name="First paragraph" style:family="paragraph" style:parent-style-name="Text_20_body" style:class="text">
   <style:paragraph-properties fo:text-indent="0in"/>
  </style:style>
  <style:style style:name="Heading_20_1" style:display-name="Heading 1" style:family="paragraph" style:parent-style-name="Standard" style:next-style-name="First_20_paragraph" style:default-outline-level="1" style:class="text">
   <style:paragraph-properties fo:break-before="page" fo:margin-top="1.5in" fo:margin-bottom="0.5in" fo:text-align="center" fo:keep-with-next="always"/>
   <style:text-properties fo:font-size="20pt" fo:font-weight="bold"/>
  </style:style>
  <style:style style:name="Heading_20_2" style:display-name="Heading 2" style:family="paragraph" style:parent-style-name="Standard" style:next-style-name="First_20_paragraph" style:default-outline-level="2" style:class="text">
   <style:paragraph-properties fo:margin-top="0.3in" fo:margin-bottom="0.15in" fo:keep-with-next="always"/>
   <style:text-properties fo:font-size="15pt" fo:font-weight="bold"/>
  </style:style>
  <style:style style:name="Heading_20_3" style:display-name="Heading 3" style:family="paragraph" style:parent-style-name="Heading_20_2" style:default-outline-level="3" style:class="text">
   <style:text-properties fo:font-size="13pt"/>
  </style:style>
  <style:style style:name="Scene_20_break" style:display-name="Scene break" style:family="paragraph" style:parent-style-name="Standard" style:next-style-name="First_20_paragraph" style:class="text">
   <style:paragraph-properties fo:text-align="center" fo:margin-top="0.15in" fo:margin-bottom="0.15in"/>
  </style:style>
  <style:style style:name="Quotations" style:family="paragraph" style:parent-style-name="Standard" style:class="html">
   <style:paragraph-properties fo:margin-left="0.5in" fo:margin-right="0.5in" fo:margin-top="0.1in" fo:margin-bottom="0.1in"/>
  </style:style>
  <style:style style:name="List_20_paragraph" style:display-name="List paragraph" style:family="paragraph" style:parent-style-name="Standard" style:class="list"/>
  <style:style style:name="Title" style:family="paragraph" style:parent-style-name="Standard" style:class="chapter">
   <style:paragraph-properties fo:margin-top="3in" fo:text-align="center"/>
   <style:text-properties fo:font-size="28pt" fo:font-weight="bold"/>
  </style:style>
  <style:style style:name="Subtitle" style:family="paragraph" style:parent-style-name="Standard" style:class="chapter">
   <style:paragraph-properties fo:margin-top="0.3in" fo:text-align="center"/>
   <style:text-properties fo:font-size="16pt"/>
  </style:style>
  <style:style style:name="em" style:family="text"><style:text-properties fo:font-style="italic"/></style:style>
  <style:style style:name="strong" style:family="text"><style:text-properties fo:font-weight="bold"/></style:style>
  <text:list-style style:name="Bullets">
   <text:list-level-style-bullet text:level="1" text:bullet-char="•">
    <style:list-level-properties text:list-level-position-and-space-mode="label-alignment">
     <style:list-level-label-alignment text:label-followed-by="listtab" text:list-tab-stop-position="0.5in" fo:text-indent="-0.25in" fo:margin-left="0.5in"/>
    </style:list-level-properties>
   </text:list-level-style-bullet>
  </text:list-style>
  <text:list-style style:name="Numbers">
   <text:list-level-style-number text:level="1" style:num-format="1" style:num-suffix=".">
    <style:list-level-properties text:list-level-position-and-space-mode="label-alignment">
     <style:list-level-label-alignment text:label-followed-by="listtab" text:list-tab-stop-position="0.5in" fo:text-indent="-0.25in" fo:margin-left="0.5in"/>
    </style:list-level-properties>
   </text:list-level-style-number>
  </text:list-style>
 </office:styles>
 <office:automatic-styles>
  <style:page-layout style:name="Page">
   <style:page-layout-properties fo:page-width="8.5in" fo:page-height="11in" fo:margin-top="1in" fo:margin-bottom="0.7in" fo:margin-left="1in" fo:margin-right="1in"/>
   <style:footer-style><style:header-footer-properties fo:min-height="0.3in" fo:margin-top="0.2in"/></style:footer-style>
  </style:page-layout>
  <style:style style:name="Footer" style:family="paragraph"><style:paragraph-properties fo:text-align="center"/></style:style>
 </office:automatic-styles>
 <office:master-styles>
  <style:master-page style:name="Standard" style:page-layout-name="Page">
   <style:footer><text:p text:style-name="Footer"><text:page-number text:select-page="current"/></text:p></style:footer>
  </style:master-page>
 </office:master-styles>
</office:document-styles>
"""


def odt_body(title, author, chapters):
    out = [f'<text:p text:style-name="Title">{odt_text(title)}</text:p>']
    if author:
        out.append(f'<text:p text:style-name="Subtitle">{odt_text(author)}</text:p>')
    for name, bl in chapters:
        out.append(f'<text:h text:style-name="Heading_20_1" text:outline-level="1">{odt_text(name)}</text:h>')
        first = True
        for kind, data in bl:
            if kind == "h":
                level = min(data[0], 3)
                out.append(f'<text:h text:style-name="Heading_20_{level}" text:outline-level="{level}">{odt_runs(data[1])}</text:h>')
                first = True
            elif kind == "p":
                style = "First_20_paragraph" if first else "Text_20_body"
                out.append(f'<text:p text:style-name="{style}">{odt_runs(data)}</text:p>')
                first = False
            elif kind == "quote":
                out.append(f'<text:p text:style-name="Quotations">{odt_runs(data)}</text:p>')
            elif kind == "list":
                ordered, items = data
                style = "Numbers" if ordered else "Bullets"
                li = "".join(f'<text:list-item><text:p text:style-name="List_20_paragraph">{odt_runs(i)}</text:p></text:list-item>'
                             for i in items)
                out.append(f'<text:list text:style-name="{style}">{li}</text:list>')
            elif kind == "break":
                out.append('<text:p text:style-name="Scene_20_break">*   *   *</text:p>')
                first = True
    return "\n".join(out)


def write_odt(path, title, author, chapters):
    content = (f'<?xml version="1.0" encoding="UTF-8"?>\n<office:document-content {ODF_NS}>\n'
               f'<office:body><office:text>\n{odt_body(title, author, chapters)}\n'
               '</office:text></office:body></office:document-content>\n')
    meta = (f'<?xml version="1.0" encoding="UTF-8"?>\n<office:document-meta {ODF_NS}><office:meta>'
            f'<dc:title>{esc(title)}</dc:title>' + (f'<meta:initial-creator>{esc(author)}</meta:initial-creator>' if author else "") +
            '<meta:generator>flickos-write spike</meta:generator></office:meta></office:document-meta>\n')
    manifest = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.3">\n'
                ' <manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.text"/>\n'
                ' <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>\n'
                ' <manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>\n'
                ' <manifest:file-entry manifest:full-path="meta.xml" manifest:media-type="text/xml"/>\n'
                '</manifest:manifest>\n')
    with zipfile.ZipFile(path, "w") as z:
        # the mimetype must be first and stored, not compressed
        z.writestr("mimetype", "application/vnd.oasis.opendocument.text", zipfile.ZIP_STORED)
        for name, data in (("content.xml", content), ("styles.xml", STYLES), ("meta.xml", meta),
                           ("META-INF/manifest.xml", manifest)):
            z.writestr(name, data, zipfile.ZIP_DEFLATED)


# --- EPUB 3 -----------------------------------------------------------------

def x_runs(text):
    return "".join(f"<{s}>{esc(t)}</{s}>" if s else esc(t) for s, t in inline(text))


def xhtml(title, body, lang):
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE html>\n'
            f'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{lang}" lang="{lang}">\n'
            f'<head><meta charset="UTF-8"/><title>{esc(title)}</title>'
            '<link rel="stylesheet" type="text/css" href="style.css"/></head>\n'
            f'<body>\n{body}\n</body>\n</html>\n')


CSS = """body { font-family: serif; line-height: 1.5; }
h1 { text-align: center; margin: 3em 0 1.5em; page-break-before: always; }
p { margin: 0; text-indent: 1.5em; text-align: justify; }
p.first, h1 + p, h2 + p, h3 + p, hr + p { text-indent: 0; }
hr { border: none; text-align: center; margin: 1em 0; }
hr::after { content: "*   *   *"; }
blockquote { margin: 0.8em 2em; }
blockquote p { text-indent: 0; }
.title { text-align: center; margin-top: 30%; font-size: 2em; font-weight: bold; text-indent: 0; }
.author { text-align: center; margin-top: 1em; text-indent: 0; }
"""


def epub_chapter(name, bl):
    out = [f"<section epub:type=\"chapter\" role=\"doc-chapter\"><h1>{esc(name)}</h1>"]
    for kind, data in bl:
        if kind == "h":
            level = min(data[0] + 1, 4)
            out.append(f"<h{level}>{x_runs(data[1])}</h{level}>")
        elif kind == "p":
            out.append(f"<p>{x_runs(data)}</p>")
        elif kind == "quote":
            out.append(f"<blockquote><p>{x_runs(data)}</p></blockquote>")
        elif kind == "list":
            tag = "ol" if data[0] else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{x_runs(i)}</li>" for i in data[1]) + f"</{tag}>")
        elif kind == "break":
            out.append('<hr class="scene" role="separator" aria-label="scene break"/>')
    out.append("</section>")
    return "\n".join(out)


def write_epub(path, title, author, chapters, lang="en"):
    book_id = f"urn:uuid:{uuid.uuid4()}"
    modified = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    files = {"title.xhtml": xhtml(title, f'<p class="title">{esc(title)}</p>' +
                                  (f'<p class="author">{esc(author)}</p>' if author else ""), lang)}
    for i, (name, bl) in enumerate(chapters, 1):
        files[f"chapter-{i:03}.xhtml"] = xhtml(name, epub_chapter(name, bl), lang)
    nav_items = "".join(f'<li><a href="chapter-{i:03}.xhtml">{esc(n)}</a></li>'
                        for i, (n, _) in enumerate(chapters, 1))
    files["nav.xhtml"] = xhtml("Contents", f'<nav epub:type="toc" id="toc" role="doc-toc"><h1>Contents</h1><ol>{nav_items}</ol></nav>', lang)
    manifest = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
                '<item id="css" href="style.css" media-type="text/css"/>',
                '<item id="title" href="title.xhtml" media-type="application/xhtml+xml"/>']
    spine = ['<itemref idref="title"/>']
    for i in range(1, len(chapters) + 1):
        manifest.append(f'<item id="c{i}" href="chapter-{i:03}.xhtml" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="c{i}"/>')
    opf = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           f'<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="{lang}">\n'
           ' <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
           f'  <dc:identifier id="bookid">{book_id}</dc:identifier>\n'
           f'  <dc:title>{esc(title)}</dc:title>\n  <dc:language>{lang}</dc:language>\n'
           + (f'  <dc:creator>{esc(author)}</dc:creator>\n' if author else "") +
           f'  <meta property="dcterms:modified">{modified}</meta>\n </metadata>\n'
           ' <manifest>\n  ' + "\n  ".join(manifest) + '\n </manifest>\n'
           ' <spine>\n  ' + "\n  ".join(spine) + '\n </spine>\n</package>\n')
    container = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                 '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
                 ' <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>\n'
                 '</container>\n')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/epub+zip", zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container, zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/content.opf", opf, zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/style.css", CSS, zipfile.ZIP_DEFLATED)
        for name, data in files.items():
            z.writestr(f"OEBPS/{name}", data, zipfile.ZIP_DEFLATED)


# --- DOCX and PDF through LibreOffice --------------------------------------

def convert(odt, fmt, output):
    """soffice --convert-to, with its own profile: with the default one, a
    LibreOffice the writer already has open takes the request and the
    command returns without writing anything."""
    with tempfile.TemporaryDirectory(prefix="write-export-") as tmp:
        profile = "file://" + os.path.join(tmp, "profile")
        cmd = ["soffice", f"-env:UserInstallation={profile}", "--headless",
               "--convert-to", {"docx": "docx:MS Word 2007 XML", "pdf": "pdf:writer_pdf_Export"}[fmt],
               "--outdir", tmp, odt]
        t0 = time.perf_counter()
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        made = os.path.join(tmp, os.path.splitext(os.path.basename(odt))[0] + "." + fmt)
        if not os.path.exists(made):
            sys.exit(f"soffice wrote nothing ({r.returncode}): {r.stdout}{r.stderr}")
        shutil.move(made, output)
        return time.perf_counter() - t0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("project")
    p.add_argument("--to", choices=("odt", "epub", "docx", "pdf"), required=True)
    p.add_argument("--output")
    p.add_argument("--title")
    p.add_argument("--author", default="")
    a = p.parse_args()
    folder = a.project.rstrip("/")
    title = a.title or os.path.basename(folder)
    output = a.output or f"{title}.{a.to}"
    t0 = time.perf_counter()
    chapters, unknown = read_project(folder)
    if not chapters:
        sys.exit(f"no chapters (NN Title.md) in {folder}")
    if a.to == "epub":
        write_epub(output, title, a.author, chapters)
    elif a.to == "odt":
        write_odt(output, title, a.author, chapters)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            odt = os.path.join(tmp, "book.odt")
            write_odt(odt, title, a.author, chapters)
            took = convert(odt, a.to, output)
            print(f"soffice: {took:.1f} s")
    words = sum(len(re.findall(r"\w+", d if isinstance(d, str) else str(d))) for _, bl in chapters for _, d in bl)
    print(f"{output}: {len(chapters)} chapters, about {words:,} words, {os.path.getsize(output):,} bytes,"
          f" {time.perf_counter() - t0:.2f} s")
    for line in unknown:
        print(f"  exported as plain text: {line}")


if __name__ == "__main__":
    main()
