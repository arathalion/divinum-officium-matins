#!/usr/bin/env python3
"""Build the by-proper Matins corpus from the engine harvest.

Inputs (see README):
  cache/harvest/*.jsonl.gz   one line per date, from harvest_years.sh
  cache/files.jsonl          resolved sections of every office file, from extract_files.pl

Every lesson the engine produced on some date is assigned to the file it is
"at home" in (the Tempora, Sancti or Commune file whose Lectio section holds
that text). Each file that is at home to a lesson, plus every Sancti file that
won the day, becomes an entry; slots whose lesson lives elsewhere become
references ("de Scriptura occurrente", "ex Communi ...").

Outputs:
  data/corpus.json
  text/{latin,english}/{temporale,sanctorale,commune}/<file>.txt (+ index.txt)
"""

import collections
import glob
import gzip
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import lessons as L  # noqa: E402
import titles  # noqa: E402

TAIL = 160


# --------------------------------------------------------------------------- keys

def body_key(text):
    """A comparison key for a lesson's body: letters only, no responsory,
    citations, verse numbers or engine markup."""
    raw = [l for l in text.split("\n")
           if not L._HEADING.match(l) and not L._RUBRIC_LINE.match(l)]
    lines = [l.strip() for l in re.sub(r"<[^>]+>", "", "\n".join(raw)).split("\n")]
    out = []
    for i, l in enumerate(lines):
        if l.startswith("R. ") and any(x == "_" for x in lines[max(0, i - 2):i]):
            break
        if not l or l[0] in "!_$&" or l.startswith("/:"):
            continue
        if l.startswith("v. "):
            l = l[3:]
        out.append(l)
    s = unicodedata.normalize("NFKD", " ".join(out).lower())
    s = "".join(c for c in s if c.isalpha())
    return s


# ------------------------------------------------------------------------ loading

def load_files():
    files = {}
    for line in open(os.path.join(ROOT, "cache", "files.jsonl"), encoding="utf-8"):
        d = json.loads(line)
        files[d["file"]] = d
    return files


def iter_days():
    for path in sorted(glob.glob(os.path.join(ROOT, "cache", "harvest", "*.jsonl.gz"))):
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                yield json.loads(line)


# ----------------------------------------------------------------------- helpers

def stem(f):
    return os.path.splitext(f)[0] if f else ""


def kind(f):
    return f.split("/", 1)[0] if f else ""


MONTHS = {"08": ("Augusti", "August"), "09": ("Septembris", "September"),
          "10": ("Octobris", "October"), "11": ("Novembris", "November")}
ORD_EN = ["", "first", "second", "third", "fourth", "fifth"]
DAYS_EN = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def month_title(f, lang):
    """Title for Tempora/MMW-D.txt (Scripture of the weeks of August–November)."""
    m = re.match(r"^Tempora/(\d\d)(\d)-(\d)\.txt$", f)
    if not m or m.group(1) not in MONTHS:
        return ""
    mon, week, day = MONTHS[m.group(1)], int(m.group(2)), int(m.group(3))
    if lang == "latin":
        if day == 0:
            return f"Dominica {L.ROMAN[week]} {mon[0]}"
        feria = "Sabbato" if day == 6 else f"Feria {L.ROMAN[day + 1]}"
        return f"{feria} infra Hebdomadam {L.ROMAN[week]} {mon[0]}"
    if day == 0:
        return f"{ORD_EN[week].capitalize()} Sunday of {mon[1]}"
    return f"{DAYS_EN[day]} of the {ORD_EN[week]} week of {mon[1]}"


# The forms of the Saturday Office of Our Lady, by season (wording from the
# files' [Missa] headings).
SATURDAY_BVM = {
    "C10": ("a Trinitate usque ad Adventum", "from Trinity to Advent"),
    "C10a": ("in Adventu", "in Advent"),
    "C10b": ("a Nativitate usque ad Purificationem", "from Christmas to the Purification"),
    "C10c": ("post Purificationem usque ad Dominicam Palmarum", "from the Purification to Palm Sunday"),
    "C10Pasc": ("tempore Paschali", "in Paschaltide"),
}


