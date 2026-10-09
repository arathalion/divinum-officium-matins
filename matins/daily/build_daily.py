#!/usr/bin/env python3
"""Render each day's Matins as a ready-to-send email and a bilingual web page.

For every date in the window, runs the engine (tools/harvest_day.pl) for the
calendar and language, and writes OUT/<calendar>/<lang>/<YYYY-MM-DD>.json:

  {date, calendar, lang, title: {latin, local}, rank,
   lessons: [{number, latin, translation}],   # structured, for the public API
   email: {subject, preheader, html, text},   # vernacular only, links to the page
   page:  {title, html}}                       # Latin and vernacular side by side

The email HTML carries placeholders the sending Worker fills per subscriber:
{{page_url}}, {{unsubscribe_url}}, {{preferences_url}}. Also writes
OUT/manifest.json listing calendars, languages and the dates available.

Usage:
  python3 matins/daily/build_daily.py --start 2026-10-08 --days 60 --out DIR
"""

import argparse
import concurrent.futures as cf
import datetime
import html
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MATINS = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(MATINS, "tools"))
import lessons as L  # noqa: E402
import layout  # noqa: E402
import titles  # noqa: E402
from build_corpus import normalise_rank  # noqa: E402

HARVEST = os.path.join(MATINS, "tools", "harvest_day.pl")

