"""The full text of a Gospel reading, for Matins lessons that give only its opening.

The breviary prints the first words of the Gospel and "Et reliqua" (the rest is
read at Mass). Divinum Officium's Mass texts give each Gospel in full under
[Evangelium], headed by its reference, so a Matins Gospel can be completed by
looking up the same reference.

  full_gospel("Matt 13:44-52")  ->  {"latin": "...", "english": "..."} or None

The English is completed from the Douay-Rheims (Challoner), the version the
breviary's English follows, in matins/data/douay-gospels.json (Project
Gutenberg #1582, public domain); the Missal's own English is more modern.
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lessons as L  # noqa: E402

WEB = os.path.join(os.path.dirname(os.path.dirname(HERE)), "web", "www")
# Mass texts first, then the Office files (which hold the Mass propers of the
# Commons); Roman folders before the monastic and Dominican ones.
SOURCES = [("missa", ""), ("horas", "Commune"), ("horas", "Sancti"), ("horas", "Tempora"), ("horas", "")]
EXTRA_BOOKS = {"Joann": "John", "Jn": "John", "Mt": "Matt", "Lk": "Luke", "Lc": "Luke", "Mk": "Mark", "Mc": "Mark"}
GOSPEL_TITLE = re.compile(r"^(Léctio|Lectio|Sequéntia|Sequentia|Initium|Inítium) sancti Evang")

_index = None


def key(cite):
    m = L._CITE_PARTS.match((cite or "").strip().rstrip("."))
    if not m:
        return None
    book = m.group(1).strip().rstrip(".")
    book = EXTRA_BOOKS.get(book) or L.BOOKS_EN.get(book) or L.BOOKS_EN.get(book + ".") or book
    return f"{book} {L._verses(m.group(2))}"


def _text(body):
    """The Gospel text from an [Evangelium] section: the lines after the reference."""
    lines = body.replace("\r", "").split("\n")
    out, started = [], False
    for line in lines:
        s = line.strip()
        if s.startswith("!"):
            started = True
            continue
        if not started:
            continue
        if not s:
            if out:
                break
            continue
        if s[0] in "($&@_":
            continue
        if s.startswith("v. "):
            s = s[3:]
        out.append(s.rstrip("~").strip())
    return re.sub(r"\s+", " ", " ".join(out)).strip()


def _build():
    index = {}
    for lang in ("Latin", "English"):
        seen = set()
        for top, sub in SOURCES:
            root = os.path.join(WEB, top, lang, sub)
            for folder, _, files in sorted(os.walk(root)):
                for name in sorted(files):
                    path = os.path.join(folder, name)
                    if not name.endswith(".txt") or path in seen:
                        continue
                    seen.add(path)
                    with open(path, encoding="utf-8", errors="replace") as fh:
                        txt = fh.read()
                    for m in re.finditer(r"^\[Evangelium[^\]\n]*\]\s*\n(.*?)(?=^\[|\Z)", txt, re.M | re.S):
                        cm = re.search(r"^!(.+)$", m.group(1), re.M)
                        k = key(cm.group(1)) if cm else None
                        text = _text(m.group(1))
                        if k and len(text) > 40:
                            index.setdefault(k, {}).setdefault(lang.lower(), text)
    return index


DOUAY = os.path.join(os.path.dirname(HERE), "data", "douay-gospels.json")
_douay = None


def douay_verses(cite):
    """[(chapter, verse, text)] for a reference such as "Luc 12:35-40" or
    "Joannes 15:26-27; 16:1-4", from the Douay-Rheims (Vulgate numbering)."""
    global _douay
    if _douay is None:
        import json
        with open(DOUAY, encoding="utf-8") as fh:
            _douay = json.load(fh)["books"]
    k = key(cite)
    if not k:
        return []
    book, rest = k.split(" ", 1)
    chapters = _douay.get(book)
    if not chapters:
        return []
    out, chapter = [], None
    for piece in re.split(r"[;,]", rest):
        m = re.match(r"(?:(\d+):)?(\d+)(?:-(\d+))?$", piece.strip())
        if not m:
            return []
        chapter = m.group(1) or chapter
        first, last = int(m.group(2)), int(m.group(3) or m.group(2))
        for v in range(first, last + 1):
            t = chapters.get(chapter, {}).get(str(v))
            if t is None:
                return []
            out.append((chapter, v, t))
    return out


# How the English openings end: "And so on.", "And so on, and that which followeth.",
# "And so forth.", "And what follows.", the Latin "Et réliqua.", and slips of each.
_ETC = re.compile(r"[\s,;]*\b(?:And so on(?:,? and that which followeth)?|And so forth|And what follows"
                  r"|Et r[ée]liqua|Etc)\b[\s.,;/]*$", re.I)


def douay_gospel(cite, opening):
    """The full Gospel in Douay-Rheims, keeping the breviary's own opening words
    ("At that time, Jesus said unto His disciples: ...") and continuing from where
    they leave off. Returns (text, matched) or (None, False)."""
    verses = douay_verses(cite)
    if not verses:
        return None, False
    start = _ETC.sub("", opening).rstrip().rstrip(",;")
    words = re.findall(r"[A-Za-z']+", start)
    if len(words) >= 3:
        tail = r"\W+".join(re.escape(w) for w in words[-3:])
        for i, (_, _, text) in enumerate(verses[:3]):
            m = None
            for m in re.finditer(r"\b" + tail + r"\b", text, re.I):
                pass  # the last occurrence in the verse
            if m:
                rest = text[m.end():].lstrip(" .,;:")
                tail_text = " ".join([rest] + [t for _, _, t in verses[i + 1:]]).strip()
                return (f"{start} {tail_text}".strip() if tail_text else start), True
    # The opening is worded differently from the Douay text: take it as the first verse.
    return f"{start} " + " ".join(t for _, _, t in verses[1:]), False


def full_gospel(cite):
    global _index
    if _index is None:
        _index = _build()
    found = _index.get(key(cite))
    return found if found and "latin" in found and "english" in found else None


def complete(latin, english=None):
    """Replace the opening-words-only Gospel in parsed lessons with the full text:
    the Latin from the Missal (Vulgate), the English from the Douay-Rheims."""
    for i, b in enumerate(latin["blocks"]):
        if not (b["cite"] and GOSPEL_TITLE.match(b["title"])):
            continue
        g = full_gospel(b["cite"])
        if not g:
            continue
        b["paras"], b["verses"] = [g["latin"]], []
        if english and len(english["blocks"]) == len(latin["blocks"]):
            eb = english["blocks"][i]
            opening = " ".join(eb["paras"] or [v[1] for v in eb["verses"]])
            text, _ = douay_gospel(b["cite"], opening)
            if text:
                eb["paras"], eb["verses"] = [text], []
