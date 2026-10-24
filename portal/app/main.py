"""FastAPI application: submission form, review links, admin list."""
from __future__ import annotations

import logging
import re
import secrets
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import publish
from .config import Settings
from .db import Database, Submission
from .emailer import send_email
from .redif import (Author, Paper, clean, existing_numbers, next_number, paper_template,
                    valid_number)
from .tokens import make_token, read_token

log = logging.getLogger("wp-portal")
HERE = Path(__file__).parent
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    db = Database(settings.db_path)
    templates = Jinja2Templates(directory=str(HERE / "templates"))
    templates.env.globals.update(settings=settings)
    basic = HTTPBasic()

    app = FastAPI(title="Working Paper Portal", docs_url=None, redoc_url=None)
    app.state.settings = settings
    app.state.db = db
    app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")

    # ---- helpers ---------------------------------------------------------
    def render(request: Request, name: str, **ctx) -> HTMLResponse:
        status_code = ctx.pop("status_code", 200)
        return templates.TemplateResponse(request, name, ctx, status_code=status_code)

    def review_link(sub_id: str) -> str:
        return f"{settings.base_url}/review/{make_token(settings.secret_key, sub_id)}"

    def submission_from_token(token: str) -> Submission:
        sub_id = read_token(settings.secret_key, token, settings.token_max_age_days * 86400)
        sub = db.get(sub_id) if sub_id else None
        if not sub:
            raise HTTPException(status.HTTP_404_NOT_FOUND,
                                "This review link is invalid or has expired. "
                                "Open the admin page to get a fresh one.")
        return sub

    def require_admin(credentials: HTTPBasicCredentials = Depends(basic)) -> str:
        ok_user = secrets.compare_digest(credentials.username.encode(), settings.admin_user.encode())
        ok_pass = secrets.compare_digest(credentials.password.encode(),
                                         settings.admin_password.encode())
        if not (ok_user and ok_pass):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unauthorized",
                                headers={"WWW-Authenticate": "Basic"})
        return credentials.username

    def make_paper(sub: Submission) -> Paper:
        return Paper(title=sub.title, authors=sub.authors, abstract=sub.abstract,
                     number=sub.number or "", creation_date=sub.creation_date,
                     keywords=sub.keywords, jel=sub.jel, length_pages=sub.length_pages)

    def numbers_in_archive(year: int) -> set[str]:
        """Numbers already published in the archive's file for ``year`` (best effort)."""
        if not (settings.github_token and settings.github_repo):
            return set()
        try:
            gh = publish.GitHubPublisher(settings.github_token, settings.github_repo,
                                        settings.github_branch, settings.github_api)
            return existing_numbers(gh.get_text(settings.rdf_path(f"{year}-01")) or "")
        except Exception:  # noqa: BLE001 - the number is re-checked at approval anyway
            log.warning("Could not read the archive to propose a number", exc_info=True)
            return set()

    def assign_number(sub: Submission) -> None:
        taken = db.numbers_in_use() | numbers_in_archive(sub.year)
        sub.number = next_number(sub.year, taken, settings.number_width)

    def regenerate_template(sub: Submission) -> None:
        sub.template = paper_template(make_paper(sub), settings)

    # ---- public: submission form -----------------------------------------
    @app.get("/", response_class=HTMLResponse)
    def form(request: Request):
        return render(request, "form.html", errors=[], values={}, authors=[{}],
                      today=date.today().strftime("%Y-%m"))

    @app.post("/submit", response_class=HTMLResponse)
    async def submit(
        request: Request,
        submitter_name: str = Form(""),
        submitter_email: str = Form(""),
        title: str = Form(""),
        abstract: str = Form(""),
        keywords: str = Form(""),
        jel: str = Form(""),
        creation_date: str = Form(""),
        length_pages: str = Form(""),
        notes: str = Form(""),
        submit_code: str = Form(""),
        author_first: list[str] = Form([]),
        author_last: list[str] = Form([]),
        author_email: list[str] = Form([]),
        author_workplace: list[str] = Form([]),
        author_person: list[str] = Form([]),
        pdf: UploadFile | None = File(None),
    ):
        errors: list[str] = []
        values = dict(submitter_name=submitter_name, submitter_email=submitter_email,
                      title=title, abstract=abstract, keywords=keywords, jel=jel,
                      creation_date=creation_date, length_pages=length_pages, notes=notes)

        if settings.submit_code and not secrets.compare_digest(submit_code.strip(),
                                                               settings.submit_code):
            errors.append("The access code is not correct.")
        if not clean(submitter_name):
            errors.append("Your name is required.")
        if not _EMAIL_RE.match(submitter_email.strip()):
            errors.append("A valid contact e-mail is required.")
        if not clean(title):
            errors.append("The title is required.")
        if len(clean(abstract)) < 50:
            errors.append("The abstract is required (at least 50 characters).")
        if not re.match(r"^\d{4}-(0[1-9]|1[0-2])(-\d{2})?$", creation_date.strip()):
            errors.append("The date must be in the form YYYY-MM.")

        authors: list[Author] = []
        rows = max(len(author_first), len(author_last))
        pad = lambda lst: list(lst) + [""] * (rows - len(lst))  # noqa: E731
        for f, l, e, w, p in zip(pad(author_first), pad(author_last), pad(author_email),
                                 pad(author_workplace), pad(author_person)):
            if not (clean(f) or clean(l)):
                continue
            if not (clean(f) and clean(l)):
                errors.append("Each author needs both a first and a last name.")
            if e.strip() and not _EMAIL_RE.match(e.strip()):
                errors.append(f"The e-mail address for {f} {l} is not valid.")
            authors.append(Author(first=clean(f), last=clean(l), email=e.strip(),
                                  workplace=clean(w), person=p.strip()))
        if not authors:
            errors.append("At least one author is required.")

        pages: int | None = None
        if length_pages.strip():
            if length_pages.strip().isdigit() and int(length_pages) > 0:
                pages = int(length_pages)
            else:
                errors.append("The number of pages must be a positive whole number.")

        pdf_bytes = b""
        if pdf is None or not pdf.filename:
            errors.append("The PDF file is required.")
        else:
            pdf_bytes = await pdf.read()
            if not pdf_bytes.startswith(b"%PDF"):
                errors.append("The uploaded file is not a PDF.")
            elif len(pdf_bytes) > settings.max_pdf_mb * 1024 * 1024:
                errors.append(f"The PDF is larger than {settings.max_pdf_mb} MB.")

        if errors:
            author_dicts = [dict(first=a.first, last=a.last, email=a.email,
                                 workplace=a.workplace, person=a.person) for a in authors] or [{}]
            return render(request, "form.html", errors=errors, values=values,
                          authors=author_dicts, today=date.today().strftime("%Y-%m"),
                          status_code=400)

        sub = Submission(
            submitter_name=clean(submitter_name), submitter_email=submitter_email.strip(),
            title=clean(title), abstract=abstract.strip(), creation_date=creation_date.strip(),
            authors=authors, pdf_path="", pdf_original_name=pdf.filename,
            keywords=keywords.strip(), jel=jel.strip(), length_pages=pages, notes=notes.strip(),
        )
        pdf_file = settings.uploads_dir / f"{sub.id}.pdf"
        pdf_file.write_bytes(pdf_bytes)
        sub.pdf_path = str(pdf_file)
        assign_number(sub)
        regenerate_template(sub)
        db.insert(sub)

        link = review_link(sub.id)
        send_email(
            settings, [settings.admin_email],
            f"[WP portal] New submission: {sub.title}",
            f"A new working paper was submitted by {sub.submitter_name} "
            f"<{sub.submitter_email}>.\n\n"
            f"Title: {sub.title}\nAuthors: {sub.author_names}\n"
            f"Proposed number: {sub.number}\n\n"
            f"Review, edit and approve or reject it here:\n{link}\n\n"
            f"Notes from the submitter:\n{sub.notes or '-'}\n\n"
            f"Generated RePEc template:\n\n{sub.template}",
        )
        send_email(
            settings, [sub.submitter_email],
            f"Working paper submission received: {sub.title}",
            f"Dear {sub.submitter_name},\n\nThank you. Your paper \"{sub.title}\" has been "
            f"received and is awaiting approval by the series editor. You will get another "
            f"e-mail once it is published or if changes are needed.\n",
        )
        return RedirectResponse(f"/submitted/{sub.id}", status_code=status.HTTP_303_SEE_OTHER)

    @app.get("/submitted/{sub_id}", response_class=HTMLResponse)
    def submitted(request: Request, sub_id: str):
        sub = db.get(sub_id)
        if not sub:
            raise HTTPException(404)
        return render(request, "submitted.html", sub=sub)

    # ---- editor: review link --------------------------------------------
    @app.get("/review/{token}", response_class=HTMLResponse)
    def review(request: Request, token: str, message: str = ""):
        sub = submission_from_token(token)
        return render(request, "review.html", sub=sub, token=token, message=message,
                      errors=[], can_publish=bool(settings.github_token and settings.github_repo))

    @app.post("/review/{token}", response_class=HTMLResponse)
    def decide(request: Request, token: str, action: str = Form(...),
               number: str = Form(""), template: str = Form(""), decision_note: str = Form("")):
        sub = submission_from_token(token)
        errors: list[str] = []
        if sub.status != "pending":
            errors.append(f"This submission was already {sub.status}.")
            return render(request, "review.html", sub=sub, token=token, message="",
                          errors=errors, can_publish=False, status_code=409)

        number = number.strip()
        if not valid_number(number):
            errors.append("The paper number must look like 2026-01.")
        elif number != sub.number and number in db.numbers_in_use():
            errors.append(f"Number {number} is already used by another submission.")

        if not errors:
            number_changed = number != sub.number
            sub.number = number
            if action == "regenerate" or number_changed and not template.strip():
                regenerate_template(sub)
            elif template.strip():
                sub.template = template.replace("\r\n", "\n").strip() + "\n"
                if number_changed:
                    regenerate_template(sub)  # keep Number/Handle/File-URL consistent
            if f"Handle: {settings.paper_handle(sub.number)}" not in sub.template:
                errors.append("The template's Handle line does not match the paper number. "
                              "Click 'Regenerate template' or fix it by hand.")

        if errors:
            return render(request, "review.html", sub=sub, token=token, message="",
                          errors=errors, can_publish=True, status_code=400)

        if action in ("save", "regenerate"):
            db.update(sub)
            return render(request, "review.html", sub=sub, token=token,
                          message="Saved.", errors=[], can_publish=True)

        if action == "reject":
            sub.status = "rejected"
            sub.decided_at = publish_now()
            sub.decision_note = decision_note.strip()
            db.update(sub)
            send_email(
                settings, [sub.submitter_email],
                f"Working paper not accepted: {sub.title}",
                f"Dear {sub.submitter_name},\n\nYour submission \"{sub.title}\" was not "
                f"accepted for the {settings.series_name}.\n\n"
                f"Message from the editor:\n{sub.decision_note or '-'}\n\n"
                f"You are welcome to submit a revised version.\n",
                cc=[settings.admin_email],
            )
            return render(request, "decided.html", sub=sub)

        if action == "approve":
            db.update(sub)  # persist any edits first
            try:
                sub.commit_url = publish.publish_submission(settings, sub)
            except Exception as exc:  # noqa: BLE001 - surfaced to the editor
                log.exception("Publishing %s failed", sub.id)
                return render(request, "review.html", sub=sub, token=token, message="",
                              errors=[f"Publishing failed, nothing was changed: {exc}"],
                              can_publish=True, status_code=502)
            sub.status = "approved"
            sub.decided_at = publish_now()
            sub.decision_note = decision_note.strip()
            db.update(sub)
            return render(request, "decided.html", sub=sub)

        raise HTTPException(400, "Unknown action")

    @app.get("/review/{token}/pdf")
    def review_pdf(token: str):
        sub = submission_from_token(token)
        return FileResponse(sub.pdf_path, media_type="application/pdf",
                            filename=f"{sub.number or sub.id}.pdf")

    # ---- admin list ------------------------------------------------------
    @app.get("/admin", response_class=HTMLResponse)
    def admin(request: Request, user: str = Depends(require_admin)):
        subs = db.list()
        links = {s.id: review_link(s.id) for s in subs}
        return render(request, "admin.html", subs=subs, links=links)

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    return app


def publish_now() -> str:
    from .db import now_iso
    return now_iso()


app = create_app()
