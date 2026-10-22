"""Build a Newcastle Economics Discussion Paper cover and prepend it to an unchanged paper PDF.

Usage: python3 make_cover.py PAPER.pdf OUT.pdf [LOGO.svg|png]
Edit the PAPER dict below for each new paper.
"""
import sys, base64, mimetypes
from pathlib import Path
from playwright.sync_api import sync_playwright
import pypdf

PAPER = dict(
    title="Fiscal anticipation and inequality: the role of the monetary-fiscal mix",
    authors=[("Vedanta Dhamija", "Centre for Macroeconomics"),
             ("Francesco Fusari", "Newcastle University Business School"),
             ("Roshni Tara", "Centre for Macroeconomics")],
    number="2026-01",
    date="October 2026",
)

src, out = Path(sys.argv[1]), Path(sys.argv[2])
# White (reversed) logo, placed bottom-right on the dark part of the panel
logo = Path(sys.argv[3]) if len(sys.argv) > 3 else Path(__file__).with_name("ncl-logo-white.png")

# Page size taken from the paper so the cover matches it exactly
r = pypdf.PdfReader(str(src))
w_pt, h_pt = float(r.pages[0].mediabox.width), float(r.pages[0].mediabox.height)

def authors_html(a):
    return "".join(f'<div class="au"><div class="n">{n}</div><div class="af">{af}</div></div>' for n, af in a)

if logo and logo.exists():
    mime = mimetypes.guess_type(str(logo))[0] or "image/png"
    data = base64.b64encode(logo.read_bytes()).decode()
    logo_html = f'<img class="logo" src="data:{mime};base64,{data}">'
else:
    logo_html = '<div class="logo ph">Newcastle University<br>logo</div>'

html = f"""<html lang="en"><head><style>
@page {{ size: {w_pt}pt {h_pt}pt; margin: 0; }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
html, body {{ width:{w_pt}pt; height:{h_pt}pt; background:#fff; color:#051435; font-family:'Inter',sans-serif; }}
.page {{ position:relative; width:100%; height:100%; overflow:hidden; }}
.panel {{ position:absolute; inset:0;
  clip-path: polygon(71% 0, 100% 0, 100% 100%, 42% 100%);
  background: linear-gradient(160deg, #29b7ea 0%, #0073bc 40%, #003a65 72%, #051435 100%); }}
.brand {{ position:absolute; right:66pt; top:610pt; color:#fff; }}
.logo {{ display:block; width:158pt; height:auto; }}
.logo.ph {{ height:37pt; border:1pt dashed rgba(255,255,255,.7); font-size:8pt; line-height:1.3;
  display:flex; align-items:center; justify-content:center; text-align:center; }}
.brand .unit {{ font-size:8.5pt; font-weight:600; margin-top:5pt; }}
.title {{ position:absolute; left:56pt; top:100pt; width:330pt; text-wrap:balance;
  font-family:'Latin Modern Roman','LM Roman 10',serif; font-weight:700; font-size:18pt; line-height:1.28; color:#051435; }}
.meta {{ position:absolute; left:56pt; top:248pt; width:260pt; font-size:11pt; line-height:1.4; }}
.meta .au {{ margin-bottom:9pt; }}
.meta .n {{ font-size:12pt; font-weight:500; }}
.meta .af {{ font-size:9.5pt; color:#4a5670; }}
.meta .dp {{ margin-top:16pt; font-size:10pt; }}
.meta .dt {{ margin-top:4pt; font-size:10pt; }}
.addr {{ position:absolute; left:56pt; bottom:76pt; font-size:9.5pt; line-height:1.5; }}
.addr b {{ font-size:11pt; display:block; margin-bottom:8pt; }}
</style></head><body><div class="page">
<div class="panel"></div>
<div class="brand">{logo_html}</div>
<div class="title">{PAPER['title']}</div>
<div class="meta">{authors_html(PAPER['authors'])}
<div class="dp">Economics Discussion Paper {PAPER['number']}</div>
<div class="dt">{PAPER['date']}</div></div>
<div class="addr"><b>Economics Subject Group</b>Newcastle University Business School<br>5 Barrack Road<br>
Newcastle upon Tyne<br>NE1 4SE<br>United Kingdom</div>
</div></body></html>"""

tmp = out.with_suffix(".cover.pdf")
png = out.with_suffix(".cover.png")
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": round(w_pt * 4 / 3), "height": round(h_pt * 4 / 3)}, device_scale_factor=1.5)
    pg.set_content(html); pg.wait_for_timeout(300)
    pg.screenshot(path=str(png))
    pg.pdf(path=str(tmp), width=f"{w_pt/72:.4f}in", height=f"{h_pt/72:.4f}in", print_background=True)
    b.close()

wr = pypdf.PdfWriter()
wr.append(str(tmp))
wr.append(str(src))          # original pages, untouched
wr.add_metadata({"/Title": PAPER["title"], "/Author": ", ".join(n for n, _ in PAPER["authors"]),
                 "/Subject": f"Newcastle University Business School Economics Discussion Paper {PAPER['number']}"})
with open(out, "wb") as f: wr.write(f)
tmp.unlink()
print(f"{out}: {len(wr.pages)} pages; preview {png}")
