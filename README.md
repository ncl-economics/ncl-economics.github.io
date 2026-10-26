# Newcastle Economics Discussion Papers – RePEc archive

This repository is the RePEc archive of the **Economics Subject Group,
Newcastle University Business School**. It is served as a website by GitHub
Pages at https://ncl-economics.github.io, and RePEc's services (IDEAS,
EconPapers, NEP, CitEc, the RePEc Author Service) mirror it from there.

| | |
|---|---|
| Archive handle | `RePEc:nwc` |
| Series | Newcastle Economics Discussion Papers, handle `RePEc:nwc:wpaper` |
| Provider | Newcastle University Business School, Economics Subject Group (`RePEc:edi:dencluk`) |
| Maintainer | Francesco Fusari, econ.media@newcastle.ac.uk |
| Archive URL read by RePEc | https://ncl-economics.github.io/RePEc/nwc/ |
| Series on IDEAS | https://ideas.repec.org/s/nwc/wpaper.html |
| Series on EconPapers | https://econpapers.repec.org/paper/nwcwpaper/ |

## Layout

```
.nojekyll                      tells GitHub Pages to serve files as they are
RePEc/nwc/
  nwcarch.rdf                  archive template (ReDIF-Archive): who we are, where the files live
  nwcseri.rdf                  series template (ReDIF-Series): the discussion paper series
  index.html                   directory listing RePEc follows to find the files above
  wpaper/
    nwc2026.rdf                paper templates (ReDIF-Paper) for 2026, one record per paper
    index.html                 directory listing RePEc follows to find the yearly files
papers/
  2026-01.pdf                  the papers, one PDF per number, cover page included
tools/
  make_cover.py                prepends the series cover page to a paper PDF
  ncl-logo-white.png, ncl-logo.jpg
```

RePEc's mirroring software does not list directories by itself: it reads
`index.html` in `RePEc/nwc/` and in `RePEc/nwc/wpaper/` and follows the
links there. Every `.rdf` file must therefore be linked from the
`index.html` of its directory.

## Adding a paper

1. **Number.** Papers are numbered `YYYY-NN` in order of publication within
   the year (`2026-01`, `2026-02`, ...). A number is never reused.
2. **Cover and PDF.** Edit the `PAPER` dictionary at the top of
   `tools/make_cover.py` (title, authors with affiliations, number, date),
   then run
   ```bash
   pip install playwright pypdf && playwright install chromium
   python3 tools/make_cover.py paper.pdf papers/2026-02.pdf
   ```
   The original pages are left untouched; the cover is added in front.
3. **Record.** Append a record to `RePEc/nwc/wpaper/nwcYYYY.rdf`, separated
   from the previous one by a blank line, following this layout
   (`Handle` last, every value on one line):
   ```
   Template-Type: ReDIF-Paper 1.0
   Author-Name: Surname, First names
   Author-Email: ...
   Author-Workplace-Name: ...
   Title: ...
   Abstract: ...
   Creation-Date: 2026-10
   File-URL: https://ncl-economics.github.io/papers/2026-02.pdf
   File-Format: Application/pdf
   Number: 2026-02
   Classification-JEL: C32, E62
   Keywords: keyword one, keyword two
   Handle: RePEc:nwc:wpaper:2026-02
   ```
   Repeat the three `Author-*` lines for each author. JEL codes and
   keywords are optional but NEP, which e-mails new papers to subscribers
   by field, uses the JEL codes to route them.
4. **New year.** The first paper of a year goes in a new file
   `nwcYYYY.rdf`; add a line for it to `RePEc/nwc/wpaper/index.html`.
5. **Commit and push to `main`.** GitHub Pages republishes within about a
   minute. IDEAS and EconPapers fetch the archive on their own schedule,
   usually overnight, so the paper's pages appear one or two days later at
   `https://ideas.repec.org/p/nwc/wpaper/2026-02.html` and
   `https://econpapers.repec.org/paper/nwcwpaper/2026-02.htm`.

After the pages are live, authors can claim the paper in the
[RePEc Author Service](https://authors.repec.org) so it shows on their
profiles. Google Scholar picks up IDEAS and EconPapers pages, which link to
the PDF here.

## Checking the archive

- RePEc's syntax checker: https://ideas.repec.org/cgi-bin/rrdcheck.pl?handle=RePEc:nwc
- IDEAS mirroring log: https://ideas.repec.org/n/checker/ (archive `nwc`)
- Series on EconPapers appears after the first successful mirroring run.

## Contact

Series editor: Francesco Fusari, econ.media@newcastle.ac.uk.
