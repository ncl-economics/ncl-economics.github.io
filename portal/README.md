# Working Paper Portal

A small web application that lets colleagues submit a working paper through a
form, turns the submission into a RePEc (ReDIF) template, e-mails the series
editor a review link, and, on approval, commits the template and the PDF to the
GitHub repository that serves the RePEc archive and e-mails the Marketing &
Communication team so they can add the paper to the university website.

```
colleague ──form──▶ portal ──e-mail (review link)──▶ editor
                                                      │ approve
                       ┌──────────────────────────────┘
                       ▼
          commit to this repository                e-mail Marketing & Communication
          (RePEc/nwc/wpaper/nwc2026.rdf,            (title, authors, abstract,
           papers/2026-02.pdf, wpaper/index.html)     PDF attached, RePEc links)
                       │
                       ▼
          IDEAS / EconPapers mirror the archive (1–2 days)
```

## What the portal does

1. **Submission form** (`/`): title, abstract, date, pages, JEL codes,
   keywords, authors (name, e-mail, affiliation, RePEc Short-ID), PDF upload,
   notes. An optional shared access code keeps strangers out.
2. **Template generation**: a `ReDIF-Paper 1.0` record is built from the form,
   with the next free number for the year (`2026-02`, …). Numbers already in
   the archive's yearly file on GitHub and in earlier submissions are skipped.
3. **Notification**: the editor gets an e-mail with the template and a signed
   review link; the submitter gets a confirmation.
4. **Review page** (`/review/<token>`): shows the metadata and the PDF, lets
   the editor change the number, edit or regenerate the template, then
   **Approve & publish** or **Reject** (with a message to the submitter).
5. **Publishing**: the cover page is prepended with `tools/make_cover.py`,
   then one commit to this repository
   - appends the record to the yearly file (`RePEc/nwc/wpaper/nwc2026.rdf`),
   - adds the PDF (`papers/2026-02.pdf`),
   - keeps `RePEc/nwc/wpaper/index.html` linking to every `.rdf` file
     (RePEc's mirroring software follows those links).
6. **Hand-over**: Marketing & Communication receive an e-mail with the paper's
   details, the PDF attached, and the IDEAS / EconPapers links; the submitter
   is told the paper is out.
7. **Admin list** (`/admin`, HTTP basic auth): every submission, status, and a
   fresh review link for each.

The defaults match this repository's layout (`RePEc/nwc/nwcarch.rdf`,
`RePEc/nwc/nwcseri.rdf`, `RePEc/nwc/wpaper/nwc<year>.rdf`, `papers/<number>.pdf`);
every path is configurable. Authors are written in the archive's `Last, First`
form.

## Run it locally

```bash
cd portal
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
pip install pypdf playwright && playwright install chromium   # for the cover page step
cp .env.example .env            # edit at least SECRET_KEY, ADMIN_*, GITHUB_TOKEN, SMTP_*
set -a; . ./.env; set +a
uvicorn app.main:app --reload
```

Open <http://localhost:8000>. With `SMTP_HOST` empty, every e-mail is written
to `data/outbox/*.eml` instead of being sent, which is handy for trying the
flow end to end: submit a paper, open the review link from the `.eml`, approve.

Tests:

```bash
python -m pytest
```

## Configuration

All settings are environment variables; `.env.example` documents each one.
The important ones:

| Variable | Meaning |
|---|---|
| `BASE_URL` | Public address of the portal, used in the e-mailed links |
| `SECRET_KEY` | Signs the review links. Keep it secret and stable |
| `ADMIN_USER`, `ADMIN_PASSWORD` | Credentials for `/admin` |
| `SUBMIT_CODE` | Optional code colleagues must enter to submit |
| `ARCHIVE_CODE`, `SERIES_CODE`, `SERIES_NAME` | `nwc`, `wpaper`, the series name |
| `SITE_URL` | The GitHub Pages site, `https://ncl-economics.github.io` |
| `RDF_DIR`, `PDF_DIR`, `RDF_FILE_PATTERN`, `PDF_FILE_PATTERN` | Archive layout (defaults: `RePEc/nwc/wpaper/nwc{year}.rdf`, `papers/{number}.pdf`) |
| `GITHUB_TOKEN`, `GITHUB_REPO`, `GITHUB_BRANCH` | Fine-grained PAT with *Contents: read and write* on the archive repo |
| `SMTP_*`, `MAIL_FROM` | Outgoing mail. Leave `SMTP_HOST` empty to write to `data/outbox` |
| `ADMIN_EMAIL` | The editor who approves (receives the review link) |
| `MARKETING_EMAILS` | Marketing & Communication contact(s), comma-separated |
| `COVER_COMMAND` | Command that adds the cover page before publishing (default in `.env.example` calls `tools/make_cover.py`) |

