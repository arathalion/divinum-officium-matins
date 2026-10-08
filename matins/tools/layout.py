"""Pair the Latin and English of a lesson row by row, for parallel layouts
(the side-by-side EPUB and the two-column print book).

lesson_rows() returns a list of (kind, latin_items, english_items). Each side
is a list of items; most rows hold one item per side. Kinds:

  head      "Lectio I" / "Lesson I"
  rubric    a red note before the text ("Commemoratio Feriae")
  title     "De Isaía Prophéta", "Homilía sancti Gregórii Papæ"
  cite      a scripture reference ("Isa 1:1-3")
  source    a patristic source ("Homilia 9 in Evangelia")
  text      prose (scripture runs together without verse numbers)
  resp      responsory items: ("R", text, repetendum) / ("V", text) / ("G", text)
  note      an editorial note (missing translation)
  tedeum    "Te Deum" follows

Where the two languages have the same shape, each paragraph gets its own row so
they stay level; where they differ, the whole part goes in one row.
"""

from itertools import zip_longest

import lessons as L

HEAD = {"latin": "Lectio", "english": "Lesson"}


def _content(block):
    """Prose paragraphs of a block: verses run together, then paragraphs."""
    out = L.verses_as_prose(block["verses"]) if block["verses"] else []
    return out + list(block["paras"])


def _pair(kind, la, en, rows):
    if len(la) == len(en):
        for a, b in zip(la, en):
            rows.append((kind, [a], [b]))
    elif la or en:
        rows.append((kind, list(la), list(en)))


def lesson_rows(n, latin, english, note_la="", note_en="", untranslated=False):
    rows = []
    roman = L.ROMAN[n] if n < len(L.ROMAN) else str(n)
    rows.append(("head", [f"{HEAD['latin']} {roman}" + (f" ({note_la})" if note_la else "")],
                 [f"{HEAD['english']} {roman}" + (f" ({note_en})" if note_en else "")]))
    if untranslated:
        rows.append(("note", [], ["No English translation in the source files; the Latin is given."]))
    for a, b in zip_longest(latin["rubric"], english["rubric"]):
        rows.append(("rubric", [a] if a else [], [b] if b else []))

    lb, eb = latin["blocks"], english["blocks"]
    if len(lb) == len(eb):
        for a, b in zip(lb, eb):
            for k in ("title", "cite", "source"):
                if a[k] or b[k]:
                    rows.append((k, [a[k]] if a[k] else [], [b[k]] if b[k] else []))
            _pair("text", _content(a), _content(b), rows)
    else:
        # Different shapes: keep each language's blocks together in one row.
        rows.append(("text", [p for b in lb for p in _content(b)], [p for b in eb for p in _content(b)]))

    _pair("resp", latin["responsory"], english["responsory"], rows)
    if latin["tedeum"] or english["tedeum"]:
        rows.append(("tedeum", ["Te Deum"], ["Te Deum"]))
    return rows
