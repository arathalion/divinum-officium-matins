#!/usr/bin/env python3
"""Write LaTeX for the two-column (Latin | English) print book from data/corpus.json.

Usage:
  python3 matins/tools/build_latex.py [GROUP ...] [-o NAME]

GROUP is a season id as used in build_epub.py (adv, nat, epi, quadp, quad,
pass, pasc, pent0, pent, m8, m9, m10, m11), "comm" for the Commons, or a
Proper of Saints month (s11a = 29-30 Nov, s12, s1 ... s11b). With no GROUP,
everything. Writes matins/book/NAME.tex; compile with
  latexmk -lualatex -cd matins/book/NAME.tex
The page design is in matins/book/matins.sty.
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import build_corpus as B  # noqa: E402
import build_epub as E  # noqa: E402
import layout  # noqa: E402
import credits  # noqa: E402

_TEX = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
        "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}


def tex(s):
    return "".join(_TEX.get(c, c) for c in (s or ""))


def stars(s):
    return tex(s).replace(" * ", r" \Star{} ")


def resp_item(item):
    if item[0] == "R":
        t = tex(item[1]) + (r" \Star{} " + tex(item[2]) if item[2] else "")
        return r"\begin{Resp}\Rsign " + t + r"\end{Resp}"
    return r"\begin{Resp}\Vsign " + stars(item[1]) + r"\end{Resp}"


def cell(kind, items, first_text):
    if kind == "resp":
        return "\n".join(resp_item(i) for i in items)
    if kind == "text":
        out = []
        for i, p in enumerate(items):
            out.append((r"\noindent " if first_text and i == 0 else "") + tex(p) + r"\par")
        return "\n".join(out)
    cmd = {"head": "LessonHead", "title": "LessonTitle", "cite": "Cite", "source": "Source",
           "rubric": "Rubric", "note": "Note", "tedeum": "TeDeum"}[kind]
    return "\n".join(f"\\{cmd}{{{tex(i)}}}" for i in items)


def row(la, en):
    return f"\\LA\n{la}\n\\switchcolumn\n\\EN\n{en}\n\\switchcolumn*\n"


def office(e, codes):
    out = []
    date = ""
    if e["kind"] == "Sancti":
        date = E.sancti_date(e["file"], "latin")
    title_la = tex(e["title_latin"])
    title_en = tex(e["title_english"])
    rank = tex(e.get("rank") or "")
    if date:
        out.append(f"\\par\\needspace{{10\\baselineskip}}\\addvspace{{1.2em}}"
                   f"{{\\centering\\small\\textsc{{{tex(date)}}} · \\textsc{{{tex(E.sancti_date(e['file'], 'english'))}}}\\par}}")
    out.append(f"\\Office{{{title_la}}}{{{title_en}}}{{{rank}}}")
    when = (tex(date) + " · ") if date else ""
    out.append(f"\\addcontentsline{{toc}}{{subsection}}{{{when}{title_la} \\textit{{— {title_en}}}}}")
    out.append(r"\begin{paracol}{2}")
    if e.get("see"):
        code = tex(E.stem(e["see"]))
        out.append(row(f"\\RefLine{{Cetera ut in {code}.}}", f"\\RefLine{{Otherwise as in {code}.}}"))
    for la, en in E.ref_lines(e, {}):
        strip = lambda h: re.sub(r"<[^>]+>", "", h)
        import html as _h
        out.append(row(f"\\RefLine{{{tex(_h.unescape(strip(la)))}}}", f"\\RefLine{{{tex(_h.unescape(strip(en)))}}}"))
    for les in e["lessons"]:
        note = les.get("note", "")
        rows = layout.lesson_rows(les["n"], les["latin"], les["english"],
                                  B.NOTE["latin"].get(note, note), B.NOTE["english"].get(note, note),
                                  untranslated=B.untranslated(les))
        # In print each language's responsory flows as one block; pairing its
        # lines would leave gaps wherever the English runs longer.
        merged = []
        for kind, la, en in rows:
            if kind == "resp" and merged and merged[-1][0] == "resp":
                merged[-1] = ("resp", merged[-1][1] + la, merged[-1][2] + en)
            else:
                merged.append((kind, list(la), list(en)))
        first = True
        for kind, la, en in merged:
            out.append(row(cell(kind, la, first), cell(kind, en, first)))
            first = kind != "text"
    out.append(r"\end{paracol}")
    return "\n".join(out)


def volume_tex(volume):
    if not volume:
        return ""
    la, en = VOLUMES[volume][:2]
    return (r"{\Large\rubr{" + tex(la) + r"}}\par\vspace{0.3em}"
            r"{\large\itshape " + tex(en) + r"}\par\vspace{2em}")


def credits_tex():
    out = [r"{\footnotesize\setlength{\parindent}{0pt}\setlength{\parskip}{0.35em}\raggedright"]
    for h, ps in credits.sections(print_book=True):
        out.append(f"\\par\\addvspace{{0.6em}}\\textsc{{{tex(h)}}}\\par")
        out.extend(tex(p) + r"\par" for p in ps)
    out.append("}")
    return "\n".join(out)


# The breviary's four parts: each holds its season's Proper of Time, the saints
# of every date that season can reach (so dates where two seasons meet are
# printed in both, as in the Breviarium Romanum of 1942), and Commons last.
# (Latin, English, Proper of Time groups, first and last date of the saints)
VOLUMES = {
    "winter": ("Pars Hiemalis", "Winter", ["adv", "nat", "epi", "quadp"], ("11-26", "03-13")),
}


def in_range(f, first, last):
    m = re.match(r"^(\d\d)-(\d\d)", E.stem(f))
    if not m:
        return False
    d = (int(m.group(1)), int(m.group(2)))
    a = tuple(int(x) for x in first.split("-"))
    b = tuple(int(x) for x in last.split("-"))
    return a <= d <= b if a <= b else (d >= a or d <= b)


def volume_saints(corpus, first, last):
    """Saints of a volume's date range, grouped by month in breviary order."""
    es = [e for e in corpus["entries"] if e["kind"] == "Sancti" and in_range(e["file"], first, last)]
    start = tuple(int(x) for x in first.split("-"))
    es.sort(key=lambda e: (B.sanctorale_sort(E.stem(e["file"]))[:2] < start,) + E.liturgical_sanctoral_key(e["file"])[1:])
    groups = []
    for e in es:
        m = B.sanctorale_sort(E.stem(e["file"]))[0]
        if not groups or groups[-1][0] != f"s{m}":
            groups.append((f"s{m}", f"Mensis {E.MONTHS_LA_NOM[m]}", E.MONTHS_EN[m], []))
        groups[-1][3].append(e)
    return groups
