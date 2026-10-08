# Matins readings (Divino Afflatu, 1954)

Every lesson and responsory of Matins from the Roman Breviary as it stood in
1954 (the "Divino Afflatu - 1954" version of Divinum Officium), in Latin and
English, arranged like the breviary: Proper of Time, Proper of Saints, Commons.

The texts come from this repository's data files (`web/www/horas/`). The
rubrics come from its engine (`web/cgi-bin/horas/`): nothing here re-implements
which lessons are read when. The engine is run for every day from 1950 to 2100,
and its output is traced back to the files the lessons live in.

## Outputs

| Path | What |
|------|------|
| `text/latin/`, `text/english/` | One plain-text file per office, in `temporale/`, `sanctorale/` and `commune/`, each with an `index.txt` in liturgical order. File names are the Divinum Officium file names (`Adv1-0` = First Sunday of Advent, `11-04` = 4 November, `C4` = Common of a Confessor Bishop, `111-3` = Wednesday of the first week of November). |
| `data/corpus.json` | The same content, structured: per entry, its title, rank, own lessons (title, scripture citation, patristic source, verses or paragraphs, responsory) and references to lessons read from elsewhere. Use this for the book, a web page or an app. |
| `output/Matins-Readings-1954.epub` | The whole corpus as one EPUB: Proper of Time, Common of the Saints, Proper of Saints (from 29 November), Latin and English side by side paragraph by paragraph, stacking on narrow screens. References link to the Common or feast they name. |
| `book/matins.sty`, `book/*.tex` | The print book: 6 × 9 in, Latin and English in two columns kept level paragraph by paragraph (LuaLaTeX, EB Garamond). `matins.sty` holds the page design; the `.tex` files are generated. `output/Winter-6x9.pdf`, `Spring-6x9.pdf`, `Summer-6x9.pdf`, `Autumn-6x9.pdf` are the four volumes, after the breviary's four parts (see below). |
| `data/coverage.txt` | Lesson sections that exist in the files but are never read under these rubrics (e.g. a Lenten saint's own 9th lesson, always replaced by the homily of the feria; sections for other rubrical editions). |

How an entry reads:

- **Temporal days** carry all their lessons. For August–November, the Scripture
  of each week is in the month files (`081-0` … `115-6`), as in the breviary.
- **Saints' days** carry their own lessons and say where the others come from,
  e.g. "Lessons I–III: from the Scripture of the day", "Lessons VII–VIII: from
  the Common of a Confessor Bishop (C4)", "Lesson IX: of Sts. Vitalis and
  Agricola (11-04cc)".
- **Commemorated saints** (e.g. `11-04cc`) carry the single lesson read for
  them as the last lesson of another office.
- **Commons** are printed in full from the Common files, including alternative
  sets ("in 2 loco"), whether or not a given year happens to use them.
- Responsories are as the engine gives them, with the Gloria Patri where it is
  said. "[Te Deum]" marks the lessons after which the Te Deum follows.
- Where the source has no English translation (112 lessons, nearly all
  alternative sets in the Commons), the English file says so and gives the Latin.

## Rebuilding

Requires Perl 5 (system Perl is fine) and Python 3.

```bash
matins/tools/harvest_years.sh 1950 2100     # ~10 min, parallel; writes matins/cache/harvest/
(cd web/www/horas/Latin && ls Tempora/*.txt Sancti/*.txt Commune/*.txt) > matins/cache/allfiles.txt
perl matins/tools/extract_files.pl < matins/cache/allfiles.txt > matins/cache/files.jsonl
python3 matins/tools/build_corpus.py        # writes text/ and data/
python3 matins/tools/build_epub.py          # writes output/Matins-Readings-1954.epub
python3 matins/tools/build_latex.py adv -o advent   # writes book/advent.tex (season ids: see the script)
python3 matins/tools/build_latex.py --volume winter # a whole breviary part: book/winter.tex (winter, spring, summer, autumn)
latexmk -lualatex -cd -outdir=build matins/book/advent.tex
```

`matins/cache/` is not committed. Re-run after pulling upstream changes to the
data files or the engine.

One day's Matins, straight from the engine:

```bash
PRETTY=1 perl matins/tools/harvest_day.pl 11-04-2026
```

## Tools

| File | Role |
|------|------|
| `tools/DOBoot.pm` | Loads the engine (`officium.pl`) unchanged for one date, replacing only its HTML output with a callback. |
| `tools/harvest_day.pl` | One date: asks the engine's own `lectio()` for each lesson of that day's Matins, Latin and English. |
| `tools/harvest_years.sh` | Runs `harvest_day.pl` for every day of a range of years. |
| `tools/extract_files.pl` | Every office file's sections as the engine resolves them for 1954 (conditionals, `@` inclusions, language layers). |
| `tools/lessons.py` | Parses lesson markup into a structure; renders plain text. |
| `tools/titles.py` | English titles for temporal days (the files name most of them only in Latin). |
| `tools/build_corpus.py` | Assigns each harvested lesson to its source file and writes the corpus. |
| `tools/layout.py` | Pairs Latin and English paragraph by paragraph for parallel layouts (EPUB, print). |
| `tools/build_epub.py` | Writes the EPUB from `data/corpus.json` (standard library only). |
| `tools/build_latex.py` | Writes LaTeX for the two-column print book, by season or whole. |

## The four volumes

The print book follows the four parts of the Breviarium Romanum. Each part
holds its season of the Proper of Time; the saints of every date that season
can reach, given Easter's five-week range; the Common lessons its own offices
refer to (and the Saturday-of-Our-Lady lessons for its Saturdays); and an
index. Where two parts meet, saints are printed in both, as in the 1942
edition (Pustet) these ranges were checked against.

| Part | Proper of Time | Proper of Saints |
|------|----------------|------------------|
| Hiemalis (Winter) | Advent, Christmastide, after Epiphany, Septuagesima | 26 Nov – 12 Mar |
| Verna (Spring) | Lent, Passiontide, Paschaltide, Octave of Pentecost | 7 Feb – 19 Jun |
| Aestiva (Summer) | Trinity Sunday – Sundays and ferias of August | 16 May – 3 Sep |
| Autumnalis (Autumn) | Sundays of September – before Advent; resumed Sundays after Epiphany | 28 Aug – 2 Dec |

Movable offices go in every part they can fall in, from the dates the engine
said them on (so Sundays XI–XV after Pentecost are in both Summer and Autumn,
as in the 1942 volumes).

## Known engine issue

On 19 Nov 2011, 20 Nov 2038 and 19 Nov 2095 (very late Easter: the 23rd
Sunday after Pentecost falls in the fourth week of November), the engine
produces empty lessons IV–VI. It is listed under `empty` in `data/corpus.json`
and should be reported upstream.
