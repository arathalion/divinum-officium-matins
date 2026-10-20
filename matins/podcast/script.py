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
REGNAL = {"II": "the Second", "III": "the Third", "IV": "the Fourth", "V": "the Fifth", "VI": "the Sixth",
          "VII": "the Seventh", "VIII": "the Eighth", "IX": "the Ninth", "X": "the Tenth", "XI": "the Eleventh",
          "XII": "the Twelfth", "XIII": "the Thirteenth"}


# Douay-Rheims spellings respelled for the voice only (the text itself is unchanged).
PRONOUNCE = [
    (r"Machab", "Maccab"),            # Machabees, Machabeus: hard "k"
    (r"Ezechi", "Ezeki"),             # Ezechiel, Ezechias
    (r"Melchisedech", "Melchisedek"),
    (r"\bHenoch\b", "Henok"),
    (r"Nabuchodonosor", "Nabukodonosor"),
    (r"æ", "ae"), (r"Æ", "Ae"), (r"œ", "oe"),
]


def clean(s):
    for pat, rep in PRONOUNCE:
        s = re.sub(pat, rep, s)
    s = re.sub(r"\bSts\.", "Saints", s)
    s = re.sub(r"\bSt\.", "Saint", s)
    s = re.sub(r"\b([A-Z][a-z]+) (II|III|IV|V|VI|VII|VIII|IX|X|XI|XII|XIII)\b\.?",
               lambda m: f"{m.group(1)} {REGNAL[m.group(2)]}", s)
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
        kind = les.get("kind")
        say("Lesson." if kind else f"Lesson {ORD[n]}.", HEADING)
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
                elif r["type"] == "verse":
                    say("Verse. " + r["text"], PART)
                else:
                    say(r["text"], PART)
        gap(LESSON)
        if t.get("te_deum"):
            say("Here follows the Te Deum.", LESSON)

    say("Thanks be to God.", 1.0)
    return seg


if __name__ == "__main__":
    doc = json.load(open(sys.argv[1], encoding="utf-8"))
    segs = script(doc)
    json.dump(segs, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(len(segs), "segments,", sum(len(s) for s, _ in segs), "characters")
