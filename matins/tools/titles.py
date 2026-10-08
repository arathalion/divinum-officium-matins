"""English titles for Temporal days, which the source files name only in Latin."""

import re

ROMAN = {r: i for i, r in enumerate(
    "I II III IV V VI VII VIII IX X XI XII XIII XIV XV XVI XVII XVIII XIX XX XXI XXII XXIII XXIV".split(), 1)}
ORD = ["", "First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth", "Ninth", "Tenth",
       "Eleventh", "Twelfth", "Thirteenth", "Fourteenth", "Fifteenth", "Sixteenth", "Seventeenth",
       "Eighteenth", "Nineteenth", "Twentieth", "Twenty-first", "Twenty-second", "Twenty-third",
       "Twenty-fourth"]
FERIA = {"ii": "Monday", "iii": "Tuesday", "iv": "Wednesday", "v": "Thursday", "vi": "Friday",
         "secunda": "Monday", "tertia": "Tuesday", "quarta": "Wednesday", "quinta": "Thursday",
         "sexta": "Friday"}
SEASON = [
    (r"Adventus", "of Advent"),
    (r"in Quadragesima", "of Lent"),
    (r"post Epiphaniam", "after Epiphany"),
    (r"post Octavam Pentecostes", "after Pentecost"),
    (r"post Pentecosten", "after Pentecost"),
    (r"post Octavam Paschæ?e?", "after the Octave of Easter"),
    (r"post Pascha", "after Easter"),
]
FIXED = {
    "dominica pentecostes": "Pentecost Sunday",
    "dominica resurrectionis": "Easter Sunday",
    "dominica de passione": "Passion Sunday",
    "dominica in albis in octava paschæ": "Low Sunday (Octave of Easter)",
    "dominica in palmis": "Palm Sunday",
    "dominica in septuagesima": "Septuagesima Sunday",
    "dominica in sexagesima": "Sexagesima Sunday",
    "dominica in quinquagesima": "Quinquagesima Sunday",
    "dominica infra octavam ascensionis": "Sunday within the Octave of the Ascension",
    "feria quinta in cœna domini": "Maundy Thursday",
    "feria sexta in parasceve": "Good Friday",
    "sabbato sancto": "Holy Saturday",
    "sabbato in albis": "Saturday in Easter Week",
    "sabbato in vigilia pentecostes": "Vigil of Pentecost",
    "feria iv cinerum": "Ash Wednesday",
    "festum sanctissimi corporis christi": "Corpus Christi",
    "in ascensione domini": "The Ascension of Our Lord",
    "sacratissimi cordis domini nostri jesu christi": "The Most Sacred Heart of Our Lord Jesus Christ",
    "dominica sanctissimae trinitatis": "Trinity Sunday",
    "dominica sanctissimæ trinitatis": "Trinity Sunday",
    "sanctae familiae jesu mariae joseph": "The Holy Family of Jesus, Mary and Joseph",
    "sanctæ familiæ jesu mariæ joseph": "The Holy Family of Jesus, Mary and Joseph",
    "feria quarta in rogationibus in vigilia ascensionis": "Wednesday in Rogationtide, Vigil of the Ascension",
}
OCTAVE = [
    (r"Paschæ?e?", "Easter"), (r"Pentecostes", "Pentecost"), (r"Ascensionis", "the Ascension"),
    (r"Corporis Christi", "Corpus Christi"), (r"SSmi Cordis Jesu", "the Sacred Heart"),
    (r"Epiphani(æ|ae)", "the Epiphany"), (r"S\. Joseph", "St. Joseph"),
]
DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def _season(rest):
    for pat, en in SEASON:
        if re.fullmatch(pat, rest.strip(), re.I):
            return en
    return None


def _octave(rest):
    for pat, en in OCTAVE:
        if re.fullmatch(pat, rest.strip(), re.I):
            return en
    return None


def _num(tok):
    return ROMAN.get(tok.upper())


