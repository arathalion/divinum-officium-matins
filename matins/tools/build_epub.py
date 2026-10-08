#!/usr/bin/env python3
"""Build a bilingual EPUB of the Matins readings from data/corpus.json.

Latin and English stand side by side, paragraph by paragraph, and stack on
narrow screens. Order follows the breviary: Proper of Time, Common of the
Saints, Proper of Saints (from 29 November). No third-party packages needed.

Usage: python3 matins/tools/build_epub.py [output.epub]
"""

import datetime
import html
import json
import os
import re
import sys
import uuid
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import build_corpus as B  # noqa: E402
import credits  # noqa: E402
import lessons as L  # noqa: E402
import layout  # noqa: E402

TITLE_LA = "Lectiones ad Matutinum"
TITLE_EN = "The Lessons of Matins"
SUBTITLE_LA = "ex Breviario Romano anni MCMLIV"
SUBTITLE_EN = "from the Roman Breviary of 1954, in Latin and English"
BOOK_ID = "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, "matins-readings-divino-afflatu-1954"))

MONTHS_LA = ["", "Januarii", "Februarii", "Martii", "Aprilis", "Maii", "Junii", "Julii", "Augusti",
             "Septembris", "Octobris", "Novembris", "Decembris"]
MONTHS_LA_NOM = ["", "Januarius", "Februarius", "Martius", "Aprilis", "Majus", "Junius", "Julius",
                 "Augustus", "September", "October", "November", "December"]
MONTHS_EN = B.MONTH_EN

TEMPORAL_GROUPS = [
    # (id, test on file stem, Latin, English)
    ("adv", lambda s: s.startswith("Adv"), "Tempus Adventus", "Advent"),
    ("nat", lambda s: s.startswith("Nat"), "Tempus Nativitatis", "Christmastide"),
    ("epi", lambda s: s.startswith("Epi"), "Tempus post Epiphaniam", "Time after Epiphany"),
    ("quadp", lambda s: s.startswith("Quadp"), "Tempus Septuagesimæ", "Septuagesima"),
    ("quad", lambda s: re.match(r"Quad[1-4]-", s), "Tempus Quadragesimæ", "Lent"),
    ("pass", lambda s: re.match(r"Quad[56]-", s), "Tempus Passionis", "Passiontide"),
    ("pasc", lambda s: re.match(r"Pasc[0-6]-", s), "Tempus Paschale", "Paschaltide"),
    ("pent0", lambda s: s.startswith("Pasc7"), "Octava Pentecostes", "The Octave of Pentecost"),
    ("pent", lambda s: s.startswith("Pent"), "Tempus post Pentecosten", "Time after Pentecost"),
] + [
    (f"m{m}", (lambda mm: lambda s: s.startswith(mm))(f"{m:02d}"),
     f"Dominicæ et Feriæ mensis {MONTHS_LA[m]}", f"Sundays and Ferias of {MONTHS_EN[m]}")
    for m in (8, 9, 10, 11)
]

CSS = """
@charset "utf-8";
body { font-family: serif; line-height: 1.4; margin: 0 1.5%; }
h1, h2, h3 { font-weight: normal; text-align: center; margin: 0.6em 0 0.3em; }
h1 { font-size: 1.6em; }
h2 { font-size: 1.3em; }
.sub { display: block; font-size: 0.75em; font-style: italic; margin-top: 0.2em; }
.date { text-align: center; font-variant: small-caps; letter-spacing: 0.05em; margin: 0.8em 0 0; }
.rank { text-align: center; font-style: italic; font-size: 0.85em; margin: 0 0 0.8em; }
p { margin: 0 0 0.5em; text-indent: 0; text-align: justify; -webkit-hyphens: auto; hyphens: auto; }
.pair { display: table; width: 100%; table-layout: fixed; }
.pair > .la, .pair > .en { display: table-cell; width: 50%; vertical-align: top; }
.pair > .la { padding-right: 0.7em; }
.pair > .en { padding-left: 0.7em; border-left: 1px solid #c8b8b8; }
.head { text-align: center; font-variant: small-caps; letter-spacing: 0.06em; color: #9b1c1c; margin-top: 1.1em; }
.title { text-align: center; font-style: italic; }
.cite, .source { text-align: center; font-size: 0.85em; color: #9b1c1c; }
.rubric, .note { font-size: 0.85em; font-style: italic; color: #9b1c1c; }
.rv, .star { color: #9b1c1c; font-weight: bold; }
.resp p { text-align: left; }
.refs { margin: 0.4em 0 0.6em; font-size: 0.9em; font-style: italic; }
.tedeum { text-align: center; font-style: italic; color: #9b1c1c; }
.toc li { list-style: none; margin: 0.15em 0; }
.back { text-align: right; font-size: 0.8em; font-style: italic; margin: 0; }
h2 a { text-decoration: none; }
.toc ol { padding-left: 1.2em; }
.front p { text-align: left; }
.front h2 { font-size: 1.05em; font-variant: small-caps; letter-spacing: 0.04em; margin-top: 1em; }
a { color: inherit; text-decoration: underline; text-decoration-color: #c8b8b8; }
@media (max-width: 34em) {
  .pair, .pair > .la, .pair > .en { display: block; width: auto; padding: 0; border: 0; }
  .pair > .en { margin-top: 0.15em; color: #3a3a3a; }
}
"""