def title_of(files, f, lang):
    if month_title(f, lang):
        return month_title(f, lang)
    st = os.path.basename(stem(f))
    if kind(f) == "Commune" and st in SATURDAY_BVM:
        season = SATURDAY_BVM[st][0 if lang == "latin" else 1]
        return f"Sanctæ Mariæ Sabbato ({season})" if lang == "latin" else f"Our Lady's Saturday ({season})"
    d = files.get(f, {})
    latin = (d.get("latin") or {}).get("Officium") or ""
    if not latin:
        latin = (d.get("latin") or {}).get("Rank", "").split(";;")[0]
    latin = latin.strip()
    nat = titles.nat_title(os.path.basename(stem(f)), latin, lang) if kind(f) == "Tempora" else None
    if nat:
        return nat
    if lang == "latin":
        return latin
    english = titles.english_title(latin, ((d.get("english") or {}).get("Officium") or "").strip())
    if kind(f) == "Tempora":
        for cand in (english, latin):
            if cand and titles.english_tempora(cand) != cand:
                return titles.english_tempora(cand)
    return english if english != latin else titles.english_title(latin, "")


def raw_section(files, f, sec, lang):
    """A section's source text; for joined readings ("Lectio2-3") the parts in order."""
    src = (files.get(f, {}).get(lang) or {})
    m = re.match(r"^Lectio(\d+)-(\d+)$", sec)
    if m:
        return "\n".join(src.get(f"Lectio{i}", "") for i in range(int(m.group(1)), int(m.group(2)) + 1))
    return src.get(sec, "")


def normalise_rank(name, num):
    """Tidy the many spellings of a rank; give Semiduplex Sundays their class,
    which the files record only as a number (6.5+ = I classis, 5.5+ = II classis)."""
    name = re.sub(r"\b(?:1|I)\.? ?(?:st )?[Cc]lass(?:is)?\b", "I classis", name)
    name = re.sub(r"\b(?:2|2nd|II)\.? ?[Cc]lass(?:is)?\b", "II classis", name)
    name = re.sub(r"\b(?:3|III)\.? ?[Cc]lass(?:is)?\b", "III classis", name)
    name = re.sub(r"^I classis Semiduplex$", "Semiduplex I classis", name)
    name = re.sub(r"\b[Cc]um [Oo]ctava\b", "cum Octava", name)
    name = re.sub(r"\bOctava ([Cc]ommuni|[Ss]implici|[Pp]rivilegiata)", lambda m: "Octava " + m.group(1).lower(), name)
    try:
        n = float(num)
    except ValueError:
        n = 0
    if name == "Semiduplex" and n >= 6.5:
        name = "Semiduplex I classis"
    elif name == "Semiduplex" and n >= 5.5:
        name = "Semiduplex II classis"
    return name


def rank_of(files, f):
    rank = (files.get(f, {}).get("latin") or {}).get("Rank", "")
    parts = [p.strip() for p in rank.split("\n")[0].split(";;")]
    return normalise_rank(parts[1], parts[2] if len(parts) > 2 else "") if len(parts) > 1 else ""


SEASONS = ["Adv", "Nat", "Epi", "Quadp", "Quad", "Pasc", "Pent"]


def temporale_sort(name):
    s = os.path.basename(name)
    # Christmastide is ordered by date: Sunday in the Octave (26-31 Dec), the
    # dated Scripture (NatDD), the Holy Name (Sunday 2-5 Jan).
    m = re.match(r"^Nat(\d\d)$", s)
    if m:
        d = int(m.group(1))
        return (1, 0 if d >= 24 else 1, d, 0, s)
    if s.startswith("Nat1-0"):
        return (1, 0, 28.5, 0, s)
    if s.startswith("Nat2-0"):
        return (1, 1, 1.5, 0, s)
    m = re.match(r"^(\d\d)(\d)-(\d)", s)
    if m:  # month files: 081-0 = August, week 1, Sunday
        return (len(SEASONS), int(m.group(1)), int(m.group(2)), int(m.group(3)), s)
    m = re.match(r"^([A-Za-z]+?)(\d+)(?:-(\d+))?(.*)$", s)
    if m:
        season = m.group(1)
        idx = SEASONS.index(season) if season in SEASONS else len(SEASONS) + 1
        return (idx, int(m.group(2)), int(m.group(3) or 0), 0, m.group(4))
    return (99, 0, 0, 0, s)


def sanctorale_sort(name):
    s = os.path.basename(name)
    m = re.match(r"^(\d\d)-(\d\d)(.*)$", s)
    return (int(m.group(1)), int(m.group(2)), m.group(3)) if m else (99, 99, s)