def english_tempora(latin):
    t = re.sub(r"\s+", " ", latin).strip()
    low = t.lower()
    if low in FIXED:
        return FIXED[low]
    m = re.fullmatch(r"Dominica (\w+) (.+)", t)
    if m and _num(m.group(1)) and _season(m.group(2)):
        return f"{ORD[_num(m.group(1))]} Sunday {_season(m.group(2))}"
    m = re.fullmatch(r"(?:Feria (\w+)|Sabbato)(?: (?:II|secunda))? infra Hebdomadam (\w+) (.+)", t)
    if m and _num(m.group(2)) and _season(m.group(3)):
        day = FERIA.get((m.group(1) or "").lower(), "Saturday")
        return f"{day} of the {ORD[_num(m.group(2))]} Week {_season(m.group(3))}"
    m = re.fullmatch(r"(?:Feria (\w+)|Sabbato) infra Hebdomadam (Septuagesim|Sexagesim|Quinquagesim)æ?a?e?", t)
    if m:
        return f"{FERIA.get((m.group(1) or '').lower(), 'Saturday')} after {m.group(2)}a Sunday"
    m = re.fullmatch(r"Dominica infra [Oo]ctavam (.+)", t)
    if m and (_octave(m.group(1)) or re.fullmatch(r"Epiphani(æ|ae)", m.group(1))):
        return f"Sunday within the Octave of {_octave(m.group(1)) or 'the Epiphany'}"
    m = re.fullmatch(r"(?:Feria (\w+)|Sabbato) infra Hebdomadam Passionis", t)
    if m:
        return f"{FERIA.get((m.group(1) or '').lower(), 'Saturday')} in Passion Week"
    m = re.fullmatch(r"Feria (\w+) Majoris Hebdomadæ", t)
    if m:
        return f"{FERIA[m.group(1).lower()]} in Holy Week"
    m = re.fullmatch(r"(?:Feria (\w+)|Sabbato) (?:Quattuor Temporum|post Cineres|Cinerum)(?: (in Adventu|Pentecostes|Quadragesim(?:æ|ae)|Septembris))?", t)
    if m:
        day = FERIA.get((m.group(1) or "").lower(), "Saturday")
        if "Cine" in t:
            return f"{day} after Ash Wednesday"
        season = {"in Adventu": "of Advent", "Pentecostes": "of Pentecost", "Quadragesimæ": "of Lent",
                  "Quadragesimae": "of Lent", "Septembris": "of September"}.get(m.group(2), "")
        return f"Ember {day} {season}".strip()
    m = re.fullmatch(r"Feria (\w+) in Rogationibus", t)
    if m:
        return f"{FERIA[m.group(1).lower()]} in Rogationtide"
    m = re.fullmatch(r"(?:Feria (\w+)|Sabbato) (?:infra|post) (?:Hebdomadam post Ascensionem|Octavam Ascensionis)", t)
    if m:
        day = FERIA.get((m.group(1) or "").lower(), "Saturday")
        return f"{day} {'after' if 'post Octavam' in t else 'within'} the Octave of the Ascension" \
            if "Octavam" in t else f"{day} after the Ascension"
    m = re.fullmatch(r"(?:Feria (\w+)|Sabbato) infra [Oo]ctavam (.+)", t)
    if m and _octave(m.group(2)):
        return f"{FERIA.get((m.group(1) or '').lower(), 'Saturday')} within the Octave of {_octave(m.group(2))}"
    m = re.fullmatch(r"Die Octavæ? ?a?e? (.+)", t)
    if m and _octave(m.group(1)):
        return f"Octave Day of {_octave(m.group(1))}"
    m = re.fullmatch(r"Feria (\w+) in Octava Ascensionis", t)
    if m:
        return f"{FERIA[m.group(1).lower()]}, Octave Day of the Ascension"
    m = re.fullmatch(r"Die (\w+) [Ii]nfra [Oo]ctavam (.+)", t)
    if m and _num(m.group(1)) and _octave(m.group(2)):
        octave = _octave(m.group(2))
        if octave in ("Easter", "Pentecost"):  # these octaves begin on Sunday
            return f"{DAYS[_num(m.group(1)) - 1]} within the Octave of {octave}"
        return f"{ORD[_num(m.group(1))]} Day within the Octave of {octave}"
    return t


def nat_title(stem, latin, lang):
    """Tempora/NatDD: Christmastide Scripture read by date (DD December or January)."""
    m = re.fullmatch(r"Nat(\d\d)", stem)
    if not m:
        return None
    d = int(m.group(1))
    mon = ("Decembris", "December") if d >= 24 else ("Januarii", "January")
    m2 = re.search(r"cap\. (\d+)", latin or "")
    if lang == "latin":
        return f"Die {d} {mon[0]}" + (f": {latin}" if latin else "")
    return f"{d} {mon[1]}" + (f": Epistle to the Romans, chapter {m2.group(1)}" if m2 else "")