XHTML = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="la" lang="la">
<head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/><title>{title}</title><link rel="stylesheet" type="text/css" href="../style.css"/></head>
<body>
{body}
</body>
</html>
"""


def esc(s):
    return html.escape(s or "", quote=False)


def stem(f):
    return os.path.basename(B.stem(f))


def fname(f):
    return "e-" + re.sub(r"[^A-Za-z0-9-]", "_", stem(f)) + ".xhtml"


# ------------------------------------------------------------------ rendering

def resp_html(item, lang):
    if item[0] == "R":
        t = esc(item[1]) + (f' <span class="star">*</span> {esc(item[2])}' if item[2] else "")
        return f'<p><span class="rv">R.</span> {t}</p>'
    t = esc(item[1]).replace(" * ", ' <span class="star">*</span> ')
    return f'<p><span class="rv">V.</span> {t}</p>'


def cell(kind, items, lang):
    if kind == "resp":
        return "".join(resp_html(i, lang) for i in items)
    if kind == "text":
        return "".join(f"<p>{esc(i)}</p>" for i in items)
    cls = {"head": "head", "title": "title", "cite": "cite", "source": "source",
           "rubric": "rubric", "note": "note", "tedeum": "tedeum"}[kind]
    return "".join(f'<p class="{cls}">{esc(i)}</p>' for i in items)


def pair(la_html, en_html, cls=""):
    return (f'<div class="pair{(" " + cls) if cls else ""}">'
            f'<div class="la" lang="la" xml:lang="la">{la_html}</div>'
            f'<div class="en" lang="en" xml:lang="en">{en_html}</div></div>')


def lesson_html(les):
    note = les.get("note", "")
    rows = layout.lesson_rows(
        les["n"], les["latin"], les["english"],
        B.NOTE["latin"].get(note, note), B.NOTE["english"].get(note, note),
        untranslated=B.untranslated(les))
    out = []
    for kind, la, en in rows:
        out.append(pair(cell(kind, la, "latin"), cell(kind, en, "english"),
                        "resp" if kind == "resp" else ""))
    return "\n".join(out)


def ref_lines(e, links):
    """Pairs of (latin, english) reference lines, as in the text files."""
    import collections
    groups = collections.OrderedDict()
    for r in e.get("refs", []):
        loco = re.search(r" in (\d+) loco$", r.get("section") or "")
        groups.setdefault((r["type"], r.get("file", ""), loco.group(1) if loco else ""), []).append(r)
    rows = []
    for (t, f, loco), rs in groups.items():
        for a, b in B.ranges([r["n"] for r in rs]):
            line = []
            for lang in ("latin", "english"):
                title = rs[0].get("title_" + lang) or rs[0].get("title_latin") or ""
                if lang == "latin":
                    title = re.sub(r"^Commune\b", "Commúni", title)
                code = stem(f) if f else ""
                what = esc(B.REF_TEXT[lang][t].format(title=title, code="@@CODE@@"))
                if f and f in links:
                    what = what.replace("@@CODE@@", f'<a href="{links[f]}">{esc(code)}</a>')
                else:
                    what = what.replace("@@CODE@@", esc(code))
                if loco:
                    what += ", " + esc(B.NOTE[lang][f"loco{loco}"])
                word = ("Lectiones" if lang == "latin" else "Lessons") if a != b else \
                       ("Lectio" if lang == "latin" else "Lesson")
                line.append(f"<p>{word} {B.roman_range(a, b)}: {what}.</p>")
            rows.append(line)
    return rows


def sancti_date(f, lang):
    m = re.match(r"^(\d\d)-(\d\d)", stem(f))
    if not m:
        return ""
    mm, dd = int(m.group(1)), int(m.group(2))
    return f"Die {dd} {MONTHS_LA[mm]}" if lang == "latin" else f"{dd} {MONTHS_EN[mm]}"


def entry_page(e, links):
    parts = []
    if e["kind"] == "Sancti":
        parts.append(pair(f'<p class="date">{esc(sancti_date(e["file"], "latin"))}</p>',
                          f'<p class="date">{esc(sancti_date(e["file"], "english"))}</p>'))
    parts.append(f'<h2 id="top">{esc(e["title_latin"])}'
                 f'<span class="sub" lang="en" xml:lang="en">{esc(e["title_english"])}</span></h2>')
    if e.get("rank"):
        parts.append(f'<p class="rank">{esc(e["rank"])}</p>')
    if e.get("see"):
        code = stem(e["see"])
        link = f'<a href="{links[e["see"]]}">{esc(code)}</a>' if e["see"] in links else esc(code)
        parts.append(pair(f"<p>Cetera ut in {link}.</p>", f"<p>Otherwise as in {link}.</p>", "refs"))
    for la, en in ref_lines(e, links):
        parts.append(pair(la, en, "refs"))
    for les in e["lessons"]:
        parts.append(f'<div class="lesson">{lesson_html(les)}</div>')
    return XHTML.format(title=esc(e["title_latin"]), body="\n".join(parts))


# ------------------------------------------------------------------ structure

def liturgical_sanctoral_key(f):
    mm, dd, rest = B.sanctorale_sort(stem(f))
    return ((mm, dd) < (11, 29), mm, dd, rest)


def build_structure(corpus):
    entries = corpus["entries"]
    temporal = sorted((e for e in entries if e["kind"] == "Tempora"), key=lambda e: B.temporale_sort(stem(e["file"])))
    commons = sorted((e for e in entries if e["kind"] == "Commune"), key=lambda e: B.commune_sort(stem(e["file"])))
    saints = sorted((e for e in entries if e["kind"] == "Sancti"), key=lambda e: liturgical_sanctoral_key(e["file"]))

    parts = []
    groups = []
    for gid, test, la, en in TEMPORAL_GROUPS:
        es = [e for e in temporal if test(stem(e["file"])) and not any(e in g[3] for g in groups)]
        if es:
            groups.append((gid, la, en, es))
    leftover = [e for e in temporal if not any(e in g[3] for g in groups)]
    if leftover:
        groups.append(("tmisc", "Alia", "Other", leftover))
    parts.append(("tempore", "Proprium de Tempore", "Proper of Time", groups))

    parts.append(("commune", "Commune Sanctorum", "Common of the Saints",
                  [("comm", "Commune Sanctorum", "Common of the Saints", commons)]))

    sgroups = []
    order = [12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    for m in [11] + order:
        if m == 11 and sgroups:
            es = [e for e in saints if B.sanctorale_sort(stem(e["file"]))[0] == 11
                  and B.sanctorale_sort(stem(e["file"]))[1] < 29]
            gid = "s11b"
        elif m == 11:
            es = [e for e in saints if B.sanctorale_sort(stem(e["file"]))[0] == 11
                  and B.sanctorale_sort(stem(e["file"]))[1] >= 29]
            gid = "s11a"
        else:
            es = [e for e in saints if B.sanctorale_sort(stem(e["file"]))[0] == m]
            gid = f"s{m}"
        if es:
            days = {"s11a": " (29–30)", "s11b": " (1–28)"}.get(gid, "")
            sgroups.append((gid, f"Mensis {MONTHS_LA_NOM[m]}{days}", f"{MONTHS_EN[m]}{days}", es))
    odd = [e for e in saints if B.sanctorale_sort(stem(e["file"]))[0] == 99]
    if odd:
        sgroups.append(("sx", "Alia", "Other", odd))
    parts.append(("sanctis", "Proprium de Sanctis", "Proper of Saints", sgroups))
    return parts


BACK = '<p class="back"><a href="contents.xhtml">Index · Contents</a></p>'


def entry_list(es):
    return "".join(
        f'<li><a href="{fname(e["file"])}">{esc(e["title_latin"])}</a>'
        f' <span lang="en" xml:lang="en">— {esc(e["title_english"])}</span></li>' for e in es)


def section_list(groups):
    """Links to a part's seasons or months; for a one-section part, its offices."""
    if len(groups) == 1:
        return f'<ol class="toc">{entry_list(groups[0][3])}</ol>'
    return '<ol class="toc">' + "".join(
        f'<li><a href="group-{gid}.xhtml">{esc(gla)}</a> <span lang="en" xml:lang="en">— {esc(gen)}</span></li>'
        for gid, gla, gen, es in groups) + "</ol>"


