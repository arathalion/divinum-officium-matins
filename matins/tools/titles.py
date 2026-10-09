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


# English names for feasts whose English file in Divinum Officium has no title.
FEASTS = {
    "In Dedicatione Basilicarum Ss. Apostolorum Petri et Pauli": "Dedication of the Basilicas of Sts. Peter and Paul",
    "In Præsentatione Beatæ Mariæ Virginis": "The Presentation of the Blessed Virgin Mary",
    "Domini Nostri Jesu Christi Regis": "Our Lord Jesus Christ the King",
    "In Dedicatione Archibasilicæ Ss. Salvatoris": "Dedication of the Archbasilica of the Most Holy Saviour",
    "In Dedicatione Basilicæ Ss. Salvatoris": "Dedication of the Basilica of the Most Holy Saviour",
    "In Commemoratione Omnium Fidelium Defunctorum": "The Commemoration of All the Faithful Departed",
    "Omnium Fidelium Defunctorum": "All the Faithful Departed",
    "In Commemoratione Omnium Defunctorum Ordinis nostri": "Commemoration of All the Departed of our Order",
    "Beatæ Mariæ Virginis a Rosario": "Our Lady of the Rosary",
    "Sacratissimi Rosarii Beatæ Mariæ Virginis": "The Most Holy Rosary of the Blessed Virgin Mary",
    "Sanctissimi Rosarii Beatæ Mariæ Virginis": "The Most Holy Rosary of the Blessed Virgin Mary",
    "Solemnitas SS. Rosarii Beatæ Mariæ Virginis": "Solemnity of the Most Holy Rosary of the Blessed Virgin Mary",
    "Maternitatis Beatæ Mariæ Virginis": "The Motherhood of the Blessed Virgin Mary",
    "S. Edmundi, Episcopi et Confessoris": "St. Edmund, Bishop and Confessor",
    "SS. Ursulae et Sociarum, Virginum et Martyrum": "Sts. Ursula and Companions, Virgins and Martyrs",
    "S. Mauritii, Abbatis et Confessoris": "St. Maurice, Abbot and Confessor",
    "S. Galgani, Eremitæ Ordinis Cisterciensis": "St. Galgano, Hermit of the Cistercian Order",
    "Omnium Sanctorum Ordinis Nostri": "All Saints of our Order",
    "S. Malachiæ, Episcopi et Confessoris": "St. Malachy, Bishop and Confessor",
    "Bb. Hieronimi, Valentini, Francisci, Hyacinthi et Sociorum Martyrum O. P.":
        "Bl. Jerome, Valentine, Francis, Hyacinth and Companions, Martyrs, O.P.",
    "S. Ludovici Bertrandi Confessoris O. P.": "St. Louis Bertrand, Confessor, O.P.",
    "Festivitas Omnium Sanctorum OP": "All Saints of the Order of Preachers",
    "Dedicatio Ecclesiæ Abb.": "Dedication of the Abbey Church",
    "Dedicatio Ecclesiæ Cath.": "Dedication of the Cathedral Church",
    "S. Galli Abbatis": "St. Gall, Abbot",
    "S. Æmiliani Abbatis": "St. Emilian, Abbot",
    "S. Odonis Abbatis": "St. Odo, Abbot",
    # Feasts of Our Lord and Our Lady
    "In Circumcisione Domini": "The Circumcision of Our Lord",
    "In Vigilia Epiphaniæ": "Vigil of the Epiphany",
    "In Epiphania Domini": "The Epiphany of Our Lord",
    "In Octava Epiphaniæ": "Octave Day of the Epiphany",
    "In Purificatione Beatæ Mariæ Virginis": "The Purification of the Blessed Virgin Mary",
    "In Apparitione Beatæ Mariæ Virginis Immaculatæ": "The Apparition of the Immaculate Virgin Mary",
    "In Annuntiatione Beatæ Mariæ Virginis": "The Annunciation of the Blessed Virgin Mary",
    "Inventione Sanctæ Crucis": "The Finding of the Holy Cross",
    "Beatæ Mariæ Virginis Reginæ": "The Queenship of the Blessed Virgin Mary",
    "In Visitatione Beatæ Mariæ Virginis": "The Visitation of the Blessed Virgin Mary",
    "In Commemoratione Beatæ Mariæ Virginis de Monte Carmelo": "Our Lady of Mount Carmel",
    "Sanctæ Mariæ Virginis ad Nives": "Our Lady of the Snows",
    "In Transfiguratione Domini Nostri Jesu Christi": "The Transfiguration of Our Lord Jesus Christ",
    "In Vigilia Assumptionis B.M.V.": "Vigil of the Assumption",
    "In Assumptione Beatæ Mariæ Virginis": "The Assumption of the Blessed Virgin Mary",
    "Immaculati Cordis Beatæ Mariæ Virginis": "The Immaculate Heart of the Blessed Virgin Mary",
    "In Nativitate Beatæ Mariæ Virginis": "The Nativity of the Blessed Virgin Mary",
    "S. Nominis Beatæ Mariæ Virginis": "The Holy Name of Mary",
    "In Exaltatione Sanctæ Crucis": "The Exaltation of the Holy Cross",
    "Septem Dolorum Beatæ Mariæ Virginis": "The Seven Sorrows of the Blessed Virgin Mary",
    "Beatæ Mariæ Virginis de Mercede": "Our Lady of Ransom",
    "Sanctæ Mariæ Sabbato": "Our Lady's Saturday",
    "In Conceptione Immaculata Beatæ Mariæ Virginis": "The Immaculate Conception of the Blessed Virgin Mary",
    "In Octava Concept. Immac. Beatæ Mariæ Virginis": "Octave Day of the Immaculate Conception",
    "In Vigilia Nativitatis Domini": "Vigil of the Nativity of Our Lord",
    "In Nativitate Domini": "The Nativity of Our Lord",
    # Commons
    "Commune Apostolorum": "Common of Apostles",
    "In Festis Beatae Mariae Virginis": "Feasts of the Blessed Virgin Mary",
    "Commune Evangelistarum": "Common of Evangelists",
    "Commune Evangelistarum tempore Paschali": "Common of Evangelists in Paschaltide",
    "Commune Plurimorum Martyrum Pontificum": "Common of Several Martyrs who were Bishops",
    "Commune Plurimorum Martyrum Tempore Paschali": "Common of Several Martyrs in Paschaltide",
    "Commune plurium Summorum Pontificum Martyrum Tempore Paschali":
        "Common of Several Martyrs who were Popes, in Paschaltide",
    "Commune plurium Confessorum non Pontificum": "Common of Several Confessors who were not Bishops",
}

