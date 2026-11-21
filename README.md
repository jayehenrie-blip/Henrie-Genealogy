# The Henrie Family

A simple website for reading the Henrie family history, built from the "Red Book":
*Ancestry and Descendants of William Henrie, 1799–1883* by Manetta (Prince) Henrie (Provo, Utah, 1954),
electronic edition by Ryan Henrie (2002).

It is designed for older readers and phones: large text with an A−/A+ control, big buttons,
one person per screen, and plain words instead of the book's abbreviations.

## Four ways to look at each person

| View | What it shows |
| --- | --- |
| **Story** | Dates, places, marriages and the person's story from the book, with the book's page number |
| **Family** | Parents above, the person and their husband or wife, and children below. Tap anyone to move to them |
| **Ancestors** | A fan chart of parents, grandparents and great-grandparents, colored by line |
| **Journey** | The places of the person's life in order, on a map |

## Turning on the website (GitHub Pages)

1. In this repository, open **Settings → Pages**.
2. Under **Build and deployment**, choose **Deploy from a branch**, branch **main**, folder **/ (root)**, then **Save**.
3. After a minute the site is live at `https://<your-github-name>.github.io/<repository-name>/`.

The site is plain HTML, CSS and JavaScript. There is no build step and nothing to install.
To try it on your own computer, run `python3 -m http.server` in this folder and open http://localhost:8000.

## The family data

All of the family information lives in one standard genealogy file:
[`data/henrie.ged`](data/henrie.ged) (GEDCOM 5.5.1). The website reads it directly, so
editing that file updates the site. The same file can be imported into FamilySearch, Ancestry,
RootsMagic, Gramps and other genealogy programs.

* **The Red Book is the primary source.** Every person cites the book (`SOUR @S1@`) with its page numbers.
  Dates the book gives loosely, such as "25-26-28 Aug. 1831", are kept word for word as GEDCOM
  interpreted dates, for example `DATE INT AUG 1831 (25-26-28 Aug. 1831)`.
* **New research is added beside the book, never over it.** Add a new `SOUR` record for each new source
  (a census, an obituary, FamilySearch) and cite it on the facts it supports. Keep the book's own words.
* **Map positions** come from [`tools/places.json`](tools/places.json) (approximate town centers) and are
  written into the GEDCOM as `MAP / LATI / LONG` under each place.

### Privacy

This repository is public. People born in the last 100 years with no recorded death are marked
`_LIVING Y` in `data/henrie.ged` and show their name only: no dates, places or stories.
The complete file is kept privately and is not part of this repository.

### Rebuilding the GEDCOM from the book

The first version of the GEDCOM was made by a program that reads the book's text. The book follows a
regular pattern (a person's sketch, then a numbered list of children, with `*` marking a child who
has their own entry later), but the conversion is not perfect. Once people start correcting
`data/henrie.ged` by hand, edit that file directly instead of re-running the conversion.

```
pip install pypdf
python3 tools/extract_text.py red_book.pdf book.txt
python3 tools/redbook_to_gedcom.py book.txt henrie-full.ged data/henrie.ged
```

Known limits of the automatic conversion:

* When a person married more than once, children are assigned to a marriage from phrases like
  "and his second wife ... had 10 children". A few may land in the wrong marriage.
* Spouses' parents are kept as a note ("Parents: ...") rather than as linked people.
* The 14 photographs referred to in the book are not in the electronic edition.
* Spellings are kept as printed, including the book's own typos. Some years were mis-scanned in the
  electronic edition (for example "1361" for 1861). `python3 tools/check_gedcom.py data/henrie.ged`
  lists parents and children whose birth years don't make sense (about 36 today), as a to-do list for hand fixes.

## Files

```
index.html            the page
css/style.css         look and layout (phone first, light and dark)
js/gedcom.js          reads the GEDCOM file
js/app.js             the four views, search and text size
data/henrie.ged       the family (public copy)
vendor/leaflet/       map library (Leaflet 1.9.4, BSD-2-Clause); map tiles © OpenStreetMap contributors
tools/                conversion scripts and place coordinates
```