# Calendars offered: slug -> (Divinum Officium version, name shown to readers)
CALENDARS = {
    "1570": ("Tridentine - 1570", "Roman Breviary, 1570 (St Pius V)"),
    "1888": ("Tridentine - 1888", "Roman Breviary, 1888"),
    "1906": ("Tridentine - 1906", "Roman Breviary, 1906"),
    "1939": ("Divino Afflatu - 1939", "Roman Breviary, 1939 (Divino Afflatu)"),
    "1954": ("Divino Afflatu - 1954", "Roman Breviary, 1954 (Divino Afflatu)"),
    "1955": ("Reduced - 1955", "Roman Breviary, 1955 (simplified rubrics)"),
    "1960": ("Rubrics 1960 - 1960", "Roman Breviary, 1960"),
    "1960-usa": ("Rubrics 1960 - 2020 USA", "Roman Breviary, 1960, with the current US calendar"),
    "monastic-1617": ("Monastic Tridentinum 1617", "Monastic Breviary, 1617"),
    "monastic-1930": ("Monastic Divino 1930", "Monastic Breviary, 1930"),
    "monastic-1963": ("Monastic - 1963", "Monastic Breviary, 1963"),
    "monastic-1963-barroux": ("Monastic - 1963 - Barroux", "Monastic Breviary, 1963 (Le Barroux)"),
    "cistercian-1951": ("Monastic Tridentinum Cisterciensis 1951", "Cistercian Breviary, 1951"),
    "cistercian-altovadensis": ("Monastic Tridentinum Cisterciensis Altovadensis", "Cistercian Breviary (Hohenfurth / Vyšší Brod)"),
    "dominican-1962": ("Ordo Praedicatorum - 1962", "Dominican Breviary, 1962"),
}
# Languages offered: code -> (Divinum Officium folder, name in that language)
LANGUAGES = {
    "en": ("English", "English"),
}

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["", "January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]
RED = "#9b1c1c"


def esc(s):
    return html.escape(s or "", quote=False)


# ---------------------------------------------------------------- titles

def load_corpus_titles():
    """Titles and ranks for 1954 from the corpus (cleaner than the engine's)."""
    path = os.path.join(MATINS, "data", "corpus.json")
    try:
        corpus = json.load(open(path, encoding="utf-8"))
    except OSError:
        return {}
    return {e["file"]: e for e in corpus["entries"]}


def day_titles(day, corpus_titles, lang_code, calendar):
    # The corpus (built for 1954) has the cleanest titles; other calendars use
    # the engine's own, with English names for temporal days.
    e = corpus_titles.get(day.get("winner") or "") if calendar == "1954" else None
    if e:
        la, local, rank = e["title_latin"], e["title_english"], e.get("rank", "")
    else:
        fields = [f.strip() for f in (day.get("rank_field") or "").split("\n")[0].split(";;")]
        la = (day.get("title_latin") or (fields[0] if fields and fields[0] else "")
              or (day.get("dayname") or ["", ""])[1].split("\t")[0]).strip()
        local = (day.get("title_english") or la).strip()
        rank = normalise_rank(fields[1], fields[2] if len(fields) > 2 else "") if len(fields) > 1 else ""
    if lang_code == "en":
        local = titles.english_title(la, local)
        if local == la:
            local = titles.english_tempora(la)
    return la, local, rank


# ---------------------------------------------------------------- email

# Headings for monastic one-lesson forms, by kind: (Latin, English)
SINGLE = {"brevis": ("Lectio brevis", "Short lesson"), "unica": ("Lectio unica", "Lesson")}


def email_lesson(n, les, kind=None):
    head = SINGLE[kind][1] if kind in SINGLE else f"Lesson {L.ROMAN[n] if n < len(L.ROMAN) else n}"
    out = [f'<p style="margin:26px 0 4px;text-align:center;color:{RED};font-variant:small-caps;'
           f'letter-spacing:.06em;font-size:15px">{head}</p>']
    for r in les["rubric"]:
        out.append(f'<p style="margin:0 0 6px;text-align:center;font-style:italic;font-size:14px;color:{RED}">{esc(r)}</p>')
    for b in les["blocks"]:
        if b["title"]:
            out.append(f'<p style="margin:0 0 2px;text-align:center;font-style:italic">{esc(b["title"])}</p>')
        if b["cite"]:
            out.append(f'<p style="margin:0 0 8px;text-align:center;font-size:14px;color:{RED}">{esc(b["cite"])}</p>')
        if b["source"]:
            out.append(f'<p style="margin:0 0 8px;text-align:center;font-size:14px;font-style:italic;color:#555">{esc(b["source"])}</p>')
        paras = (L.verses_as_prose(b["verses"]) if b["verses"] else []) + b["paras"]
        for p in paras:
            out.append(f'<p style="margin:0 0 10px">{esc(p)}</p>')
    for item in les["responsory"]:
        if item[0] == "R":
            t = esc(item[1]) + (f' <span style="color:{RED}">*</span> {esc(item[2])}' if item[2] else "")
            sign = "℟. br." if len(item) > 3 else "℟."
        else:
            t = esc(item[1]).replace(" * ", f' <span style="color:{RED}">*</span> ')
            sign = "℣."
        out.append(f'<p style="margin:0 0 4px;padding-left:1.4em;text-indent:-1.4em">'
                   f'<span style="color:{RED};font-weight:bold">{sign}</span> {t}</p>')
    if les["tedeum"]:
        out.append(f'<p style="margin:10px 0 0;text-align:center;font-style:italic;color:{RED}">Te Deum</p>')
    return "\n".join(out)


def email_text_lesson(n, les, kind=None):
    t = L.to_text(n, les, "english")
    return t.replace("Lesson I", SINGLE[kind][1], 1) if kind in SINGLE else t


def commemorations(day, lang_code):
    """[(latin, local)] for the offices commemorated today."""
    out = []
    for c in day.get("commemorations") or []:
        la, local = c["latin"].strip(), (c.get("local") or c["latin"]).strip()
        if lang_code == "en":
            local = titles.english_title(la, local)
            if local == la:
                local = titles.english_tempora(la)
        out.append((la, local))
    return out


def comm_line(items, which):
    """"Commemoration: X" / "Commemorations: X; Y" in Latin (0) or the vernacular (1)."""
    if not items:
        return ""
    names = "; ".join(i[which] for i in items)
    if which == 0:
        return ("Commemoratio: " if len(items) == 1 else "Commemorationes: ") + names
    return ("Commemoration: " if len(items) == 1 else "Commemorations: ") + names


def render_email(day, la_title, title, rank, date, cal_name, vernacular, comms=()):
    when = f"{WEEKDAYS[date.weekday()]}, {date.day} {MONTHS[date.month]} {date.year}"
    subject = f"Matins for {WEEKDAYS[date.weekday()]} {date.day} {MONTHS[date.month]}: {title}"
    first = next((p for les in vernacular for b in les[1]["blocks"] for p in b["paras"] + [v[1] for v in b["verses"]]), "")
    preheader = (first[:140] + "…") if len(first) > 140 else first
    body = "\n".join(email_lesson(n, les, brevis) for n, les, brevis in vernacular)
    link = f'<a href="{{{{page_url}}}}" style="color:{RED}">Read in Latin and English</a>'
    html_doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light only"><title>{esc(subject)}</title></head>
<body style="margin:0;padding:0;background:#f6f2ea">
<div style="display:none;max-height:0;overflow:hidden">{esc(preheader)}</div>
<div style="max-width:620px;margin:0 auto;padding:28px 20px;background:#fffdf8;font-family:Georgia,'Times New Roman',serif;font-size:17px;line-height:1.55;color:#222">
<p style="margin:0;font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:{RED}">Matins · {esc(when)}</p>
<h1 style="margin:8px 0 4px;font-weight:normal;font-size:26px;line-height:1.25">{esc(title)}</h1>
<p style="margin:0 0 6px;font-style:italic;color:#555;font-size:15px">{esc(la_title)}{(" · " + esc(rank)) if rank else ""}</p>
{f'<p style="margin:0 0 6px;color:#555;font-size:15px">{esc(comm_line(comms, 1))}</p>' if comms else ""}
<p style="margin:0 0 6px;font-size:15px">{link}</p>
{body}
<hr style="border:none;border-top:1px solid #e3d6c4;margin:32px 0 16px">
<p style="margin:0 0 8px;font-size:15px">{link}</p>
<p style="margin:0 0 8px;font-size:13px;color:#777">{esc(cal_name)}. Texts from Divinum Officium (divinumofficium.com).</p>
<p style="margin:0;font-size:13px;color:#777"><a href="{{{{preferences_url}}}}" style="color:#777">Change settings</a> | <a href="{{{{unsubscribe_url}}}}" style="color:#777">Unsubscribe</a></p>
</div></body></html>
"""
    text = "\n\n".join([
        f"MATINS · {when}", title, la_title + (f" · {rank}" if rank else "")
        + (f"\n{comm_line(comms, 1)}" if comms else ""),
        "Read in Latin and English: {{page_url}}",
        "\n\n".join(email_text_lesson(n, les, brevis) for n, les, brevis in vernacular),
        "",
        f"{cal_name}. Texts from Divinum Officium (divinumofficium.com).",
        "Change settings: {{preferences_url}}",
        "Unsubscribe: {{unsubscribe_url}}",
    ])
    return {"subject": subject, "preheader": preheader, "html": html_doc, "text": text}


# ---------------------------------------------------------------- web page

STAR = ' <span class="star">*</span> '


def page_cell(kind, items):
    if kind == "resp":
        out = []
        for i in items:
            if i[0] == "R":
                t = esc(i[1]) + (f' <span class="star">*</span> {esc(i[2])}' if i[2] else "")
                out.append(f'<p><span class="rv">℟.{" br." if len(i) > 3 else ""}</span> {t}</p>')
            else:
                out.append(f'<p><span class="rv">℣.</span> {esc(i[1]).replace(" * ", STAR)}</p>')
        return "".join(out)
    if kind == "text":
        return "".join(f"<p>{esc(i)}</p>" for i in items)
    return "".join(f'<p class="{kind}">{esc(i)}</p>' for i in items)


def render_page(la_title, title, rank, date, lessons_pairs, lang_attr, comms=()):
    when = f"{WEEKDAYS[date.weekday()]}, {date.day} {MONTHS[date.month]} {date.year}"
    parts = [f'<p class="date">{esc(when)}</p>',
             f'<h1>{esc(la_title)}<span class="sub" lang="{lang_attr}">{esc(title)}</span></h1>']
    if rank:
        parts.append(f'<p class="rank">{esc(rank)}</p>')
    if comms:
        parts.append(f'<div class="pair comm"><div class="la" lang="la"><p class="rubric">{esc(comm_line(comms, 0))}</p></div>'
                     f'<div class="en" lang="{lang_attr}"><p class="rubric">{esc(comm_line(comms, 1))}</p></div></div>')
    for n, la, local, brevis in lessons_pairs:
        same = body_words(la) and body_words(la) == body_words(local)
        rows = layout.lesson_rows(n, la, local, untranslated=same, heads=SINGLE.get(brevis))
        parts.append('<section class="lesson">')
        for kind, a, b in rows:
            parts.append(f'<div class="pair{" resp" if kind == "resp" else ""}">'
                         f'<div class="la" lang="la">{page_cell(kind, a)}</div>'
                         f'<div class="en" lang="{lang_attr}">{page_cell(kind, b)}</div></div>')
        parts.append("</section>")
    return {"title": f"Matins for {when}: {title}", "html": "\n".join(parts)}


def body_words(les):
    return " ".join(p for b in les["blocks"] for p in b["paras"] + [t for _, t in b["verses"]])


# ---------------------------------------------------------------- API form

def api_text(les):
    """One language of a lesson, in the shape the public API returns."""
    parts = []
    for b in les["blocks"]:
        part = {"title": b["title"], "citation": b["cite"], "source": b["source"]}
        if b["verses"]:
            part["verses"] = [{"n": n, "text": t} for n, t in b["verses"]]
        part["paragraphs"] = list(b["paras"])
        parts.append(part)
    resp = []
    for item in les["responsory"]:
        if item[0] == "R":
            resp.append(dict({"type": "respond", "text": item[1], "repeat": item[2]},
                             **({"short": True} if len(item) > 3 else {})))
        elif item[0] == "G":
            resp.append({"type": "gloria", "text": item[1]})
        else:
            resp.append({"type": "verse", "text": item[1]})
    return {"notes": list(les["rubric"]), "parts": parts, "responsory": resp, "te_deum": les["tedeum"]}


# ---------------------------------------------------------------- build

def harvest(date, version, folder):
    out = subprocess.run(["perl", HARVEST, date.strftime("%m-%d-%Y"), version, folder],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def build_one(date, cal, lang, out_dir, corpus_titles):
    version, cal_name = CALENDARS[cal]
    folder, _ = LANGUAGES[lang]
    day = harvest(date, version, folder)
    la_title, title, rank = day_titles(day, corpus_titles, lang, cal)
    comms = commemorations(day, lang)
    pairs, vernacular = [], []
    for les in day["lessons"]:
        la = L.parse_lesson(les["latin"], "latin")
        local = L.parse_lesson(les["vernacular"], "english" if lang == "en" else "latin")
        if lang == "en":
            L.align_cites(la, local)
        if not body_words(la) and not body_words(local):
            continue  # the engine gave no text (see README: known engine issue)
        brevis = les.get("kind")  # None, "brevis" or "unica"
        pairs.append((les["n"], la, local, brevis))
        vernacular.append((les["n"], local, brevis))
    if not pairs:
        # The engine produced no lessons (a gap in Divinum Officium's data for
        # this calendar and day): publish nothing rather than an empty email.
        return None
    doc = {
        "date": date.isoformat(), "calendar": cal, "lang": lang, "version": version,
        "title": {"latin": la_title, "local": title}, "rank": rank,
        "commemorations": [{"latin": a, "local": b} for a, b in comms],
        "lessons": [dict({"number": n, "latin": api_text(la), "translation": api_text(local)},
                         **({"kind": {"brevis": "short", "unica": "single"}[brevis]} if brevis else {}))
                    for n, la, local, brevis in pairs],
        "email": render_email(day, la_title, title, rank, date, cal_name, vernacular, comms),
        "page": render_page(la_title, title, rank, date, pairs, lang, comms),
    }
    path = os.path.join(out_dir, cal, lang, f"{date.isoformat()}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=datetime.date.today().isoformat())
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--out", required=True)
    ap.add_argument("--calendars", default=",".join(CALENDARS))
    ap.add_argument("--languages", default=",".join(LANGUAGES))
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    args = ap.parse_args()

    start = datetime.date.fromisoformat(args.start)
    dates = [start + datetime.timedelta(days=i) for i in range(args.days)]
    cals = args.calendars.split(",")
    langs = args.languages.split(",")
    corpus_titles = load_corpus_titles()

    jobs = [(d, c, l) for c in cals for l in langs for d in dates]
    failures, missing = [], []
    with cf.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futs = {pool.submit(build_one, d, c, l, args.out, corpus_titles): (d, c, l) for d, c, l in jobs}
        for f in cf.as_completed(futs):
            try:
                if f.result() is None:
                    d, c, l = futs[f]
                    missing.append(f"{c}/{l}/{d.isoformat()}")
            except Exception as exc:  # report and carry on; the manifest lists what exists
                failures.append((futs[f], repr(exc)))

    # Manifest: what the sign-up form offers and which dates exist.
    manifest = {"generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                "calendars": {}, "languages": {k: v[1] for k, v in LANGUAGES.items()}}
    for cal in CALENDARS:
        langs_avail = {}
        for lang in LANGUAGES:
            d = os.path.join(args.out, cal, lang)
            if os.path.isdir(d):
                ds = sorted(f[:-5] for f in os.listdir(d) if re.match(r"\d{4}-\d\d-\d\d\.json$", f))
                if ds:
                    langs_avail[lang] = {"first": ds[0], "last": ds[-1]}
        if langs_avail:
            manifest["calendars"][cal] = {"name": CALENDARS[cal][1], "languages": langs_avail}
    manifest["missing"] = sorted(missing)  # days the engine gave no lessons for
    with open(os.path.join(args.out, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)

    print(f"{len(jobs) - len(failures) - len(missing)} pages written to {args.out}; "
          f"{len(missing)} days without lessons skipped; {len(failures)} failed")
    for job, err in failures[:10]:
        print("  failed:", job, err)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