OCTAVE_DAY = {"secunda": 2, "tertia": 3, "quarta": 4, "quinta": 5, "sexta": 6, "septima": 7}
OCTAVES = [
    (r"Epiphaniæ", "the Epiphany"),
    (r"S\. Assumptionis Beatæ Mariæ Virginis", "the Assumption"),
    (r"Concept(?:ionis|\.) Immac(?:ulatæ|\.) Beatæ Mariæ Virginis", "the Immaculate Conception"),
]


def octave_title(latin):
    """"Quarta die infra Octavam Epiphaniæ" / "De II die infra Octavam ..." in English."""
    m = re.fullmatch(r"(?:De )?(\w+) die infra Octavam (.+)", latin.strip())
    if not m:
        return None
    n = OCTAVE_DAY.get(m.group(1).lower()) or ROMAN.get(m.group(1).upper())
    for pat, en in OCTAVES:
        if n and re.fullmatch(pat, m.group(2)):
            return f"{ORD[n]} Day within the Octave of {en}"
    return None


def english_title(latin, english):
    """Best English title: a known feast name, else the given English, tidied
    (some source titles carry the rank after a semicolon)."""
    english = (english or "").split(";")[0].strip()
    if not english or english == latin:
        if latin in FEASTS:
            return FEASTS[latin]
        octave = octave_title(latin)
        if octave:
            return octave
    return english or latin