def commune_sort(name):
    s = os.path.basename(name)
    m = re.match(r"^C(\d+)(.*)$", s)
    return (int(m.group(1)), m.group(2)) if m else (99, s)


# -------------------------------------------------------------------------- build

def main():
    files = load_files()

    # Index every Lectio section of every file by body key, and by the key's
    # ending (for Common lessons whose "N." the engine fills with a name).
    home_index = collections.defaultdict(list)  # key -> [(file, section)]
    tail_index = collections.defaultdict(list)  # key[-TAIL:] -> [(file, section, len)]
    keys = {}                                   # (file, section) -> key
    for f, d in files.items():
        for sec, text in (d.get("latin") or {}).items():
            if sec.startswith("Lectio") and sec not in ("Lectio", "Lectio Prima"):
                k = body_key(text)
                if len(k) > 40:
                    home_index[k].append((f, sec))
                    keys[(f, sec)] = k
                    if len(k) > 2 * TAIL:
                        tail_index[k[-TAIL:]].append((f, sec, len(k)))

    def numbered(f):
        out = {}
        for (ff, sec), k in keys.items():
            m = re.match(r"^Lectio(\d+)$", sec)
            if ff == f and m:
                out[int(m.group(1))] = k
        return out

    numbered_cache = {}

    def find_home(k, n, refs):
        """Return ((file, section), how) for a harvested lesson key."""
        cands = home_index.get(k, [])
        for role in ("winner", "scriptura", "commune", "commemoratio"):
            for c in cands:
                if c[0] == refs[role]:
                    return c, "exact"
        if cands:
            same = [c for c in cands if c[1] == f"Lectio{n}"]
            return (same or cands)[0], "exact"
        # Name filled in for "N.": same ending, about the same length.
        if len(k) > 2 * TAIL:
            tails = [c for c in tail_index.get(k[-TAIL:], []) if abs(c[2] - len(k)) < 0.15 * len(k)]
            for role in ("winner", "commune", "commemoratio", "scriptura"):
                for c in tails:
                    if c[0] == refs[role]:
                        return (c[0], c[1]), "named"
            if tails:
                return (tails[0][0], tails[0][1]), "named"
        # Several consecutive lessons of one file read as one.
        pool = [refs[r] for r in ("winner", "commemoratio", "scriptura", "commune") if refs.get(r)]
        for ff in dict.fromkeys(pool + list(refs.get("extra") or [])):
            if True:
                if ff not in numbered_cache:
                    numbered_cache[ff] = numbered(ff)
                nums = numbered_cache[ff]
                for a in sorted(nums):
                    acc = ""
                    for b in range(a, a + 4):
                        if b not in nums:
                            break
                        acc += nums[b]
                        if b > a and acc == k:
                            return (ff, f"Lectio{a}-{b}"), "joined"
        return None, None

    occurrences = collections.defaultdict(list)  # (file, section) -> [occ]
    winners = collections.defaultdict(list)      # winner file -> [day summary]
    unmatched = collections.Counter()
    empty = []  # (date, n, winner): the engine produced no text for this lesson
    ndays = 0

    for day in iter_days():
        ndays += 1
        w = day.get("winner") or ""
        refs = {
            "winner": w,
            "scriptura": day.get("scriptura") or "",
            "commune": day.get("commune") or "",
            "commemoratio": day.get("commemoratio") or "",
        }
        slots = []
        refs["extra"] = [os.path.join("Sancti", e + ".txt") if "/" not in e else e + ".txt"
                         for e in day.get("commemoentries") or []]
        for les in day["lessons"]:
            k = body_key(les["latin"])
            if not k:
                empty.append((day["date"], les["n"], w))
                slots.append([les["n"], None, None])
                continue
            home, how = find_home(k, les["n"], refs)
            if home:
                occurrences[home].append({
                    "date": day["date"], "n": les["n"], "winner": w, "how": how,
                    "latin": les["latin"], "english": les["english"],
                })
                slots.append([les["n"], home[0], home[1]])
            else:
                unmatched[(w, les["n"])] += 1
                slots.append([les["n"], None, None])
        winners[w].append({
            "date": day["date"], "slots": slots,
            "title_latin": day.get("title_latin"), "title_english": day.get("title_english"),
            "commune": refs["commune"], "scriptura": refs["scriptura"],
        })

    # Pick one rendering per (file, section).
    chosen = {}
    for home, occs in occurrences.items():
        own = [o for o in occs if o["winner"] == home[0]]
        pool = own or occs
        counts = collections.Counter((o["latin"], o["english"]) for o in pool)
        (la, en), _ = counts.most_common(1)[0]
        n = collections.Counter(o["n"] for o in pool).most_common(1)[0][0]
        chosen[home] = {"n": n, "latin": la, "english": en, "dates": len(occs)}

    # Entries.
    entries = {}
    homes_by_file = collections.defaultdict(list)
    for (f, sec) in chosen:
        m = re.match(r"^Lectio(\d+)-(\d+)$", sec)
        if m and all((f, f"Lectio{i}") in chosen
                     for i in range(int(m.group(1)), int(m.group(2)) + 1)):
            continue
        homes_by_file[f].append(sec)

    def entry_for(f):
        if f not in entries:
            entries[f] = {
                "file": f, "kind": kind(f),
                "title_latin": title_of(files, f, "latin"),
                "title_english": title_of(files, f, "english"),
                "rank": rank_of(files, f),
                "lessons": [], "refs": [],
            }
        return entries[f]

    for f, secs in homes_by_file.items():
        e = entry_for(f)
        for sec in secs:
            c = chosen[(f, sec)]
            m = re.match(r"^Lectio(\d+)(?:-\d+)?(?: in (\d+) loco)?$", sec)
            num = int(m.group(1)) if m and int(m.group(1)) < 13 else c["n"]
            note = ""
            if sec in ("Lectio93", "Lectio94"):
                note = "commemoratio"
            elif m and m.group(2):
                note = f"loco{m.group(2)}"
            entry = {"section": sec, "n": num, "note": note, "dates": c["dates"]}
            for lang in ("latin", "english"):
                entry[lang] = L.restore_verse_case(L.parse_lesson(c[lang], lang), raw_section(files, f, sec, lang))
            L.align_cites(entry["latin"], entry["english"])
            e["lessons"].append(entry)

        def lsort(x):
            m = re.match(r"Lectio(\d+)", x["section"])
            return (x["n"], int(m.group(1)) if m else 0, x["section"])

        e["lessons"].sort(key=lsort)

    # Commons: every lesson of the Common file, not only those the engine used.
    for f, e in entries.items():
        if e["kind"] == "Commune":
            e["lessons"] = commune_lessons(files, f)

    # References for Sancti winners (and Tempora winners that have own lessons).
    for w, days in winners.items():
        if not w:
            continue
        if kind(w) != "Sancti" and w not in entries:
            continue
        e = entry_for(w)
        if days[0].get("title_english") and e["title_english"] == e["title_latin"]:
            e["title_english"] = days[0]["title_english"]
        sig = collections.Counter(
            tuple((n, kind(hf) if hf != w else "own", hf if kind(hf) in ("Commune", "Sancti") else "",
                   hs if kind(hf) == "Commune" else "")
                  for n, hf, hs in d["slots"])
            for d in days
        ).most_common(1)[0][0]
        refs = []
        for n, k, cf, cs in sig:
            if k == "own":
                continue
            if k == "Commune":
                refs.append({"n": n, "type": "commune", "file": cf, "section": cs,
                             "title_latin": title_of(files, cf, "latin"),
                             "title_english": title_of(files, cf, "english")})
            elif k == "Tempora":
                refs.append({"n": n, "type": "scriptura"})
            elif k == "Sancti":
                refs.append({"n": n, "type": "sancti", "file": cf,
                             "title_latin": title_of(files, cf, "latin"),
                             "title_english": title_of(files, cf, "english")})
            else:
                refs.append({"n": n, "type": "unknown"})
        e["refs"] = refs
        e["won_on"] = len(days)
        if kind(w) == "Commune":
            # A Common said as the office of the day (Saturday of Our Lady): which of
            # its sections were read, and the Scripture that places the day in a season.
            e["won_days"] = [[d["date"], d.get("scriptura") or "",
                              sorted({hs for n, hf, hs in d["slots"] if hf == w})] for d in days]

    # Every date a temporal office was said, or any of its lessons read (e.g. a
    # feria's Scripture on a saint's day): this places movable days in the
    # breviary's parts.
    read = collections.defaultdict(set)
    for (f, sec), occs in occurrences.items():
        if kind(f) == "Tempora":
            read[f].update(o["date"] for o in occs)
    for w, days in winners.items():
        if kind(w) == "Tempora":
            read[w].update(d["date"] for d in days)
    for f, e in entries.items():
        if f in read:
            e["read_dates"] = sorted(read[f], key=lambda d: (d[6:], d[:5]))

    fold_second_forms(files, entries, entry_for)
    drop_duplicate_variants(entries)

    corpus = {
        "version": "Divino Afflatu - 1954",
        "harvest_days": ndays,
        "entries": sorted(entries.values(), key=lambda e: e["file"]),
        "unmatched": [{"winner": w, "n": n, "days": c} for (w, n), c in unmatched.most_common()],
        "empty": [{"date": d, "n": n, "winner": w} for d, n, w in empty],
    }
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    with open(os.path.join(ROOT, "data", "corpus.json"), "w", encoding="utf-8") as fh:
        json.dump(corpus, fh, ensure_ascii=False, indent=1)

    write_text(corpus)
    write_coverage(files, chosen, entries)
    print(f"{ndays} days; {len(entries)} entries; "
          f"{sum(len(e['lessons']) for e in entries.values())} lessons; "
          f"{sum(unmatched.values())} unmatched lesson-slots; {len(empty)} empty lessons from the engine")