PART_ORDER = ["tempore", "sanctis", "commune"]


def season_of(date, scriptura):
    """The Proper of Time group a date belongs to, from the week's Scripture."""
    st = E.stem(scriptura)
    month = int(date[:2])
    if st.startswith("Pent") and 8 <= month <= 11:
        return f"m{month}"
    for gid, test, _, _ in E.TEMPORAL_GROUPS:
        if test(st):
            return gid
    return None


def slim_commons(selected, groups_wanted):
    """Keep only the Common lessons this volume's offices refer to, plus the
    Saturday-of-Our-Lady lessons for the Saturdays that fall in its seasons."""
    needed = {}
    for pid, _, _, groups in selected:
        if pid == "commune":
            continue
        for _, _, _, es in groups:
            for e in es:
                for r in e.get("refs", []):
                    if r["type"] == "commune" and r.get("file"):
                        needed.setdefault(r["file"], set()).add(r.get("section") or "")
                if e.get("see"):
                    needed.setdefault(e["see"], set())
    out = []
    for pid, pla, pen, groups in selected:
        if pid != "commune":
            out.append((pid, pla, pen, groups))
            continue
        new_groups = []
        for gid, gla, gen, es in groups:
            kept, seen_text = [], set()
            for e in es:
                want = set(needed.get(e["file"], set()))
                for date, scrip, secs in e.get("won_days", []):
                    if season_of(date, scrip) in groups_wanted:
                        want.update(secs)
                lessons = []
                for les in e["lessons"]:
                    if les["section"] not in want:
                        continue
                    key = B.body_words(les["latin"])
                    if e.get("won_days") and key in seen_text:  # same monthly lesson in another form
                        continue
                    seen_text.add(key)
                    lessons.append(les)
                if lessons:
                    kept.append(dict(e, lessons=lessons))
            if kept:
                new_groups.append((gid, gla, gen, kept))
        if new_groups:
            out.append((pid, pla, pen, new_groups))
    return out


