# Working paper submissions (zero-cost, runs on GitHub)

Colleagues submit a paper through a GitHub issue form. GitHub Actions turn
it into the RePEc record, add the series cover page, commit the files to this
repository (which is the live archive) and e-mail Marketing & Communication.
Nothing is hosted and nothing is paid for: Actions are free on public
repositories.

```
colleague ─── issue form ───▶ issue #N  ──▶ bot comment: RePEc record preview
                                   │
          editor adds label "approved" (or comments /approve, also by e-mail reply)
                                   │
                                   ▼
      Action: download PDF → add cover (tools/make_cover.py) → papers/2026-02.pdf
              append record to RePEc/nwc/wpaper/nwc2026.rdf, update index.html
              commit to main → GitHub Pages republishes → RePEc mirrors (1-2 days)
              e-mail Marketing & Communication (PDF attached) → close issue
```

## For colleagues: submitting a paper

1. Open **https://github.com/ncl-economics/ncl-economics.github.io/issues/new/choose**
   and pick *Submit a working paper*. A free GitHub account is needed.
2. Fill in the form. Authors go one per line as
   `Surname, First names; e-mail; affiliation; RePEc Short-ID`.
   Drag the PDF (without a cover page) into the *Paper PDF* box.
3. Submit. Within a minute a comment shows the RePEc record that will be
   published and the paper number. If something is wrong, edit the issue
   (three dots on the first comment, *Edit*); the preview updates.
4. The editor approves. The issue is closed with the links to the PDF, IDEAS
   and EconPapers.

## For the editor: approving

You get GitHub's e-mail for every new issue and for the preview comment.
Check the preview, then either add the **approved** label on the issue, or
comment `/approve` (replying to the notification e-mail with `/approve` works
too). To change the number or any field first, edit the issue. To reject,
close the issue with a comment.

Publishing takes two to three minutes. The issue then gets a closing comment
with the links, and the label **published**. If anything fails, the issue
gets a comment linking to the log; fix the fields and re-add the label.

## One-time setup

1. **Merge this branch into `main`.** Issue forms and workflows only work from
   the default branch.
2. **Labels**: `submission`, `approved`, `published` (created already; see
   *Issues → Labels*).
3. **E-mail to Marketing & Communication** (optional but recommended). In
   *Settings → Secrets and variables → Actions*:
   - Secrets `MAIL_USERNAME` and `MAIL_PASSWORD`: a Gmail address and an
     [app password](https://myaccount.google.com/apppasswords) (needs 2-step
     verification on that Google account). Any other SMTP server works with
     the extra secrets `MAIL_SERVER` and `MAIL_PORT` (SSL port, e.g. 465).
   - Variables `MARKETING_EMAILS` (comma-separated) and `ADMIN_EMAIL` (cc).
   Without these the closing comment on the issue contains the ready-to-send
   e-mail text for you to forward.
4. **Share the form link** with colleagues (step 1 above). It can go on the
   group's web page or a Google Site as a button.

## Layout and tests

```
.github/ISSUE_TEMPLATE/working-paper.yml   the submission form
.github/workflows/wp-preview.yml           preview comment on open/edit
.github/workflows/wp-publish.yml           publish on approval
.github/workflows/wp-tests.yml             runs the tests below
tools/wp/config.py      archive layout (codes, directories, site URL)
tools/wp/issue.py       reads the issue form body
tools/wp/redif.py       ReDIF record, numbering, index.html upkeep
tools/wp/pipeline.py    preview and publish steps
tools/wp/cli.py         entry points used by the workflows
tools/wp/tests/         pytest suite: python3 -m pytest -q tools/wp/tests
tools/make_cover.py     cover page (also usable by hand: --meta meta.json)
```

Numbers are `YYYY-NN`, assigned as the next free one in the year's file;
the form's *Paper number* field overrides it. A number already in the
archive is never reused.