# ----------------------------------------------------------------- commons in full

def drop_duplicate_variants(entries):
    """Drop variant files (Nat1-0a, Epi1-0g, ...) whose Matins is identical to
    their base file's: they differ only in other Hours."""
    for f in sorted(entries):
        e = entries.get(f)
        if not e or e["kind"] not in ("Tempora", "Sancti"):
            continue
        m = re.match(r"^(.*\d)([a-z]+)\.txt$", f)
        if not m or m.group(1) + ".txt" not in entries:
            continue
        base = entries[m.group(1) + ".txt"]
        mine = {l["section"]: body_words(l["latin"]) for l in e["lessons"]}
        theirs = {l["section"]: body_words(l["latin"]) for l in base["lessons"]}
        same_refs = [(r["n"], r["type"], r.get("file")) for r in e.get("refs", [])] == \
                    [(r["n"], r["type"], r.get("file")) for r in base.get("refs", [])]
        if mine and all(theirs.get(k) == v for k, v in mine.items()) and same_refs:
            del entries[f]


def fold_second_forms(files, entries, entry_for):
    """Fold the second form of a Common (C4-1, C2-1p, ...) into its parent (C4,
    C2p), as the breviary prints them: lessons the parent already has become
    references to the parent's section (e.g. C4 "Lectio7 in 2 loco"). A second
    form keeps an entry only for lessons the parent does not have."""
    alias = {}
    for f in sorted(e for e in entries if entries[e]["kind"] == "Commune"):
        m = re.match(r"^Commune/(C\d+[a-z]*)-\d+(p?)\.txt$", f)
        if not m:
            continue
        parent = f"Commune/{m.group(1)}{m.group(2)}.txt"
        if parent not in files:
            continue
        if parent not in entries:
            entry_for(parent)["lessons"] = commune_lessons(files, parent)
        pmap = {}
        for l in entries[parent]["lessons"]:
            pmap.setdefault(body_words(l["latin"]), l["section"])
        keep = []
        for l in entries[f]["lessons"]:
            ps = pmap.get(body_words(l["latin"]))
            if ps:
                alias[(f, l["section"])] = (parent, ps)
            else:
                keep.append(l)
        if keep:
            e = entries[f]
            e["lessons"], e["see"] = keep, parent
            for lang in ("latin", "english"):
                if not e["title_" + lang] or e["title_" + lang] == e["title_latin"] and lang == "english":
                    base = entries[parent]["title_" + lang]
                    e["title_" + lang] = base + (" (altera forma)" if lang == "latin" else " (second form)")
        else:
            del entries[f]
    for e in entries.values():
        for r in e.get("refs", []):
            if r["type"] == "commune" and (r["file"], r.get("section")) in alias:
                r["file"], r["section"] = alias[(r["file"], r["section"])]
                r["title_latin"] = entries[r["file"]]["title_latin"]
                r["title_english"] = entries[r["file"]]["title_english"]


