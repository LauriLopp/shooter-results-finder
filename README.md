# Athlete results finder

A small local web app that looks through Estonian and international shooting
result sites and lists the competitions an athlete took part in for a chosen
period. Useful for example for a project or stipend application.

> **What it is – and what it is not.** The aim is to *find every competition*
> an athlete took part in, so nothing is forgotten. The results, ranks,
> categories and participant counts are read automatically from result files
> in many different layouts and **can contain mistakes**. Every row has a link
> to its source document: check the numbers there before you use them
> anywhere official.

For each result you get the **date(s), competition name, category / event, type** (individual, team) **,
result, rank, number of participants in that category, link and source**, plus
a **Notes** column that says when something needs a closer look.

## Starting it

You need [uv](https://docs.astral.sh/uv/). It installs Python and all libraries
automatically on the first start.

| System | How |
|---|---|
| Windows | double-click `start.bat` |
| Linux, macOS, WSL | `./start.sh` |
| any | `uv run results-scraper` |

A page opens in your browser (http://localhost:8501). Stop it with `Ctrl+C` in
the terminal.

1. Enter **up to five athletes** (first and last name; the birth year is
   optional and separates athletes with the same name).
2. Choose the **period** and press **Search**.
3. Each athlete gets a tab with a table and downloads for **Excel, PDF, CSV,
   TXT** and a **search log**. *Download all athletes (ZIP)* gives one folder
   per athlete.

The sidebar switches the language (English / Estonian), the sources, which
result types are shown and whether possible matches are shown.

The first search of a period downloads all result files and can take several
minutes (10–25 with SIUS switched on, see below). Everything is cached in
`~/.cache/results_scraper` (change with `RESULTS_SCRAPER_CACHE`), so later
searches – also for other athletes – take seconds.

## Sources

| Source | Role | How it is read |
|---|---|---|
| [laskurliit.ee](https://laskurliit.ee/tulemused-2026/) | **main source**; wins when the same result is on several sites | the yearly "Tulemused YYYY" pages (found from the site menu) and every PDF / XLS / XLSX protocol linked there |
| [protokollitaja.eu](https://protokollitaja.eu/) | additional | its public JSON interface (qualification and final scores per event) |
| [esc-shooting.org](https://esc-shooting.org/results) | additional | its public interface; each event's "Result Book" PDF |
| [results.sius.com](https://results.sius.com/Championships.aspx) | additional, **international championships only; off by default** (see below) | championship list → events → rank-list PDFs |

## What the result rows mean

**Types:** *Individual*, *Final*, *Team*, *Mixed team* – each is a separate row,
so a final and its qualification are two rows. A fifth type, **Not read**, is
explained below.

**Confirmed matches** (the main table). Names are compared without accents,
case or word order (`KASK Mari` = `Mari Kask`) and with a small tolerance for
transliteration of long names (`BELOZERSKAJA` / `BELOZERSKAYA`). Every word
you type must be found. If the source writes the name differently, the Notes
column shows how, e.g. *Name in source: Mari-Liis KASK*. Also confirmed:

* names whose spaces were lost in the document (`Liisa MariKÄRKÄNEN`);
* a misspelling in an event, when the same athlete is found with the correct
  spelling in *another* event of the same competition (Notes says so).

**Possible matches** (a separate table / sheet, can be hidden). The name is
close but not equal: one letter differs (`Merli` for `Kerli`) or a given name is
missing. The first or last name must match, so a sibling with the same surname
is never suggested. A stated birth year that differs excludes the row.

**Not read.** The athlete's name was found in a document (on a line that also
has a score), but no result could be read from it – the layout is too unusual.
The row has the competition, date and link; Notes quotes the line of text that
was found, so you can see the result and check it.

**Participants** = athletes with a score in that category (did-not-start and 0
are not counted); teams for team events; finalists for finals.

**Duplicates.** The same result on two sites is shown once – same type, same
score, overlapping dates and the same or a neighbouring rank (or the same field
size). The kept row is from the higher-priority source and Notes says where
else it was found.

## Trade-offs and known limitations

The tool favours *finding* competitions over being certain about every value.

**Reading results**

* Result files come in dozens of layouts (Estonian protocols, ISSF result
  books, Excel sheets, club spreadsheets, foreign protocols). Unusual layouts
  can give a wrong category name, a shifted score, a wrong rank or a wrong
  participant count. The link is there to check.
* Categories are shown as printed in the document, so the same event can be
  named differently at different competitions.
* When a protocol prints "QF" instead of ranks for finalists, they are ranked
  in list order.
* Participant counts depend on the document listing everyone. Tables cut off,
  merged with another table, or cup standings that combine several
  competitions can give counts that differ from the real field size.
* Scanned (image) PDFs have no text and cannot be read or searched at all.
  They are listed in the search log as errors with a "check manually" link –
  the athlete may have taken part there without it showing in the results.

**Finding the athlete**

* A misspelled name can be missed completely if it is too different, or shown
  only as a *possible match*.
* The "same athlete in another event" rule can, rarely, confirm a different
  athlete with a very similar name in the same competition.
* *Not read* rows only appear when **none** of the athlete's results in that
  document could be read; if some were read and others were not, the missing
  ones are not reported.
* A *Not read* row can be a false hit: the name is on a line with a number,
  but the line is not a result (e.g. a start list). Lines that name officials
  (kohtunik, žürii, referee, …) are skipped.
* Initials alone never match (`T.K.` does not match `Toomas Kask`), so a
  document that prints only initials is not found.

**Merging and dates**

* Duplicate detection is a heuristic. Two different results with the same
  score on the same days could be merged, and the same result could appear
  twice if the sites disagree too much (different score format or rank).
* A *Not read* row is dropped when another source has real results for the
  athlete on the same days (an athlete cannot be at two competitions at once).
* Dates come from the link text or the document. When neither has a date, the
  upload month is shown as `~MM.YYYY`.

**Sources**

* laskurliit.ee: only documents linked from the yearly result pages.
* protokollitaja.eu has no web address per competition, so its rows link to
  the site's front page.
* esc-shooting.org: only events that have a "Result Book" document.
* results.sius.com: only championships whose name looks international (ISSF,
  ESC, Grand Prix, …). SIUS limits request rates, so the tool waits between
  requests; a first search over many months takes a long time.
* **results.sius.com's `robots.txt` asks all automated clients not to access
  the site.** The source is therefore **off by default**; switching it on in
  the sidebar shows a warning. Use it only if you accept that, for short
  periods and not repeatedly. Many international championships are also found
  through esc-shooting.org result books.
* If a site changes its layout or interface, that source can stop working
  until the code is updated. Errors are shown in the search log.
* Downloaded result files are cached without expiry. If a site replaces a file
  under the same address with a corrected version, delete the cache folder to
  see it.

## Responsible use

The tool only reads public result pages and files. It identifies itself with
a User-Agent that links to this repository, caches every file so it is
downloaded once, and waits between requests to results.sius.com. Please keep
it that way: don't remove the throttling or the cache, and don't run it in
tight loops. The results are about real people, many of them minors: use the
output for its purpose (applications, an athlete's own records) and don't
publish collected data in bulk.

## Development

```
uv run pytest            # tests
uv run results-scraper   # start the app
```

Tests use short excerpts in the layouts of real result files; all names in the
tests are invented.

Code layout (`src/results_scraper/`):

| Part | What |
|---|---|
| `sources/` | one module per site: list competitions, load result tables |
| `parsing/` | PDF / Excel → text lines; parsers for Estonian protocols, ISSF result books, and a fallback for other layouts |
| `names.py` | name matching (confirmed / possible / text search) |
| `search.py`, `dedupe.py` | load every competition once, match all athletes, merge duplicates |
| `export.py`, `app.py` | Excel / PDF / CSV / TXT export, Streamlit interface |
| `net.py` | HTTP with cache, retries and per-site throttling |

When a parser change alters its output, bump `PARSER_VERSION` in
`parsing/__init__.py` so cached parse results are rebuilt.

protokollitaja.eu serves an incomplete certificate chain; the missing Let's
Encrypt intermediate certificate is shipped in `certs/`, so TLS verification
stays on.

## License

MIT – see [LICENSE](LICENSE). Fonts: DejaVu Sans (free license in
`src/results_scraper/fonts/`).
