"""The approval pipeline: build the files, commit them, notify people."""
from __future__ import annotations

import calendar
import json
import logging
import shlex
import subprocess
import tempfile
from pathlib import Path

from .config import Settings
from .db import Submission
from .emailer import send_email
from .github_publisher import GitHubPublisher
from .redif import append_template, existing_numbers, update_index

log = logging.getLogger("wp-portal.publish")


def build_files(settings: Settings, sub: Submission, pdf_bytes: bytes,
                existing_rdf: str | None, existing_index: str | None) -> dict[str, bytes]:
    """Return {repo path: content} for one approved submission (pure function)."""
    assert sub.number and sub.template
    rdf_path = settings.rdf_path(sub.number)
    pdf_path = settings.pdf_path(sub.number)
    if sub.number in existing_numbers(existing_rdf or ""):
        raise ValueError(f"Paper number {sub.number} already exists in {rdf_path}")

    files: dict[str, bytes] = {
        rdf_path: append_template(existing_rdf, sub.template).encode("utf-8"),
        pdf_path: pdf_bytes,
    }
    listed = [Path(rdf_path).name]
    if Path(pdf_path).parent == Path(rdf_path).parent:
        listed.append(Path(pdf_path).name)
    files[settings.rdf_index_path()] = update_index(
        existing_index, listed, settings.series_name).encode("utf-8")
    return files


def cover_metadata(sub: Submission) -> dict:
    """What tools/make_cover.py needs: title, authors with affiliation, number, long date."""
    year, month = sub.creation_date.split("-")[:2]
    long_date = f"{calendar.month_name[int(month)]} {year}"
    return {
        "title": sub.title,
        "authors": [[a.name, a.workplace] for a in sub.authors],
        "number": sub.number,
        "date": long_date,
    }


def apply_cover(settings: Settings, sub: Submission, pdf_bytes: bytes) -> bytes:
    """Run the optional COVER_COMMAND on the PDF and return the processed file.

    Placeholders in the command: {input} {output} {meta} (a JSON file with the
    cover metadata) {number} {title} {authors} {date}.
    """
    if not settings.cover_command:
        return pdf_bytes
    meta = cover_metadata(sub)
    with tempfile.TemporaryDirectory() as tmp:
        inp = Path(tmp) / "input.pdf"
        out = Path(tmp) / "output.pdf"
        meta_file = Path(tmp) / "meta.json"
        inp.write_bytes(pdf_bytes)
        meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
        argv = [
            a.format(input=str(inp), output=str(out), meta=str(meta_file), number=sub.number,
                     title=sub.title, authors=sub.author_names, date=meta["date"])
            for a in shlex.split(settings.cover_command)
        ]
        subprocess.run(argv, check=True, timeout=600)
        if not out.exists():
            raise RuntimeError("COVER_COMMAND finished but produced no output file")
        return out.read_bytes()


def marketing_message(settings: Settings, sub: Submission) -> tuple[str, str]:
    subject = f"New working paper: {sub.title} ({sub.number})"
    body = (
        f"Dear colleagues,\n\n"
        f"A new paper has been published in the {settings.series_name} series and is ready "
        f"to be announced on the university website.\n\n"
        f"Title: {sub.title}\n"
        f"Authors: {sub.author_names}\n"
        f"Number: {sub.number}\n"
        f"Date: {sub.creation_date}\n"
        f"JEL codes: {sub.jel or '-'}\n"
        f"Keywords: {sub.keywords or '-'}\n\n"
        f"Abstract:\n{sub.abstract}\n\n"
        f"PDF: {settings.pdf_url(sub.number)}\n"
        f"IDEAS page (live within 1-2 days): {settings.ideas_url(sub.number)}\n"
        f"EconPapers page (live within 1-2 days): {settings.econpapers_url(sub.number)}\n\n"
        f"The PDF is attached. Contact for queries: {sub.submitter_name} <{sub.submitter_email}>.\n"
    )
    return subject, body


def publish_submission(settings: Settings, sub: Submission,
                       gh: GitHubPublisher | None = None) -> str:
    """Commit the approved paper to the archive repo and send the notifications.

    Returns the commit URL. Raises on any failure before anything is changed in
    the submission record (the caller updates the record).
    """
    gh = gh or GitHubPublisher(settings.github_token, settings.github_repo,
                               settings.github_branch, settings.github_api)
    pdf_bytes = apply_cover(settings, sub, Path(sub.pdf_path).read_bytes())
    existing_rdf = gh.get_text(settings.rdf_path(sub.number))
    existing_index = gh.get_text(settings.rdf_index_path())
    files = build_files(settings, sub, pdf_bytes, existing_rdf, existing_index)
    commit_url = gh.commit_files(
        files, f"Add working paper {sub.number}: {sub.title}")
    log.info("Published %s -> %s", sub.number, commit_url)

    subject, body = marketing_message(settings, sub)
    attachments = []
    if len(pdf_bytes) <= 20 * 1024 * 1024:
        attachments.append((f"{sub.number}.pdf", pdf_bytes, "application/pdf"))
    send_email(settings, settings.marketing_emails, subject, body, attachments,
               cc=[settings.admin_email])

    send_email(
        settings, [sub.submitter_email],
        f"Your working paper has been published ({sub.number})",
        f"Dear {sub.submitter_name},\n\n"
        f"\"{sub.title}\" has been approved and published as number {sub.number} of the "
        f"{settings.series_name}.\n\n"
        f"PDF: {settings.pdf_url(sub.number)}\n"
        f"IDEAS: {settings.ideas_url(sub.number)}\n"
        f"EconPapers: {settings.econpapers_url(sub.number)}\n\n"
        f"The RePEc pages appear once IDEAS and EconPapers have mirrored the archive, usually "
        f"within one or two days. Once they are live, you can claim the paper in the RePEc "
        f"Author Service (https://authors.repec.org).\n\n"
        f"The Marketing and Communication team has been notified and will add the paper to the "
        f"university website.\n",
    )
    return commit_url