MONTH_ABL = ["", "Januario", "Februario", "Martio", "Aprili", "Majo", "Junio", "Julio", "Augusto",
             "Septembri", "Octobri", "Novembri", "Decembri"]
MONTH_EN = ["", "January", "February", "March", "April", "May", "June", "July", "August",
            "September", "October", "November", "December"]


def as_lectio_markup(text):
    """Give a raw Lectio section the shape lectio() output has ("v." initials)."""
    text = text.replace("\r", "").strip("\n")
    if not re.search(r"^!", text, re.M):
        return re.sub(r"^(?=[^\W\d_])", "v. ", text, count=1)
    return re.sub(r"^(!.*\n)(?=[^\W\d_])", r"\1v. ", text, flags=re.M)


def with_gloria(resp):
    """Add Gloria Patri and the repeated respond, as responsory_gloria() does."""
    if not resp or "&Gloria" in resp:
        return resp
    resp = resp.rstrip()
    last = [l for l in resp.split("\n") if l.startswith("R. ")]
    return resp + "\n&Gloria1\n" + last[-1] if last else resp


def commune_lessons(files, f):
    """All lessons of a Common file, as printed in the Commune Sanctorum."""
    d = files.get(f, {})
    la, en = d.get("latin") or {}, d.get("english") or {}
    out = []
    for sec in la:
        m = re.match(r"^Lectio(\d+)(?: in (\d+) loco)?$", sec)
        mm = re.match(r"^Lectio M(\d+)$", sec)
        if m:
            num, loco = int(m.group(1)), int(m.group(2) or 1)
            note = f"loco{loco}" if loco > 1 else ""
            order = (loco, num)
        elif mm:
            num, loco = 3, 99
            code = int(mm.group(1))
            note = "M101" if code == 101 else f"M{code:02d}"
            order = (loco, code)
        else:
            continue
        if num > 12:
            continue
        rkey = f"Responsory{num}" + (f" in {loco} loco" if m and loco > 1 else "")
        lesson = {"section": sec, "n": num, "note": note, "dates": 0, "order": order}
        has9 = "Responsory9" in la
        tedeum = (num == 9 and not has9) or (mm is not None)
        for lang, src in (("latin", la), ("english", en)):
            body = as_lectio_markup(src.get(sec) or la.get(sec, ""))
            resp = src.get(rkey) or src.get(f"Responsory{num}") or la.get(rkey) or la.get(f"Responsory{num}") or ""
            if mm or tedeum:
                resp = ""
            elif num % 3 == 0 or (num == 8 and not has9):
                resp = with_gloria(resp)
            text = body + ("\n_\n" + resp if resp else "") + ("\n&teDeum" if tedeum else "")
            lesson[lang] = L.parse_lesson(text, lang)
        L.align_cites(lesson["latin"], lesson["english"])
        out.append(lesson)
    out.sort(key=lambda x: x["order"])
    for x in out:
        del x["order"]
    return out