def group_page(title_la, title_en, es):
    body = (BACK + f'<h1>{esc(title_la)}<span class="sub" lang="en" xml:lang="en">{esc(title_en)}</span></h1>'
            f'<ol class="toc">{entry_list(es)}</ol>')
    return XHTML.format(title=esc(title_la), body=body)


def part_page(title_la, title_en, groups):
    body = (BACK + f'<div style="margin-top:12%"><h1>{esc(title_la)}'
            f'<span class="sub" lang="en" xml:lang="en">{esc(title_en)}</span></h1></div>'
            + section_list(groups))
    return XHTML.format(title=esc(title_la), body=body)


def contents_page(parts):
    body = ['<h1>Index<span class="sub" lang="en" xml:lang="en">Contents</span></h1>']
    for pid, pla, pen, groups in parts:
        body.append(f'<h2><a href="part-{pid}.xhtml">{esc(pla)}</a>'
                    f'<span class="sub" lang="en" xml:lang="en">{esc(pen)}</span></h2>')
        body.append(section_list(groups))
    body.append('<h2><a href="about.xhtml">About this edition</a></h2>')
    body.append('<h2><a href="credits.xhtml">Credits</a></h2>')
    body.append('<h2><a href="colophon.xhtml">Colophon</a></h2>')
    return XHTML.format(title="Contents", body="\n".join(body))


