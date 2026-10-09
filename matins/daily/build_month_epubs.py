#!/usr/bin/env python3
"""Build one EPUB per calendar, language and month from a daily-data tree.

  python3 matins/daily/build_month_epubs.py DIR

Writes DIR/<calendar>/<lang>/epub/<YYYY-MM>.epub for every month whose days
are all published (allowing for the odd day the engine has no lessons for),
using each day's bilingual page. Output is reproducible, so a month that has
not changed produces the same bytes. EPUBs for months more than three months
past are removed.
"""

import argparse
import calendar as cal_mod
import datetime
import html
import json
import os
import re
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import build_epub as E  # noqa: E402
import epubkit  # noqa: E402

DAY = re.compile(r"^(\d{4})-(\d{2})-(\d{2})\.json$")
MONTHS = ["", "January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]
CSS = E.CSS + """
.calname { text-align: center; font-style: italic; color: #555; }
.date { text-align: center; font-variant: small-caps; letter-spacing: 0.05em; }
.comm p { font-size: 0.85em; }
"""


def esc(s):
    return html.escape(s or "", quote=False)


def page(title, body):
    return E.XHTML.format(title=esc(title), body=body)


def colophon_page():
    _front, back = E.front_pages(None)
    return next(doc for href, _, doc in back if href == "colophon.xhtml")


def build_month(d, cal, lang, month, days, cal_name, out_path):
    y, m = map(int, month.split("-"))
    files, spine, nav = [], [], []
    title = f"Matins, {MONTHS[m]} {y}"
    files.append(("title.xhtml", page(title, (
        f'<div style="margin-top:25%"><h1>{esc(title)}<span class="sub">Lectiones ad Matutinum</span></h1>'
        f'<p class="calname">{esc(cal_name)}</p>'
        '<p class="calname">The lessons and responsories of each day, in Latin and English.</p></div>'))))
    spine.append("title.xhtml")
    nav.append((title, "text/title.xhtml", []))
    for day in days:
        with open(os.path.join(d, f"{day}.json"), encoding="utf-8") as fh:
            doc = json.load(fh)
        href = f"d-{day}.xhtml"
        files.append((href, page(doc["page"]["title"], doc["page"]["html"])))
        spine.append(href)
        nav.append((f"{int(day[8:])} {MONTHS[m]}: {doc['title']['local']}", f"text/{href}", []))
    files.append(("colophon.xhtml", colophon_page()))
    spine.append("colophon.xhtml")
    nav.append(("Colophon", "text/colophon.xhtml", []))
    epubkit.write_epub(
        out_path,
        book_id="urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, f"matutinum.org/{cal}/{lang}/{month}")),
        title=f"{title} ({cal_name})", description=f"Matins for {MONTHS[m]} {y}: {cal_name}",
        files=files, spine=spine, nav=nav, css=CSS, modified=f"{month}-01T00:00:00Z")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    args = ap.parse_args()
    manifest_path = os.path.join(args.dir, "manifest.json")
    names = {}
    if os.path.exists(manifest_path):
        names = {k: v["name"] for k, v in json.load(open(manifest_path, encoding="utf-8")).get("calendars", {}).items()}
    oldest = (datetime.date.today().replace(day=1) - datetime.timedelta(days=92)).strftime("%Y-%m")

    built = 0
    for cal in sorted(os.listdir(args.dir)):
        cal_dir = os.path.join(args.dir, cal)
        if not os.path.isdir(cal_dir) or cal.startswith("."):
            continue
        for lang in sorted(os.listdir(cal_dir)):
            d = os.path.join(cal_dir, lang)
            if not os.path.isdir(d):
                continue
            by_month = {}
            for name in os.listdir(d):
                mt = DAY.match(name)
                if mt:
                    by_month.setdefault(f"{mt.group(1)}-{mt.group(2)}", []).append(name[:-5])
            epub_dir = os.path.join(d, "epub")
            for month, days in sorted(by_month.items()):
                y, m = map(int, month.split("-"))
                length = cal_mod.monthrange(y, m)[1]
                days.sort()
                complete = (days[0].endswith("-01") and days[-1].endswith(f"-{length:02d}")
                            and len(days) >= length - 7)
                if complete:
                    build_month(d, cal, lang, month, days, names.get(cal, cal),
                                os.path.join(epub_dir, f"{month}.epub"))
                    built += 1
            if os.path.isdir(epub_dir):
                for name in os.listdir(epub_dir):
                    if name.endswith(".epub") and name[:7] < oldest:
                        os.remove(os.path.join(epub_dir, name))
    print(f"built {built} monthly EPUBs")


if __name__ == "__main__":
    main()