# ------------------------------------------------------------------------ output

def write_coverage(files, chosen, entries):
    """List Lectio sections of files in the corpus that the engine never read."""
    lines = ["# Lectio sections never produced by the engine (Divino Afflatu - 1954, harvest years)",
             "# in files that do appear in the corpus. Joined readings (e.g. 8+9) count as read.", ""]
    read = set(chosen)
    for (f, sec) in list(chosen):
        m = re.match(r"^Lectio(\d+)-(\d+)$", sec)
        if m:
            read.update((f, f"Lectio{i}") for i in range(int(m.group(1)), int(m.group(2)) + 1))
    for f in sorted(entries):
        if kind(f) == "Commune":  # printed in full regardless
            continue
        secs = sorted(k for k in (files.get(f, {}).get("latin") or {})
                      if k.startswith("Lectio") and k not in ("Lectio", "Lectio Prima") and (f, k) not in read)
        if secs:
            lines.append(f"{f}: {', '.join(secs)}")
    with open(os.path.join(ROOT, "data", "coverage.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


FOLDER = {"Tempora": "temporale", "Sancti": "sanctorale", "Commune": "commune"}
SORT = {"Tempora": temporale_sort, "Sancti": sanctorale_sort, "Commune": commune_sort}

NOTE = {
    "latin": {"commemoratio": "pro commemoratione", "M101": "infra Octavam Nativitatis B.M.V.",
              **{f"loco{i}": f"in {i} loco" for i in range(2, 9)},
              **{f"M{i:02d}": f"mense {MONTH_ABL[i]}" for i in range(1, 13)}},
    "english": {"commemoratio": "when commemorated", "M101": "within the Octave of the Nativity of Our Lady",
                **{f"loco{i}": f"set {i}" for i in range(2, 9)},
                **{f"M{i:02d}": f"in {MONTH_EN[i]}" for i in range(1, 13)}},
}

REF_TEXT = {
    "latin": {
        "scriptura": "de Scriptura occurrente",
        "commune": "ex {title} ({code})",
        "sancti": "de {title} ({code})",
        "unknown": "aliunde",
    },
    "english": {
        "scriptura": "from the Scripture of the day",
        "commune": "from the {title} ({code})",
        "sancti": "of {title} ({code})",
        "unknown": "from elsewhere",
    },
}


def body_words(lesson):
    return " ".join(p for b in lesson["blocks"] for p in b["paras"] + [t for _, t in b["verses"]])


def untranslated(les):
    la = body_words(les["latin"])
    return bool(la) and la == body_words(les["english"])


def ranges(ns):
    ns = sorted(ns)
    out, start, prev = [], None, None
    for n in ns:
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            out.append((start, prev))
            start = prev = n
    if start is not None:
        out.append((start, prev))
    return out


def roman_range(a, b):
    return L.ROMAN[a] if a == b else f"{L.ROMAN[a]}–{L.ROMAN[b]}"


def entry_text(e, lang):
    head = e["title_latin"] if lang == "latin" else e["title_english"]
    out = [head]
    if e["rank"]:
        out.append(e["rank"])
    out.append(f"[{stem(e['file'])}]")
    if e.get("see"):
        code = os.path.basename(stem(e["see"]))
        out.append(f"Cetera ut in {code}." if lang == "latin" else f"Otherwise as in {code}.")
    out.append("")

    # Group references by (type, file).
    groups = collections.OrderedDict()
    for r in e.get("refs", []):
        loco = re.search(r" in (\d+) loco$", r.get("section") or "")
        groups.setdefault((r["type"], r.get("file", ""), loco.group(1) if loco else ""), []).append(r)
    word = "Lectiones" if lang == "latin" else "Lessons"
    for (t, f, loco), rs in groups.items():
        title = rs[0].get("title_" + lang) or rs[0].get("title_latin") or ""
        if lang == "latin":
            title = re.sub(r"^Commune\b", "Commúni", title)
        what = REF_TEXT[lang][t].format(title=title, code=os.path.basename(stem(f)))
        if loco:
            what += ", " + NOTE[lang][f"loco{loco}"]
        for a, b in ranges([r["n"] for r in rs]):
            w = word if a != b else ("Lectio" if lang == "latin" else "Lesson")
            out.append(f"{w} {roman_range(a, b)}: {what}.")
    if groups:
        out.append("")

    for les in e["lessons"]:
        label_n = les["n"]
        sec = les["section"]
        txt = L.to_text(label_n, les[lang], lang, NOTE[lang].get(les.get("note", ""), les.get("note", "")))
        if lang == "english" and untranslated(les):
            first, _, rest = txt.partition("\n")
            txt = first + "\n[No English translation in the source files; the Latin is given.]\n" + rest
        out.append(txt)
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def write_text(corpus):
    base = os.path.join(ROOT, "text")
    by_kind = collections.defaultdict(list)
    for e in corpus["entries"]:
        if e["kind"] in FOLDER:
            by_kind[e["kind"]].append(e)
    for lang in ("latin", "english"):
        for k, es in by_kind.items():
            d = os.path.join(base, lang, FOLDER[k])
            os.makedirs(d, exist_ok=True)
            for old in glob.glob(os.path.join(d, "*.txt")):
                os.remove(old)
            es = sorted(es, key=lambda e: SORT[k](stem(e["file"])))
            index = []
            for e in es:
                name = os.path.basename(stem(e["file"])) + ".txt"
                with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
                    fh.write(entry_text(e, lang))
                title = e["title_latin"] if lang == "latin" else e["title_english"]
                index.append(f"{os.path.basename(stem(e['file'])):<12} {title}")
            with open(os.path.join(d, "index.txt"), "w", encoding="utf-8") as fh:
                fh.write("\n".join(index) + "\n")


if __name__ == "__main__":
    main()
