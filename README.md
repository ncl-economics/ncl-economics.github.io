# ncl-economics.github.io

GitHub Pages site of the Economics Subject Group, Newcastle University
Business School. It hosts the RePEc archive of the **Newcastle Economics
Discussion Papers** (`RePEc:nwc:wpaper`).

| Path | Contents |
|---|---|
| `RePEc/nwc/` | Archive and series templates (`nwcarch.rdf`, `nwcseri.rdf`) and the yearly paper files in `wpaper/` |
| `papers/` | The PDFs, one per paper (`2026-01.pdf`, ...) |
| `render.yaml`, `fly.toml` | Hosting configuration for the portal (Render and Fly.io) |
| `tools/make_cover.py` | Prepends the series cover page to a paper PDF |
| `portal/` | The submission portal: colleagues submit a paper through a form, the editor approves it by e-mail link, and the portal commits the template and PDF here and notifies Marketing & Communication. See `portal/README.md` and `portal/DEPLOY.md` |

Series pages: [IDEAS](https://ideas.repec.org/s/nwc/wpaper.html),
[EconPapers](https://econpapers.repec.org/paper/nwcwpaper/).
