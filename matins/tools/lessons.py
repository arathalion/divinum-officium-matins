"""Parse Divinum Officium Matins lesson markup into a plain structure.

Input is the text returned by the engine's lectio() (see harvest_day.pl): DO
markup plus a little HTML that lectio() adds (the "Lectio N" heading, red verse
numbers, small parenthesised notes). parse_lesson() returns:

    {
      "rubric":  ["Commemoratio Feriae", ...],          # red notes before the text
      "blocks":  [                                      # one per "_"-separated part
        {"title": "De Ezechiéle Prophéta",              # e.g. "Homilía sancti Gregórii Papæ"
         "cite":  "Ezek 7:1-4",                         # scripture reference, if any
         "source": "Homilia 9 in Evangelia",            # patristic source line, if any
         "verses": [[1, "Et factus est ..."], ...],     # numbered scripture, or
         "paras":  ["Cárolus, Mediolani ...", ...]},    # prose paragraphs
      ],
      "responsory": [["R", "...", "..."], ["V", "..."], ["R", "..."], ["G", "..."]],
      "tedeum": False,
    }

Responsory entries: ("R", text, repetendum) for the respond — the repetendum
is the part after the asterisk, or "" — then ("V", text), ("R", text) for the
repeated part, and ("G", text) for the Gloria Patri.
"""

import html
import re

GLORIA1 = {
    "latin": "Glória Patri, et Fílio, * et Spirítui Sancto.",
    "english": "Glory be to the Father, and to the Son, * and to the Holy Ghost.",
}

_HEADING = re.compile(r"^<FONT SIZE='\+1'[^>]*>.*?</FONT>\s*$")
_RUBRIC_LINE = re.compile(r'^<FONT COLOR="red"><I>(.*?)</I></FONT>\s*$')
_VERSE_NUM = re.compile(r"^<FONT SIZE='1' COLOR=\"red\">(\d+)</FONT>\s*")
_SMALL = re.compile(r"<FONT SIZE='1' COLOR=\"red\">(.*?)</FONT>", re.S)
_TAG = re.compile(r"<[^>]+>")
_CITE = re.compile(
    r"^(?:[1-4] ?)?[^\W\d_][^\W\d_]+\.? \d+[:,]\d+(?:[-–]\d+(?::\d+)?)?(?:[;,] ?\d+(?:[:,]\d+)?(?:[-–]\d+)?)*\.?\s*$"
)


def _normalise(text):
    """Turn lectio() output back into line-based DO markup without HTML."""
    out = []
    for line in text.replace("\r", "").split("\n"):
        if _HEADING.match(line):
            continue
        m = _RUBRIC_LINE.match(line)
        if m:
            out.append("/:" + m.group(1) + ":/")
            continue
        m = _VERSE_NUM.match(line)
        if m:
            line = m.group(1) + " " + line[m.end():]
        # Small red text is either an English translator's note that the source
        # had in parentheses, or a Latin rubric; both read well in parentheses.
        line = _SMALL.sub(lambda mm: "(" + mm.group(1).strip() + ")", line)
        line = _TAG.sub("", line)
        line = html.unescape(line)
        out.append(line.rstrip())
    # "~" at end of line joins with the next line.
    joined = []
    for line in out:
        if joined and joined[-1].endswith("~"):
            joined[-1] = joined[-1][:-1].rstrip() + " " + line.lstrip()
        else:
            joined.append(line)
    # A "~" left at the start of a line joins nothing (a slip in a few sources).
    return [re.sub(r"\s+", " ", l.lstrip("~")).strip() if l.strip() else "" for l in joined]


def _tidy(s):
    s = s.replace("/:«", "").replace("»:/", "")
    s = re.sub(r"\s+([,.;:?!])", r"\1", s) if False else s
    return re.sub(r"\s{2,}", " ", s).strip()


# A heading ("From the Book of ...") is a line or two; anything longer is the
# lesson itself, set without its usual red initial.
TITLE_MAX = 150