def document(selected, title_note, volume=None):
    parts_out = []
    for pid, pla, pen, groups in selected:
        parts_out.append(f"\\PartTitle{{{tex(pla)}}}{{{tex(pen)}}}")
        parts_out.append(f"\\addcontentsline{{toc}}{{chapter}}{{{tex(pla)} \\textit{{— {tex(pen)}}}}}")
        for gid, gla, gen, es in groups:
            if len(groups) > 1 or pid != "commune":
                parts_out.append(f"\\SeasonTitle{{{tex(gla)}}}{{{tex(gen)}}}")
                parts_out.append(f"\\addcontentsline{{toc}}{{section}}{{{tex(gla)} \\textit{{— {tex(gen)}}}}}")
            for e in es:
                parts_out.append(office(e, {}))
    body = "\n\n".join(parts_out)
    return rf"""% Generated by matins/tools/build_latex.py from data/corpus.json — do not edit.
\documentclass[10pt,twoside,openright]{{book}}
\usepackage{{matins}}
\begin{{document}}
\BodySize
\frontmatter
\thispagestyle{{empty}}
\vspace*{{0.25\textheight}}
{{\centering
{{\Huge\rubr{{{tex(E.TITLE_LA)}}}}}\par\vspace{{0.4em}}
{{\large\itshape {tex(E.SUBTITLE_LA)}}}\par\vspace{{2em}}
{{\LARGE {tex(E.TITLE_EN)}}}\par\vspace{{0.4em}}
{{\large\itshape {tex(E.SUBTITLE_EN)}}}\par\vspace{{3em}}
{volume_tex(volume)}
{{\small {tex(title_note)}}}\par}}
\clearpage
\thispagestyle{{empty}}
{credits_tex()}
\mainmatter
{body}
\backmatter
\IndexOfOffices
\end{{document}}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("groups", nargs="*")
    ap.add_argument("-o", "--output", default=None)
    ap.add_argument("--volume", choices=sorted(VOLUMES), help="one of the breviary's parts")
    args = ap.parse_args()
    if args.volume:
        args.groups = VOLUMES[args.volume][2] + ["comm"]
        args.output = args.output or args.volume

    corpus = json.load(open(os.path.join(ROOT, "data", "corpus.json"), encoding="utf-8"))
    parts = E.build_structure(corpus)
    want = set(args.groups)
    selected = []
    for pid, pla, pen, groups in parts:
        gs = [g for g in groups if not want or g[0] in want or pid in want]
        if gs:
            selected.append((pid, pla, pen, gs))
    if not selected:
        sys.exit(f"no such group: {', '.join(args.groups)}")
    if args.volume:
        first, last = VOLUMES[args.volume][3]
        selected = [p for p in selected if p[0] != "sanctis"]
        sp = next(p for p in parts if p[0] == "sanctis")
        selected.append(("sanctis", sp[1], sp[2], volume_saints(corpus, first, last)))
        selected.sort(key=lambda p: PART_ORDER.index(p[0]))
        selected = slim_commons(selected, set(args.groups))
    name = args.output or ("matins" if not want else "-".join(args.groups))
    note = "Sample: " + ", ".join(g[2] for _, _, _, gs in selected for g in gs) if want and not args.volume else ""
    path = os.path.join(ROOT, "book", name + ".tex")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(document(selected, note, args.volume))
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
