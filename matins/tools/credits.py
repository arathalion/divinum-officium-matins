"""Credits for the EPUB and the print book, after Divinum Officium's own credits
page (web/www/horas/Help/credits.html).

Each section is (heading, [paragraphs]); "print_only" sections apply to the
typeset book alone (its typeface).
"""

# Who prepared this edition, e.g. "Prepared by ...". Left empty, the line is omitted.
EDITION_CREDIT = ""

CREDITS = [
    ("Divinum Officium", [
        "The texts, and the program that arranges them according to the rubrics, are the work "
        "of the Divinum Officium Project (divinumofficium.com), begun by the late Laszlo Kiss and "
        "continued by the Project's volunteers. Its code and data are available at "
        "github.com/DivinumOfficium/divinum-officium under the MIT License.",
    ]),
    ("Latin", [
        "The Latin text derives from the Ratisbon 1888 edition of the Breviarium Romanum, scanned "
        "by the University of St Michael's College, Toronto, amended from the 1906 edition, and "
        "corrected by Laszlo Kiss and the Project team against later printings: Pustet "
        "(Regensburg, 1943), Benziger Brothers (New York, 1945), Burns Oates & Washbourne "
        "(London, 1946), La Presse Catholique Panaméricaine (Montréal, 1943), and Desclée and "
        "Mame (1962).",
        "The accented text of the Sixto-Clementine Vulgate was supplied by Frère Romain-Marie of "
        "the Abbaye Saint-Joseph de Clairval, Flavigny-sur-Ozerain.",
    ]),
    ("English", [
        "Holy Scripture is given in the Douay-Rheims translation.",
        "The other lessons and the responsories are from the translation of the Roman Breviary "
        "by John, Marquess of Bute (edition of 1908), made available by the University of "
        "St Michael's College, Toronto.",
    ]),
    ("This edition", [
        "The arrangement of this edition follows the Divinum Officium program's choice of "
        "lessons for each day under the rubrics of 1954. Any errors in the arrangement are the "
        "editor's, not the Project's.",
    ]),
    ("Typeface", [
        "Set in EB Garamond, designed by Georg Duffner and Octavio Pardo, under the SIL Open "
        "Font License 1.1.",
    ]),
]

PRINT_ONLY = {"Typeface"}


def sections(print_book=False):
    out = []
    for heading, paras in CREDITS:
        if heading in PRINT_ONLY and not print_book:
            continue
        if heading == "This edition" and EDITION_CREDIT:
            paras = paras + [EDITION_CREDIT]
        out.append((heading, paras))
    return out