def parse_lesson(text, lang="latin"):
    lines = _normalise(text)
    tedeum = any(l.startswith("&teDeum") for l in lines)
    lines = [l for l in lines if not l.startswith("&teDeum")]

    # The responsory starts at the first "R." line that follows a "_" separator.
    resp_at = None
    for i, l in enumerate(lines):
        if l.startswith("R. ") or l == "R." or l.startswith("R.br. "):
            j = i - 1
            while j >= 0 and not lines[j]:
                j -= 1
            if j >= 0 and lines[j] == "_":
                resp_at = i
                break
    body = lines[:resp_at] if resp_at is not None else lines
    resp = lines[resp_at:] if resp_at is not None else []

    body = [l for l in body if l and l != "$Tu autem"]
    while body and body[0] == "_":
        body.pop(0)
    while body and body[-1] == "_":
        body.pop()

    rubric, blocks = [], []
    cur = None

    def new_block():
        b = {"title": "", "cite": "", "source": "", "verses": [], "paras": []}
        blocks.append(b)
        return b

    for l in body:
        if l == "_":
            cur = None
            continue
        if l.startswith("$rubrica"):
            rubric.append(l[len("$rubrica"):].strip())
            continue
        if l.startswith("/:") and l.endswith(":/") and not l.startswith("/:«"):
            if cur is None and not blocks:
                rubric.append(l[2:-2].strip())
            else:
                (cur or new_block())["paras"].append("(" + l[2:-2].strip() + ")")
            continue
        if cur is None:
            cur = new_block()
        if l.startswith("!"):
            ref = l[1:].strip()
            if re.match(r"^(Commemoratio|Commemoration)\b", ref):
                if cur["verses"] or cur["paras"] or cur["title"]:
                    cur = new_block()
                cur["title"] = ref
            elif _CITE.match(ref):
                cur["cite"] = ref.rstrip(".").strip()
            else:
                cur["source"] = ref
            continue
        m = re.match(r"^(\d+) (.*)$", l)
        if m and (cur["cite"] or cur["verses"] or not cur["paras"]):
            cur["verses"].append([int(m.group(1)), _tidy(m.group(2))])
            continue
        if l.startswith("r. "):  # red initial: same as "v." for our purposes
            l = "v. " + l[3:]
        if l.startswith("v. "):
            if _CITE.match(l[3:]) and not cur["cite"] and not cur["paras"] and not cur["verses"]:
                cur["cite"] = l[3:].rstrip(".").strip()  # citation missing its "!" in the source
            else:
                cur["paras"].append(_tidy(l[3:]))
            continue
        if (not cur["paras"] and not cur["verses"] and not cur["cite"] and not cur["source"]
                and len(cur["title"]) + len(l) <= TITLE_MAX):
            cur["title"] = (cur["title"] + " " + _tidy(l)).strip()
        elif cur["verses"] and not cur["paras"]:
            # Text after numbered verses (e.g. "Jerúsalem, convértere ..."):
            cur["paras"].append(_tidy(l))
        else:
            cur["paras"].append(_tidy(l))

    responsory = []
    for l in resp:
        if not l or l in ("_", "$Tu autem"):
            continue
        if l.startswith("&Gloria"):
            responsory.append(["G", GLORIA1[lang]])
        elif l.startswith("* ") and responsory and responsory[-1][0] == "R":
            responsory[-1][2] = _tidy(l[2:])
        elif l.startswith("R.br. "):  # short responsory (responsorium breve)
            t = _tidy(l[6:])
            rep = ""
            if " * " in t:
                t, rep = [x.strip() for x in t.split(" * ", 1)]
            responsory.append(["R", t, rep, "br"])
        elif l.startswith("R. "):
            t = _tidy(l[3:])
            rep = ""
            if " * " in t and not any(r[0] == "R" for r in responsory):
                t, rep = [x.strip() for x in t.split(" * ", 1)]
            responsory.append(["R", t, rep])
        elif l.startswith("V. "):
            t = _tidy(l[3:])
            if re.match(r"^(Glória Patri|Glory be to the Father)", t):
                responsory.append(["G", t])
            else:
                responsory.append(["V", t])
        elif responsory:
            responsory[-1][1] = (responsory[-1][1] + " " + _tidy(l)).strip()

    return {"rubric": rubric, "blocks": blocks, "responsory": responsory, "tedeum": tedeum}


HEBREW = re.compile(
    r"^(Aleph|Beth|Ghimel|Gimel|Daleth|He|Vau|Zain|Heth|Teth|Jod|Caph|Lamed|Mem|Nun|Samech|Ain|Phe|Sade|Coph|Res|Sin|Thau)\.\s")


def verses_as_prose(verses):
    """Verse texts run together without numbers. Lamentations keeps one line per
    verse, since each begins with its Hebrew letter."""
    lines = []
    for _, t in verses:
        if HEBREW.match(t) or not lines:
            lines.append(t)
        else:
            lines[-1] += " " + t
    return lines


def restore_verse_case(lesson, raw):
    """The engine capitalises the first letter of every numbered verse; put back
    the source's own casing, taken from the raw section text."""
    first = {}
    for line in raw.replace("\r", "").split("\n"):
        m = re.match(r"^(\d+)\s+(\S)", line.strip())
        if m:
            first.setdefault(int(m.group(1)), m.group(2))
    for b in lesson["blocks"]:
        for v in b["verses"]:
            c = first.get(v[0])
            if c and c.islower() and v[1][:1] == c.upper():
                v[1] = c + v[1][1:]
    return lesson


ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


def to_text(n, lesson, lang="latin", note="", numbers=False):
    """Render one parsed lesson as plain text."""
    word = "Lectio" if lang == "latin" else "Lesson"
    out = [f"{word} {ROMAN[n] if n < len(ROMAN) else n}" + (f" ({note})" if note else "")]
    for r in lesson["rubric"]:
        out.append(f"[{r}]")
    for b in lesson["blocks"]:
        if b["title"]:
            out.append(b["title"])
        if b["cite"]:
            out.append(b["cite"])
        if b["source"]:
            out.append(b["source"])
        if b["verses"]:
            if numbers:
                out.append(" ".join(f"{v} {t}" for v, t in b["verses"]))
            else:
                out.extend(verses_as_prose(b["verses"]))
        out.extend(b["paras"])
        out.append("")
    if out[-1] == "":
        out.pop()
    if lesson["responsory"]:
        out.append("")
        for item in lesson["responsory"]:
            if item[0] == "R":
                text = item[1] + (f" * {item[2]}" if item[2] else "")
                out.append(f"℟.{' br.' if len(item) > 3 else ''} {text}")
            elif item[0] == "V":
                out.append(f"℣. {item[1]}")
            elif item[0] == "G":
                out.append(f"℣. {item[1]}")
    if lesson["tedeum"]:
        out.append("")
        out.append("[Te Deum]" if lang == "latin" else "[Te Deum follows]")
    return "\n".join(out)
