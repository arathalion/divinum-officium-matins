"""Turn a daily-data JSON document into a spoken script: [(text, pause_after_seconds)]."""

import datetime
import json
import re
import sys

ORD = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"]
NOCTURN = {1: "First Nocturn", 4: "Second Nocturn", 7: "Third Nocturn"}
DAY_ORD = ["", "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth",
           "eleventh", "twelfth", "thirteenth", "fourteenth", "fifteenth", "sixteenth", "seventeenth",
           "eighteenth", "nineteenth", "twentieth", "twenty-first", "twenty-second", "twenty-third",
           "twenty-fourth", "twenty-fifth", "twenty-sixth", "twenty-seventh", "twenty-eighth",
           "twenty-ninth", "thirtieth", "thirty-first"]


# Douay-Rheims spellings respelled for the voice only (the text itself is unchanged).
PRONOUNCE = [
    (r"Machab", "Maccab"),            # Machabees, Machabeus: hard "k"
    (r"Ezechi", "Ezeki"),             # Ezechiel, Ezechias
    (r"Melchisedech", "Melchisedek"),
    (r"\bHenoch\b", "Henok"),
    # Hard "ch" in Hebrew and Greek names; the voice otherwise reads them as in "church".
    # Each respelling was checked against the voice's own phonemes.
    (r"\bZacharias\b", "Zakka-ryus"),
    (r"\bMalachias\b", "Mala-kyus"),
    (r"\bBarachias\b", "Bara-kyus"),
    (r"\bMicheas\b", "Mykeeas"),
    (r"\bAchaia\b", "Akaya"),
    (r"\bAchaz\b", "Akaz"),
    (r"\bAntiochus\b", "Antiocus"),
    (r"\bMisach\b", "Mysak"),
    (r"\bSidrach\b", "Sidrak"),
    (r"\bEutyches\b", "Eutikeez"),
    (r"\bJoachin\b", "Joakin"),
    (r"\bMelchom\b", "Melkom"),
    (r"\bBarach\b", "Barak"),
    (r"\bAlmachius\b", "Almakkius"),
    (r"\bAchillas\b", "Akillas"),
    (r"\bMechtilde\b", "Mektilde"),
    (r"\bBacchides\b", "Bakkideez"),
    (r"\bChanaan", "Kanaan"),
    (r"\bCham\b", "Kam"),
    (r"\b([Pp])asch", r"\1ask"),           # Pasch, Paschal
    (r"\b([Cc])atechumen", r"\1atakyumen"),
    (r"\bRavenna\b", "Revenna"),        # stress on the second syllable, not "RAY-vuh-nuh"
    (r"Nabuchodonosor", "Nabukodonosor"),
    (r"æ", "ae"), (r"Æ", "Ae"), (r"œ", "oe"),
]


# Scripture references are printed "John i. 2" or "Matth. xiii. 41"; spoken as
# "John one, two" and "Matthew thirteen, forty-one" (no "chapter" or "verse").
_UNITS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
          "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_ROMAN = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}
_FIRST = {"1": "First", "2": "Second", "3": "Third", "4": "Fourth"}
BOOKS = {
    "Matth": "Matthew", "Matt": "Matthew", "Marc": "Mark", "Apoc": "Revelation", "Rev": "Revelation",
    "Rom": "Romans", "Cor": "Corinthians", "Gal": "Galatians", "Eph": "Ephesians", "Phil": "Philippians",
    "Col": "Colossians", "Thess": "Thessalonians", "Tim": "Timothy", "Tit": "Titus", "Heb": "Hebrews",
    "Jas": "James", "Pet": "Peter", "Isa": "Isaiah", "Jer": "Jeremiah", "Ezech": "Ezekiel", "Ezek": "Ezekiel",
    "Dan": "Daniel", "Gen": "Genesis", "Exod": "Exodus", "Lev": "Leviticus", "Num": "Numbers",
    "Deut": "Deuteronomy", "Judg": "Judges", "Prov": "Proverbs", "Eccles": "Ecclesiastes",
    "Eccl": "Ecclesiastes", "Ecclus": "Ecclesiasticus", "Cant": "Canticle of Canticles", "Wisd": "Wisdom",
    "Lam": "Lamentations", "Ps": "Psalm", "Zach": "Zechariah", "Soph": "Zephaniah", "Mich": "Micah",
    "Mal": "Malachi", "Hab": "Habakkuk", "Agg": "Aggeus", "Jon": "Jonas", "Neh": "Nehemiah", "Esth": "Esther",
    "Tob": "Tobias", "Bar": "Baruch", "Kings": "Kings", "Par": "Paralipomenon", "Paral": "Paralipomenon",
    "Esd": "Esdras", "Jos": "Josue", "Machab": "Machabees", "Mach": "Machabees",
    "John": "John", "Luke": "Luke", "Mark": "Mark", "Acts": "Acts", "Job": "Job", "Joel": "Joel", "Amos": "Amos",
    "Osee": "Osee", "Jude": "Jude", "Judith": "Judith", "Ruth": "Ruth", "Jonas": "Jonas", "Nahum": "Nahum",
    "Abdias": "Abdias", "Titus": "Titus", "Philemon": "Philemon",
}