def front_pages(corpus):
    title = (f'<div style="margin-top:25%"><h1>{esc(TITLE_LA)}<span class="sub">{esc(SUBTITLE_LA)}</span></h1>'
             f'<h2 lang="en" xml:lang="en">{esc(TITLE_EN)}<span class="sub">{esc(SUBTITLE_EN)}</span></h2></div>')
    about = f"""<div class="front" lang="en" xml:lang="en">
<h1>About this edition</h1>
<p>This book gives every lesson read at Matins in the Roman Breviary as it stood in 1954, with its
responsory, in Latin and English: the Proper of Time, the Common of the Saints, and the Proper of
Saints, in the order of the breviary.</p>
<p>The texts and their arrangement come from the Divinum Officium project
(divinumofficium.com). Its program was run for every day from 1950 to 2100 under the rubrics of
Divino Afflatu as they stood in 1954, and each lesson it read was traced back to the office it
belongs to. A saint's day therefore gives that saint's own lessons, and says where the others are
read from: the Scripture of the day (in the Proper of Time), a Common, or a commemorated feast.</p>
<p>Scripture is printed without verse numbers. Responsories are given as said, with the
<i>Gloria Patri</i> where it occurs; where the <i>Te Deum</i> follows a lesson, it is noted.
The English is that of Divinum Officium: the Douay-Rheims for Scripture, and for the other lessons
chiefly the translation of the Marquess of Bute. Where no English is available, the Latin is given
and the gap is noted.</p>
<p>Built {datetime.date.today().isoformat()} from {corpus["harvest_days"]:,} days of the calendar.</p>
</div>"""
    colophon = """<div class="front" lang="en" xml:lang="en">
<h1>Colophon</h1>
<p>Texts from Divinum Officium (github.com/DivinumOfficium/divinum-officium), distributed under the
MIT License:</p>
<p>Copyright (c) 2026 Divinum Officium</p>
<p>Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
associated documentation files (the "Software"), to deal in the Software without restriction,
including without limitation the rights to use, copy, modify, merge, publish, distribute,
sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:</p>
<p>The above copyright notice and this permission notice shall be included in all copies or
substantial portions of the Software.</p>
<p>THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT
NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES
OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.</p>
</div>"""
    credits_body = '<div class="front" lang="en" xml:lang="en"><h1>Credits</h1>' + "".join(
        f"<h2>{esc(h)}</h2>" + "".join(f"<p>{esc(p)}</p>" for p in ps)
        for h, ps in credits.sections(print_book=False)) + "</div>"
    return [("title.xhtml", TITLE_LA, XHTML.format(title=esc(TITLE_LA), body=title)),
            ("about.xhtml", "About this edition", XHTML.format(title="About this edition", body=about))], \
        [("credits.xhtml", "Credits", XHTML.format(title="Credits", body=credits_body)),
         ("colophon.xhtml", "Colophon", XHTML.format(title="Colophon", body=colophon))]


# ------------------------------------------------------------------ package

