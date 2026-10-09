#!/usr/bin/env python3
"""Prune old days and write per-calendar indexes in a daily-data tree.

  python3 matins/daily/build_index.py DIR [--keep-past-days 60]

For every DIR/<calendar>/<lang>/, removes day files older than the window and
writes index.json: {"dates": {"YYYY-MM-DD": {"title", "latin", "rank"}}}, used
by the site's browse-by-date calendar.
"""

import argparse
import datetime
import json
import os
import re

DAY = re.compile(r"^(\d{4}-\d{2}-\d{2})\.json$")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--keep-past-days", type=int, default=60)
    args = ap.parse_args()
    cutoff = (datetime.date.today() - datetime.timedelta(days=args.keep_past_days)).isoformat()

    removed = indexed = 0
    for cal in sorted(os.listdir(args.dir)):
        cal_dir = os.path.join(args.dir, cal)
        if not os.path.isdir(cal_dir) or cal.startswith("."):
            continue
        for lang in sorted(os.listdir(cal_dir)):
            d = os.path.join(cal_dir, lang)
            if not os.path.isdir(d):
                continue
            dates = {}
            for name in sorted(os.listdir(d)):
                m = DAY.match(name)
                if not m:
                    continue
                path = os.path.join(d, name)
                if m.group(1) < cutoff:
                    os.remove(path)
                    removed += 1
                    continue
                with open(path, encoding="utf-8") as fh:
                    doc = json.load(fh)
                dates[m.group(1)] = {"title": doc["title"]["local"], "latin": doc["title"]["latin"],
                                     "rank": doc.get("rank", ""),
                                     "commemorations": [c["local"] for c in doc.get("commemorations", [])]}
            epub_dir = os.path.join(d, "epub")
            epubs = sorted(n[:-5] for n in os.listdir(epub_dir) if n.endswith(".epub")) if os.path.isdir(epub_dir) else []
            with open(os.path.join(d, "index.json"), "w", encoding="utf-8") as fh:
                json.dump({"calendar": cal, "lang": lang, "dates": dates, "epubs": epubs}, fh, ensure_ascii=False)
            indexed += len(dates)
    print(f"indexed {indexed} days; removed {removed} older than {cutoff}")


if __name__ == "__main__":
    main()