def words(n):
    if n < 20:
        return _UNITS[n]
    if n < 100:
        return _TENS[n // 10] + ("-" + _UNITS[n % 10] if n % 10 else "")
    if n < 1000:
        return _UNITS[n // 100] + " hundred" + (" " + words(n % 100) if n % 100 else "")
    return str(n)


def roman(token):
    """Value of a Roman numeral, or None. A capital I misprinted for l ("Ixvi") reads as l."""
    t = token
    if len(t) > 1 and t[0] == "I" and t[1:2].islower():
        t = "l" + t[1:]
    t = t.lower()
    if not t or any(c not in _ROMAN for c in t):
        return None
    total = 0
    for a, b in zip(t, t[1:] + " "):
        v = _ROMAN[a]
        total += -v if _ROMAN.get(b, 0) > v else v
    return total


_VERSES = r"\d+[a-c]?(?:\s?[-–]\s?\d+[a-c]?)?(?:,\s?\d+[a-c]?(?:\s?[-–]\s?\d+[a-c]?)?)*"
_REF = re.compile(r"\b(?:([1-4]) )?(" + "|".join(sorted(BOOKS, key=len, reverse=True)) + r")\.? "
                  r"(I?[ivxlc]+)\.(?:\s?(" + _VERSES + "))?")


def _verses(v):
    v = re.sub(r"(\d+)[a-c]\b", r"\1", v)
    return re.sub(r"\d+", lambda m: words(int(m.group(0))), re.sub(r"\s?[-–]\s?", " to ", v))


def _ref(m):
    num, book, chap, verses = m.groups()
    c = roman(chap)
    if c is None:
        return m.group(0)
    name = BOOKS[book]
    if num == "4" and name not in ("Kings", "Machabees"):
        num = None  # a stray footnote number, not part of the book's name
    if num:
        name = f"{_FIRST[num]} {name}" if name in ("Corinthians", "Thessalonians", "Timothy", "Peter", "John", "Kings", "Machabees") \
            else f"{num} {name}"
    out = f"{name} {words(c)}"
    if verses:
        return f"{out}, {_verses(verses)}"
    # A chapter alone keeps its full stop only where a sentence ends ("Luke xii. and ..." does not).
    rest = m.string[m.end():]
    return out + ("." if not rest.strip() or rest.lstrip()[:1] in ")]\u201d\"'" or rest.lstrip()[:1].isupper() else "")


def references(s):
    s = _REF.sub(_ref, s)
    return re.sub(r"\bBk\. ([ivxlc]+)\.", lambda m: f"Book {words(roman(m.group(1)) or 0)}.", s)


# "Leo I." is "Leo the First", but a bare "I" is usually the pronoun, so it is only
# read as a number after a name that popes and kings bear.
REGNAL_NAMES = ("Leo Nicholas Martin Gregory Pius Clement Innocent John Paul Sixtus Urban Benedict Boniface Stephen "
                "Felix Celestine Sylvester Alexander Adrian Anastasius Agatho Callistus Calixtus Eugene Hilary "
                "Julius Lucius Mark Victor Zosimus Symmachus Siricius Damasus Eusebius Hormisdas Vigilius "
                "Pelagius Sabinian Honorius Vitalian Sergius Constantine Gelasius Marcellus Marcellinus "
                "Cornelius Fabian Silverius Theodore Zachary Valentine Charles Henry Louis Edward Philip "
                "Ferdinand Francis Frederick William Peter Joseph Pontian Anicetus").split()
_ROMAN_ONE = re.compile(r"\b((?:Pope|Saint|St\.|King|Emperor|Blessed) (?:" + "|".join(REGNAL_NAMES) + r")|(?:"
                        + "|".join(REGNAL_NAMES) + r")) I\b(\.?)(?=[,;:)\]]|\s*$|\s+[A-Z]|\s+[a-z])")


def _one(m):
    # After Pope, King or Emperor the name is certainly numbered; otherwise only before punctuation.
    # ("Saint John I saw" is the pronoun, so Saint and Blessed count only before punctuation.)
    titled = m.group(1).split(" ")[0] in ("Pope", "King", "Emperor")
    rest = m.string[m.end():]
    if not titled and not (rest[:1] in ",;:)]" or not rest.strip() or m.group(2)):
        return m.group(0)
    end = "." if m.group(2) and (not rest.strip() or rest.lstrip()[:1].isupper()) else ""
    return m.group(1) + " the First" + end


_ORDINALS = ["", "First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth", "Ninth", "Tenth",
             "Eleventh", "Twelfth", "Thirteenth"]


def ordinal(n):
    """Ordinal in words: 22 is "Twenty-Second"."""
    if n < len(_ORDINALS):
        return _ORDINALS[n]
    tens, unit = divmod(n, 10)
    if n < 20:
        return _UNITS[n].capitalize() + "th"
    if unit == 0:
        return _TENS[tens].capitalize()[:-1] + "ieth"
    return _TENS[tens].capitalize() + "-" + _ORDINALS[unit]


def _regnal(m):
    n = roman(m.group(2))
    if not m.group(2) or n is None or n < 2:
        return m.group(0)
    return f"{m.group(1)} the {ordinal(n)}"


def clean(s):
    s = references(s)
    s = _ROMAN_ONE.sub(_one, s)
    for pat, rep in PRONOUNCE:
        s = re.sub(pat, rep, s)
    s = re.sub(r"\bSts\.", "Saints", s)
    s = re.sub(r"\bSt\.", "Saint", s)
    s = re.sub(r"\b([A-Z][a-z]+) (X{0,3}(?:IX|IV|V?I{0,3}))\b\.?", _regnal, s)
    s = s.replace("(", "").replace(")", "").replace("[", "").replace("]", "")
    s = s.replace("*", "").replace("†", "")
    s = re.sub(r"\bAnd so on\.", "And so on.", s)
    return re.sub(r"\s+", " ", s).strip()


# Pauses (seconds). Each sentence is read on its own so it can be followed by a
# breath; long sentences are split at a colon or semicolon with a shorter one.
SENTENCE = 0.6
CLAUSE = 0.3
HEADING = 1.0      # after "Lesson one.", a title or "Responsory."
PART = 1.2         # after a block of text inside a lesson
LESSON = 2.0       # after a lesson and its responsory
NOCTURN_GAP = 2.5  # before a new Nocturn


def sentences(text, limit=300):
    """[(piece, pause)] for a passage: one piece per sentence, long ones split at ; or :."""
    out = []
    for sent in re.split(r"(?<=[.?!])\s+(?=[A-Z\u201c\"'(])", text):
        if len(sent) <= limit:
            out.append([sent, SENTENCE])
            continue
        cur = ""
        for clause in re.split(r"(?<=[;:])\s+", sent):
            if cur and len(cur) + len(clause) > limit:
                out.append([cur, CLAUSE])
                cur = clause
            else:
                cur = f"{cur} {clause}".strip()
        if cur:
            out.append([cur, SENTENCE])
    return out


def script(doc):
    seg = []

    def say(text, pause=SENTENCE):
        seg.extend(sentences(clean(text)))
        if seg:
            seg[-1][1] = pause

    def gap(pause):
        if seg:
            seg[-1][1] = max(seg[-1][1], pause)

    d = datetime.date.fromisoformat(doc["date"])
    say(f"Matins for {d.strftime('%A')}, the {DAY_ORD[d.day]} of {d.strftime('%B')}.", 0.8)
    say(doc["title"]["local"] + ".", PART)
    comms = doc.get("commemorations") or []
    if comms:
        say("With a commemoration of " + " and ".join(c["local"] for c in comms) + ".", PART)
    gap(LESSON)

    nine = len(doc["lessons"]) >= 8
    for les in doc["lessons"]:
        n = les["number"]
        if nine and n in NOCTURN:
            gap(NOCTURN_GAP)
            say(NOCTURN[n] + ".", HEADING)
        # Only the Nocturns are named; the lessons follow one another without announcement.
        t = les["translation"]
        for part in t["parts"]:
            if part.get("title"):
                say(clean(part["title"]).rstrip(".") + ".", HEADING)
            if part.get("verses"):
                say(" ".join(v["text"] for v in part["verses"]), PART)
            for p in part.get("paragraphs", []):
                say(p, PART)
        gap(PART)
        resp = t.get("responsory") or []
        if resp:
            say("Responsory.", HEADING)
            for r in resp:
                if r["type"] == "respond":
                    say(" ".join(x for x in (r["text"], r.get("repeat", "")) if x), PART)
                else:
                    say(r["text"], PART)
        gap(LESSON)
        if t.get("te_deum"):
            say("Here follows the Te Deum.", LESSON)

    # The Martyrology read at Prime today, which announces tomorrow.
    m = (doc.get("martyrology") or {}).get("translation")
    if m and m.get("entries"):
        gap(LESSON)
        say("The Martyrology, for tomorrow.", HEADING)
        if m.get("heading"):
            say(m["heading"], PART)
        for entry in m["entries"]:
            say(entry, PART)
        if m.get("closing"):
            say(m["closing"], PART)

    say("Thanks be to God.", 1.0)
    return seg


if __name__ == "__main__":
    doc = json.load(open(sys.argv[1], encoding="utf-8"))
    segs = script(doc)
    json.dump(segs, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(len(segs), "segments,", sum(len(s) for s, _ in segs), "characters")