def build(out_path):
    corpus = json.load(open(os.path.join(ROOT, "data", "corpus.json"), encoding="utf-8"))
    parts = build_structure(corpus)
    links = {e["file"]: fname(e["file"]) for e in corpus["entries"]}

    files = []   # (href, xhtml)
    spine = []   # hrefs
    nav = []     # nested: (label, href, children)

    front, colophon = front_pages(corpus)
    front.append(("contents.xhtml", "Contents", contents_page(parts)))
    for href, label, doc in front:
        files.append((href, doc))
        spine.append(href)
        nav.append((label, f"text/{href}", []))

    for pid, pla, pen, groups in parts:
        phref = f"part-{pid}.xhtml"
        files.append((phref, part_page(pla, pen, groups)))
        spine.append(phref)
        pnav = []
        for gid, gla, gen, es in groups:
            ghref = f"group-{gid}.xhtml"
            if len(groups) > 1:
                files.append((ghref, group_page(gla, gen, es)))
                spine.append(ghref)
            enav = []
            for e in es:
                href = fname(e["file"])
                files.append((href, entry_page(e, links)))
                spine.append(href)
                enav.append((f'{e["title_latin"]} — {e["title_english"]}', f"text/{href}", []))
            if len(groups) > 1:
                pnav.append((f"{gla} — {gen}", f"text/{ghref}", enav))
            else:
                pnav.extend(enav)
        nav.append((f"{pla} — {pen}", f"text/{phref}", pnav))

    for href, label, doc in colophon:  # back matter: credits, colophon
        files.append((href, doc))
        spine.append(href)
        nav.append((label, f"text/{href}", []))

    # Navigation documents.
    def nav_ol_root(items):
        return "<ol>" + "".join(
            f'<li><a href="{h}">{esc(l)}</a>{nav_ol_root(c) if c else ""}</li>' for l, h, c in items) + "</ol>"

    nav_doc = ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
               '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en" xml:lang="en">'
               '<head><meta charset="utf-8"/><title>Contents</title><link rel="stylesheet" type="text/css" href="style.css"/></head>'
               f'<body><nav epub:type="toc" id="toc" class="toc"><h1>Contents</h1>{nav_ol_root(nav)}</nav>'
               '<nav epub:type="landmarks" id="landmarks" hidden="hidden"><ol>'
               '<li><a epub:type="toc" href="text/contents.xhtml">Contents</a></li>'
               '<li><a epub:type="bodymatter" href="text/part-tempore.xhtml">Proprium de Tempore</a></li>'
               '</ol></nav></body></html>')

    counter = [0]

    def ncx_points(items):
        out = []
        for l, h, c in items:
            counter[0] += 1
            out.append(f'<navPoint id="np{counter[0]}" playOrder="{counter[0]}"><navLabel><text>{esc(l)}</text></navLabel>'
                       f'<content src="{h}"/>{ncx_points(c)}</navPoint>')
        return "".join(out)

    ncx_doc = ('<?xml version="1.0" encoding="utf-8"?>\n'
               '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1"><head>'
               f'<meta name="dtb:uid" content="{BOOK_ID}"/><meta name="dtb:depth" content="3"/></head>'
               f'<docTitle><text>{esc(TITLE_LA)}</text></docTitle><navMap>{ncx_points(nav)}</navMap></ncx>')

    modified = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
                '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
                '<item id="css" href="style.css" media-type="text/css"/>']
    ids = {}
    for i, (href, _) in enumerate(files):
        ids[href] = f"x{i}"
        manifest.append(f'<item id="x{i}" href="text/{href}" media-type="application/xhtml+xml"/>')
    spine_xml = "".join(f'<itemref idref="{ids[h]}"/>' for h in spine)
    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="en">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="bookid">{BOOK_ID}</dc:identifier>
<dc:title>{esc(TITLE_LA)} · {esc(TITLE_EN)}</dc:title>
<dc:language>la</dc:language>
<dc:language>en</dc:language>
<dc:creator>Divinum Officium (texts)</dc:creator>
<dc:description>{esc(SUBTITLE_EN)}</dc:description>
<meta property="dcterms:modified">{modified}</meta>
</metadata>
<manifest>
{chr(10).join(manifest)}
</manifest>
<spine toc="ncx">{spine_xml}</spine>
</package>
"""
    container = ('<?xml version="1.0" encoding="utf-8"?>\n'
                 '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                 '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
                 '</rootfiles></container>')

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tmp = out_path + ".part"
    with zipfile.ZipFile(tmp, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/content.opf", opf, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/nav.xhtml", nav_doc, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/toc.ncx", ncx_doc, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/style.css", CSS, compress_type=zipfile.ZIP_DEFLATED)
        for href, doc in files:
            z.writestr(f"OEBPS/text/{href}", doc, compress_type=zipfile.ZIP_DEFLATED)
    os.replace(tmp, out_path)
    return len(files)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "output", "Matins-Readings-1954.epub")
    n = build(out)
    print(f"wrote {out} ({n} pages, {os.path.getsize(out) / 1e6:.1f} MB)")