### Cover page

Before publishing, the portal runs `COVER_COMMAND` with the uploaded PDF as
`{input}`, writes the paper's metadata (title, authors with affiliations,
number, date such as "October 2026") to a JSON file passed as `{meta}`, and
publishes `{output}`:

```
COVER_COMMAND=python3 ../tools/make_cover.py {input} {output} --meta {meta}
```

`tools/make_cover.py` needs `pypdf`, `playwright` and a Chromium (set
`CHROMIUM_PATH` to use a system browser). Leave `COVER_COMMAND` empty to
publish the PDF exactly as uploaded.

### GitHub token

Create a fine-grained personal access token (GitHub → Settings → Developer
settings → Fine-grained tokens) restricted to the archive repository with
**Contents: Read and write**. If the archive lives under an organisation,
create the token from an account with write access, or use a GitHub App.

### E-mail

Any SMTP server works. For Microsoft 365 use `smtp.office365.com`, port 587,
STARTTLS, and an account that has SMTP AUTH enabled (IT may need to enable it,
or provide a shared mailbox / relay). Transactional services (Postmark, Resend,
SendGrid) also expose SMTP credentials and are simpler to set up.

## Deploy

The app is a single process with a SQLite database and an uploads folder under
`DATA_DIR`, so it needs one persistent volume. Any of these works:

- **Docker** on a university VM (build from the repository root so the image
  includes `tools/`):
  ```bash
  docker build -f portal/Dockerfile -t wp-portal .
  docker run -d --name wp-portal -p 8000:8000 --env-file portal/.env -v wp-portal-data:/srv/data wp-portal
  ```
  Put it behind the university's reverse proxy (nginx, Apache) with HTTPS.
- **Fly.io / Railway / Render**: build from `portal/Dockerfile` with the
  repository root as context, attach a volume mounted at `/srv/data`, set the
  environment variables from `.env.example`.

Keep `data/` backed up: it holds the submission history and the original PDFs.

## RePEc notes

- The archive and series templates (`RePEc/nwc/nwcarch.rdf`, `nwcseri.rdf`)
  are created once; the portal only touches the yearly paper files. To
  regenerate them, run
  `python -m app.cli init-templates --name "..." --maintainer-name "..." --maintainer-email ... --provider-homepage ... --provider-institution RePEc:edi:dencluk`.
- RePEc discovers files by following the links in each directory's
  `index.html`, which is why the portal maintains `RePEc/nwc/wpaper/index.html`
  (a new yearly file is added to it automatically).
- After a commit, GitHub Pages republishes within about a minute. IDEAS and
  EconPapers mirror the archive on their own schedule, usually overnight, so
  the paper pages appear one or two days after approval. The e-mails already
  carry the final IDEAS and EconPapers links.
- Paper numbers are `YYYY-NN`; the handle is `RePEc:nwc:wpaper:YYYY-NN`. Once
  a number is published it must never be reused, which the portal enforces
  against both its own records and the archive file.

## Layout

```
portal/
├── app/
│   ├── main.py              routes (form, review, admin)
│   ├── config.py            settings from environment variables
│   ├── redif.py             ReDIF templates, numbering, index.html upkeep
│   ├── publish.py           approval pipeline: build files, commit, notify
│   ├── github_publisher.py  GitHub REST client (single-commit publishing)
│   ├── emailer.py           SMTP or dev outbox
│   ├── db.py                SQLite storage
│   ├── tokens.py            signed review links
│   ├── cli.py               archive/series template generator
│   ├── templates/           HTML pages
│   └── static/style.css
├── tests/                   pytest suite (form, review, publishing, GitHub client)
├── Dockerfile
├── requirements.txt
└── .env.example
```
