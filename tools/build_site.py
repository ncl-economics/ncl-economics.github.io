"""Build the public series website from the RePEc paper records.

Run from the repository root after adding or editing a paper record:

    python3 tools/build_site.py

It reads every record in RePEc/nwc/wpaper/*.rdf and writes:
  index.html             series home page, newest paper first
  papers/<number>.html   one landing page per paper, with Google Scholar tags
  sitemap.xml, robots.txt

Nothing in RePEc/ is changed: the .rdf files stay the single source of truth.
"""
from __future__ import annotations

import html
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://ncl-economics.github.io"
SERIES = "Newcastle Economics Discussion Papers"
PUBLISHER = "Newcastle University Business School"
GROUP = "Economics Subject Group"
CONTACT = "econ.media@newcastle.ac.uk"
IDEAS_SERIES = "https://ideas.repec.org/s/nwc/wpaper.html"
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


# ---------------------------------------------------------------- ReDIF parsing
def parse_redif(text: str) -> list[dict]:
    """Return one dict per template; repeated fields (authors etc.) become lists."""
    records, cur, last = [], None, None
    for raw in text.splitlines():
        if not raw.strip():
            continue
        if raw[0] in " \t" and cur is not None and last:  # continuation line
            cur[last][-1] += " " + raw.strip()
            cur["_seq"][-1][1] += " " + raw.strip()
            continue
        m = re.match(r"([A-Za-z][A-Za-z0-9-]*):\s?(.*)$", raw)
        if not m:
            continue
        key, val = m.group(1).lower(), m.group(2).strip()
        if key == "template-type":
            cur = {}
            records.append(cur)
        if cur is None:
            continue
        cur.setdefault(key, []).append(val)
        cur.setdefault("_seq", []).append([key, val])
        last = key
    return records


def to_paper(rec: dict) -> dict:
    # Author-* fields belong to the Author-Name above them, so walk in file order
    authors = []
    for key, val in rec.get("_seq", []):
        if key == "author-name":
            authors.append({"name": val, "aff": ""})
        elif key == "author-workplace-name" and authors and not authors[-1]["aff"]:
            authors[-1]["aff"] = val
    first = lambda k: rec.get(k, [""])[0]
    y, _, m = first("creation-date").partition("-")
    return dict(
        number=first("number"), title=first("title"), abstract=first("abstract"),
        authors=authors, year=y, month=int(m) if m.isdigit() else 0,
        jel=first("classification-jel"), keywords=first("keywords"),
        pdf=first("file-url"), handle=first("handle"),
    )


def display_name(redif_name: str) -> str:
    """'Fusari, Francesco' -> 'Francesco Fusari'."""
    last, _, given = redif_name.partition(",")
    return f"{given.strip()} {last.strip()}".strip() if given else redif_name.strip()


def load_papers() -> list[dict]:
    papers = []
    for f in sorted((ROOT / "RePEc/nwc/wpaper").glob("*.rdf")):
        for rec in parse_redif(f.read_text(encoding="latin-1")):
            if rec.get("template-type", [""])[0].lower().startswith("redif-paper"):
                papers.append(to_paper(rec))
    return sorted(papers, key=lambda p: p["number"], reverse=True)


# ---------------------------------------------------------------- HTML
e = lambda s: html.escape(s, quote=True)

CSS = """
:root{--ink:#051435;--muted:#4a5670;--line:#d9dee8;--blue:#0073bc;--bg:#fff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--blue)} a:hover{color:var(--ink)}
.bar{height:6px;background:linear-gradient(90deg,#29b7ea,#0073bc 45%,#003a65 75%,#051435)}
header,main,footer{max-width:820px;margin:0 auto;padding:0 20px}
header{display:flex;align-items:center;gap:20px;padding-top:28px;padding-bottom:24px;border-bottom:1px solid var(--line)}
header img{width:150px;height:auto;display:block}
header .s{font-weight:600;font-size:1.05rem;line-height:1.3}
header .s small{display:block;font-weight:400;color:var(--muted);font-size:.85rem}
header a{color:inherit;text-decoration:none}
main{padding-top:32px;padding-bottom:48px}
h1{font-family:Georgia,"Times New Roman",serif;font-weight:700;font-size:1.9rem;line-height:1.25;margin:0 0 12px}
.lead{color:var(--muted);margin:0 0 28px;max-width:640px}
ol.papers{list-style:none;margin:0;padding:0}
ol.papers li{padding:18px 0;border-top:1px solid var(--line)}
.num{font-size:.8rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.t{font-family:Georgia,"Times New Roman",serif;font-size:1.2rem;line-height:1.35;margin:2px 0 4px;display:block}
.au{color:var(--muted);font-size:.95rem}
.meta{color:var(--muted);font-size:.9rem;margin:0 0 20px}
.authors{margin:18px 0 22px;padding:0;list-style:none}
.authors li{margin:0 0 6px}.authors span{color:var(--muted);font-size:.92rem}
.btn{display:inline-block;background:var(--ink);color:#fff;text-decoration:none;padding:10px 18px;border-radius:4px;font-weight:600}
.btn:hover{background:var(--blue);color:#fff}
h2{font-size:.85rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:32px 0 8px}
.abs{font-family:Georgia,"Times New Roman",serif;font-size:1.05rem;line-height:1.65}
dl{display:grid;grid-template-columns:max-content 1fr;gap:6px 18px;margin:0;font-size:.95rem}
dt{color:var(--muted)} dd{margin:0}
.cite{background:#f4f6fa;border-left:3px solid var(--blue);padding:12px 16px;font-size:.92rem}
footer{border-top:1px solid var(--line);padding-top:20px;padding-bottom:40px;color:var(--muted);font-size:.85rem}
@media (max-width:560px){header{flex-direction:column;align-items:flex-start;gap:12px}h1{font-size:1.5rem}}
"""


