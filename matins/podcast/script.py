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


def chunks(text, limit=350):
    """Split long text at sentence ends so each piece stays well inside the model's input limit."""
    out, cur = [], ""
    for sent in re.split(r"(?<=[.;:?!])\s+", text):
        if cur and len(cur) + len(sent) > limit:
            out.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}".strip()
    if cur:
        out.append(cur)
    return out


def script(doc):
    seg = []

    def say(text, pause=0.35):
        for piece in chunks(clean(text)):
            seg.append([piece, 0.35])
        if seg:
            seg[-1][1] = pause

    d = datetime.date.fromisoformat(doc["date"])
    say(f"Matins for {d.strftime('%A')}, the {DAY_ORD[d.day]} of {d.strftime('%B')}.", 0.6)
    say(doc["title"]["local"] + ".", 1.2)
    comms = doc.get("commemorations") or []
    if comms:
        say("With a commemoration of " + " and ".join(c["local"] for c in comms) + ".", 1.2)

    nine = len(doc["lessons"]) >= 8
    for les in doc["lessons"]:
        n = les["number"]
        if nine and n in NOCTURN:
            say(NOCTURN[n] + ".", 1.0)
        kind = les.get("kind")
        say("Lesson." if kind else f"Lesson {ORD[n]}.", 0.7)
        t = les["translation"]
        for part in t["parts"]:
            if part.get("title"):
                say(clean(part["title"]).rstrip(".") + ".", 0.6)
            if part.get("verses"):
                say(" ".join(v["text"] for v in part["verses"]), 0.8)
            for p in part.get("paragraphs", []):
                say(p, 0.6)
        seg[-1][1] = 1.0
        resp = t.get("responsory") or []
        if resp:
            say("Responsory.", 0.5)
            for r in resp:
                if r["type"] == "respond":
                    say(" ".join(x for x in (r["text"], r.get("repeat", "")) if x), 0.6)
                elif r["type"] == "verse":
                    say("Verse. " + r["text"], 0.6)
                else:
                    say(r["text"], 0.6)
            seg[-1][1] = 1.4
        if t.get("te_deum"):
            say("Here follows the Te Deum.", 1.4)

    say("Thanks be to God.", 0.8)
    return seg


if __name__ == "__main__":
    doc = json.load(open(sys.argv[1], encoding="utf-8"))
    segs = script(doc)
    json.dump(segs, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(len(segs), "segments,", sum(len(s) for s, _ in segs), "characters")
