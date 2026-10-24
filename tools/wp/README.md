# Working paper submissions (zero-cost, runs on GitHub)

Colleagues submit a paper through a Microsoft Forms form with their
university account. A Power Automate flow (included in Microsoft 365) files
it as a GitHub issue; GitHub Actions turn it into the RePEc record, add the
series cover page, commit the files to this repository (which is the live
archive) and e-mail Marketing & Communication. Nothing is hosted and nothing
is paid for: Actions are free on public repositories.

```
colleague ─── Microsoft Forms ──▶ Power Automate ──▶ GitHub issue #N ──▶ bot comment: RePEc record preview
             (or the GitHub issue form directly)
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

Colleagues fill in a **Microsoft Forms** form with their university account
(no GitHub account needed). A Power Automate flow files the submission in
GitHub as an issue, and the rest is automatic. See *Microsoft Forms front
door* below for the one-time setup of the form and the flow.

Anyone with a GitHub account can also use the GitHub form directly:
https://github.com/ncl-economics/ncl-economics.github.io/issues/new?template=working-paper.yml

Either way, within a minute a comment under the issue shows the RePEc record
that will be published, the paper number, and whether the PDF could be
fetched. If something is wrong, the editor edits the issue (three dots on
the first comment, *Edit*) and the preview updates.

## For the editor: approving

You get an e-mail for every new submission (from the flow, and from GitHub
if you watch the repository). Open the issue, check the preview comment
(record, number, and whether the PDF was fetched), then either add the
**approved** label on the issue, or
comment `/approve` (replying to the notification e-mail with `/approve` works
too). To change the number or any field first, edit the issue. To reject,
close the issue with a comment.

Publishing takes two to three minutes. The issue then gets a closing comment
with the links, and the label **published**. If anything fails, the issue
gets a comment linking to the log; fix the fields and re-add the label.

## One-time setup

### 1. Labels and workflows

Labels `submission`, `approved`, `published` exist on the repository and the
workflows run from `main`. Nothing to do.

### 2. Microsoft Forms front door

Build this once, signed in as the account that will own the form and the
flow (your own account, or a full account for econ.media@newcastle.ac.uk if
IT gives it a licence; a plain shared mailbox cannot own forms).

**The form** (forms.office.com → New form → "Newcastle Economics Discussion
Papers: submit a paper"). Settings: *Only people in my organization can
respond*, *Record name*. Six questions:

| # | Question | Type |
|---|---|---|
| 1 | Title | Text, required |
| 2 | Author names | Text, **Long answer**, required. Subtitle: "One per line, in the order on the paper: Surname, First names" |
| 3 | Author e-mails | Text, Long answer. Subtitle: "One per line, same order as the names (leave a line blank to skip an author)" |
| 4 | Author affiliations | Text, Long answer, required. Subtitle: "One per line, same order as the names; one line if it is the same for everyone" |
| 5 | Abstract | Text, Long answer, required |
| 6 | Paper PDF | **File upload**, PDF only, 1 file, required. Subtitle: "Without a cover page; it is added automatically" |

Everything else is filled in automatically: the date is the month of
submission, the page count comes from the PDF, the number is the next free
one, and the responder's university e-mail is the contact. JEL codes,
keywords, a different date or RePEc Short-IDs can be added by the editor on
the issue before approving (add a `### JEL codes` section and the codes).

**The flow** (make.powerautomate.com → Create → Automated cloud flow). Every
action below is a *Standard* connector, included in Microsoft 365.

1. Trigger **Microsoft Forms: When a new response is submitted**. Form: the one above.
2. **Microsoft Forms: Get response details**. Form: same. Response Id: *Response Id* from the trigger.
3. **Parse JSON**. Content: the *Paper PDF* answer from step 2. Schema:
   ```json
   {"type":"array","items":{"type":"object","properties":{"name":{"type":"string"},"link":{"type":"string"},"id":{"type":"string"},"type":{},"size":{"type":"integer"},"referenceId":{"type":"string"},"driveId":{"type":"string"},"status":{"type":"integer"},"uploadSessionUrl":{}},"required":["name","id"]}}
   ```
4. **OneDrive for Business: Create share link**. File: `id` from step 3
   (Power Automate wraps this in *Apply to each*, which is fine). Link type:
   **View**. Link scope: **Anonymous**. This gives a link the publishing step
   can download without signing in. If "Anonymous" is refused by the
   university's sharing policy, pick *Organization* instead: the issue is
   still created, and the editor then drags the PDF into the issue before
   approving (the preview comment says when this is needed).
5. **GitHub: Create an issue**. Sign in with the GitHub account that will
   appear as the submitter (your own). Repository owner `ncl-economics`,
   repository `ncl-economics.github.io`. Title:
   `[WP] ` followed by the *Title* answer. Body: paste the block below and
   replace each `<...>` with the matching answer from step 2 (and the *Web URL*
   from step 4). Keep the `###` lines and the blank lines exactly.
   ```
   ### Title

   <Title>

   ### Author names

   <Author names>

   ### Author e-mails

   <Author e-mails>

   ### Author affiliations

   <Author affiliations>

   ### Abstract

   <Abstract>

   ### Paper PDF

   <Web URL from Create share link>

   ### Contact e-mail

   <Responders' Email>
   ```
   Labels: `submission` if the action offers a labels field; otherwise leave
   it, the preview workflow adds the label.
6. **Office 365 Outlook: Send an email (V2)**, so the editor hears about it
   from the shared mailbox rather than from GitHub. To: `econ.media@newcastle.ac.uk`
   (and yourself). Subject: `New working paper submission: ` + *Title*. Body:
   "Review and approve here: " + *HTML URL* from step 5 (the issue link),
   plus the title and the responder's e-mail. To send *from* econ.media, the
   flow owner needs *Send as* rights on that mailbox; otherwise send from your
   own address.
7. Save, then submit a test response to the form. A `[WP]` issue appears in
   the repository with the preview comment under it.

### 3. E-mail to Marketing & Communication

The publishing workflow sends the hand-over e-mail itself when these are set
in *Settings → Secrets and variables → Actions*:

- Secrets `MAIL_USERNAME` and `MAIL_PASSWORD`: a Microsoft 365 mailbox with
  **Authenticated SMTP** enabled (ask IT to enable it for
  econ.media@newcastle.ac.uk and set a password; defaults are
  `smtp.office365.com`, port 587). Any other SMTP server works with the
  extra secrets `MAIL_SERVER` and `MAIL_PORT`.
- Variables `MARKETING_EMAILS` (comma-separated) and `ADMIN_EMAIL` (cc).

Until IT enables SMTP, the closing comment on each published issue contains
the ready-to-send e-mail text with the PDF link; forward it from Outlook.

### 4. Share the form

Put the Microsoft Forms link on the group's web page, in the group's Teams
channel, or on a Google Site as a button.

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
