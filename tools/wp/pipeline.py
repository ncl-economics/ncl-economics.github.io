"""Preview and publish steps, run from the repository root by the workflows."""
from __future__ import annotations

import calendar
import json
import os
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

from .config import CONFIG, Config
from .issue import Submission, parse_submission
from .redif import (Paper, append_template, existing_numbers, next_number, paper_template,
                    update_index)

Downloader = Callable[[str, Path], None]


def read(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.exists() else None


def assign_number(sub: Submission, root: Path, cfg: Config = CONFIG) -> tuple[str, str | None]:
    """The paper number to use and, if it cannot be used, why."""
    taken = existing_numbers(read(root / cfg.rdf_path(f"{sub.year}-01")) or "")
    if sub.number:
        if sub.number in taken:
            return sub.number, f"Number {sub.number} is already published in the archive."
        if not sub.number.startswith(sub.year + "-"):
            return sub.number, f"Number {sub.number} does not match the paper's year {sub.year}."
        return sub.number, None
    return next_number(sub.year, taken, cfg.number_width), None


def make_paper(sub: Submission, number: str) -> Paper:
    return Paper(title=sub.title, authors=sub.authors, abstract=sub.abstract, number=number,
                 creation_date=sub.date, keywords=sub.keywords, jel=sub.jel,
                 length_pages=sub.pages)


def long_date(date: str) -> str:
    year, month = date.split("-")[:2]
    return f"{calendar.month_name[int(month)]} {year}"


def cover_metadata(sub: Submission, number: str) -> dict:
    return {"title": sub.title, "authors": [[a.name, a.workplace] for a in sub.authors],
            "number": number, "date": long_date(sub.date)}


# ---- preview ---------------------------------------------------------------

def preview_markdown(issue_body: str, root: Path, cfg: Config = CONFIG) -> str:
    sub = parse_submission(issue_body)
    out = ["<!-- wp-preview -->"]
    number, number_error = (assign_number(sub, root, cfg) if sub.date and not sub.errors
                            else ("", None))
    errors = sub.errors + ([number_error] if number_error else [])
    if errors:
        out.append("### Please fix the following before this can be published")
        out += [f"- {e}" for e in errors]
        out.append("")
        out.append("Edit the issue (the three dots at the top right of the first comment, "
                   "then *Edit*) and this preview will update.")
        return "\n".join(out) + "\n"
    template = paper_template(make_paper(sub, number), cfg)
    out += [
        f"Thank you. This will be published as **{number}** "
        f"(handle `{cfg.paper_handle(number)}`) once the editor approves it.",
        "",
        "RePEc record that will be added to the archive:",
        "",
        "```",
        template.rstrip(),
        "```",
        "",
        f"Files: `{cfg.rdf_path(number)}` and `{cfg.pdf_path(number)}` "
        f"(cover page added automatically).",
        "",
        "**For the editor:** add the `approved` label or comment `/approve` to publish. "
        "To change anything first, edit the issue; the preview updates. Close the issue to reject.",
    ]
    return "\n".join(out) + "\n"


# ---- publish ---------------------------------------------------------------

def default_download(url: str, dest: Path) -> None:
    """Fetch an issue attachment; retry with the Actions token if GitHub asks for auth."""
    headers = {"User-Agent": "wp-publish"}
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    attempts = [headers] + ([{**headers, "Authorization": f"Bearer {token}"}] if token else [])
    last: Exception | None = None
    for h in attempts:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=120) as r:
                dest.write_bytes(r.read())
            return
        except urllib.error.HTTPError as exc:  # 403/404 on a private attachment: retry with token
            last = exc
            if exc.code not in (401, 403, 404):
                raise
    raise ValueError(f"Could not download the PDF attachment ({last}). "
                     "Re-attach the file to the issue and approve again.")


def add_cover(src: Path, dest: Path, meta: dict, root: Path, cfg: Config = CONFIG) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        meta_file = Path(tmp) / "meta.json"
        meta_file.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        subprocess.run(["python3", str(root / cfg.cover_script), str(src), str(dest),
                        "--meta", str(meta_file)], check=True, timeout=600)
    preview = dest.with_suffix(".cover.png")  # make_cover.py's preview image; not for the archive
    if preview.exists():
        preview.unlink()


def marketing_email(sub: Submission, number: str, cfg: Config = CONFIG) -> tuple[str, str]:
    subject = f"New working paper: {sub.title} ({number})"
    body = (
        "Dear colleagues,\n\n"
        f"A new paper has been published in the {cfg.series_name} series and is ready to be "
        "announced on the university website.\n\n"
        f"Title: {sub.title}\n"
        f"Authors: {sub.author_names}\n"
        f"Number: {number}\n"
        f"Date: {long_date(sub.date)}\n"
        f"JEL codes: {sub.jel or '-'}\n"
        f"Keywords: {sub.keywords or '-'}\n\n"
        f"Abstract:\n{sub.abstract}\n\n"
        f"PDF (with the series cover): {cfg.pdf_url(number)}\n"
        f"IDEAS page (live within 1-2 days): {cfg.ideas_url(number)}\n"
        f"EconPapers page (live within 1-2 days): {cfg.econpapers_url(number)}\n\n"
        f"Contact for queries: {sub.contact or 'the series editor'}.\n"
    )
    return subject, body


def publish(issue_body: str, root: Path, cfg: Config = CONFIG, download: Downloader | None = None,
            cover: bool = True) -> dict:
    """Write the RePEc record, the PDF and the index into the checkout at ``root``.

    Returns a result dict (number, title, urls, e-mail subject/body). Raises
    ValueError with a readable message when the submission is not publishable.
    """
    download = download or default_download
    sub = parse_submission(issue_body)
    if sub.errors:
        raise ValueError("The submission is not complete:\n- " + "\n- ".join(sub.errors))
    number, number_error = assign_number(sub, root, cfg)
    if number_error:
        raise ValueError(number_error)

    rdf_file = root / cfg.rdf_path(number)
    pdf_file = root / cfg.pdf_path(number)
    if pdf_file.exists():
        raise ValueError(f"{cfg.pdf_path(number)} already exists in the archive.")

    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "upload.pdf"
        download(sub.pdf_url, raw)
        if not raw.read_bytes().startswith(b"%PDF"):
            raise ValueError("The attached file is not a PDF.")
        pdf_file.parent.mkdir(parents=True, exist_ok=True)
        if cover:
            add_cover(raw, pdf_file, cover_metadata(sub, number), root, cfg)
        else:
            pdf_file.write_bytes(raw.read_bytes())

    template = paper_template(make_paper(sub, number), cfg)
    rdf_file.parent.mkdir(parents=True, exist_ok=True)
    rdf_file.write_text(append_template(read(rdf_file), template), encoding="utf-8")
    index_file = root / cfg.rdf_index_path()
    index_file.write_text(update_index(read(index_file), [rdf_file.name], cfg.series_name),
                          encoding="utf-8")

    subject, body = marketing_email(sub, number, cfg)
    return {
        "number": number, "title": sub.title, "authors": sub.author_names,
        "handle": cfg.paper_handle(number), "pdf_url": cfg.pdf_url(number),
        "ideas_url": cfg.ideas_url(number), "econpapers_url": cfg.econpapers_url(number),
        "rdf_path": cfg.rdf_path(number), "pdf_path": cfg.pdf_path(number),
        "subject": subject, "email_body": body, "template": template,
    }