def page(title: str, head_extra: str, body: str, depth: int) -> str:
    up = "../" * depth
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
{head_extra}
<style>{CSS}</style>
</head>
<body>
<div class="bar"></div>
<header>
  <a href="{up}index.html"><img src="{up}tools/ncl-logo.jpg" alt="Newcastle University"></a>
  <div class="s"><a href="{up}index.html">{SERIES}</a><small>{GROUP}, {PUBLISHER}</small></div>
</header>
<main>
{body}
</main>
<footer>
  {SERIES} &middot; {GROUP}, {PUBLISHER}, 5 Barrack Road, Newcastle upon Tyne, NE1 4SE, United Kingdom<br>
  Also listed on <a href="{IDEAS_SERIES}">RePEc/IDEAS</a> &middot; Contact: <a href="mailto:{CONTACT}">{CONTACT}</a><br>
  Discussion papers present preliminary research to stimulate discussion. Views are those of the authors.
</footer>
</body>
</html>
"""


def authors_text(p: dict) -> str:
    names = [display_name(a["name"]) for a in p["authors"]]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def date_text(p: dict) -> str:
    return f"{MONTHS[p['month'] - 1]} {p['year']}" if p["month"] else p["year"]


def paper_page(p: dict) -> str:
    url = f"{SITE}/papers/{p['number']}.html"
    tags = [
        ("citation_title", p["title"]),
        *[x for a in p["authors"] for x in
          [("citation_author", a["name"])] + ([("citation_author_institution", a["aff"])] if a["aff"] else [])],
        ("citation_publication_date", f"{p['year']}/{p['month']:02d}" if p["month"] else p["year"]),
        ("citation_technical_report_institution", PUBLISHER),
        ("citation_technical_report_number", p["number"]),
        ("citation_series_title", SERIES),
        ("citation_pdf_url", p["pdf"]),
        ("citation_abstract_html_url", url),
        ("citation_language", "en"),
        *[("citation_keywords", k.strip()) for k in p["keywords"].split(",") if k.strip()],
        ("description", p["abstract"][:300]),
    ]
    head = "\n".join(f'<meta name="{n}" content="{e(v)}">' for n, v in tags if v)
    head += f'\n<link rel="canonical" href="{e(url)}">'
    auth_li = "\n".join(
        f'<li>{e(display_name(a["name"]))}{"<br><span>" + e(a["aff"]) + "</span>" if a["aff"] else ""}</li>'
        for a in p["authors"])
    cite = (f'{e(authors_text(p))} ({e(p["year"])}). &ldquo;{e(p["title"])}.&rdquo; '
            f'<em>{SERIES}</em> {e(p["number"])}, {GROUP}, {PUBLISHER}.')
    body = f"""<div class="num">Discussion Paper {e(p['number'])} &middot; {e(date_text(p))}</div>
<h1>{e(p['title'])}</h1>
<ul class="authors">
{auth_li}
</ul>
<a class="btn" href="{e(p['number'])}.pdf">Download PDF</a>
<h2>Abstract</h2>
<p class="abs">{e(p['abstract'])}</p>
<h2>Details</h2>
<dl>
  <dt>JEL codes</dt><dd>{e(p['jel'])}</dd>
  <dt>Keywords</dt><dd>{e(p['keywords'])}</dd>
  <dt>RePEc handle</dt><dd><a href="https://ideas.repec.org/p/{'/'.join(p['handle'].split(':')[1:3])}/{e(p['number'])}.html">{e(p['handle'])}</a></dd>
</dl>
<h2>Cite as</h2>
<p class="cite">{cite}</p>"""
    return page(f"{p['title']} | {SERIES} {p['number']}", head, body, depth=1)


def index_page(papers: list[dict]) -> str:
    items = "\n".join(
        f"""<li><div class="num">{e(p['number'])} &middot; {e(date_text(p))}</div>
<a class="t" href="papers/{e(p['number'])}.html">{e(p['title'])}</a>
<div class="au">{e(authors_text(p))}</div></li>""" for p in papers)
    body = f"""<h1>{SERIES}</h1>
<p class="lead">Working papers from the {GROUP} at {PUBLISHER}, sharing new research
in economics ahead of journal publication.</p>
<ol class="papers">
{items}
</ol>"""
    head = (f'<meta name="description" content="{e(SERIES)}: working papers from the {e(GROUP)}, '
            f'{e(PUBLISHER)}.">\n<link rel="canonical" href="{SITE}/">')
    return page(SERIES, head, body, depth=0)


def main() -> None:
    papers = load_papers()
    (ROOT / "papers").mkdir(exist_ok=True)
    for p in papers:
        (ROOT / "papers" / f"{p['number']}.html").write_text(paper_page(p), encoding="utf-8")
    (ROOT / "index.html").write_text(index_page(papers), encoding="utf-8")
    today = date.today().isoformat()
    urls = [f"{SITE}/"] + [f"{SITE}/papers/{p['number']}.html" for p in papers]
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc><lastmod>{today}</lastmod></url>\n" for u in urls)
        + "</urlset>\n", encoding="utf-8")
    (ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n", encoding="utf-8")
    print(f"Built index.html and {len(papers)} paper page(s).")


if __name__ == "__main__":
    main()
