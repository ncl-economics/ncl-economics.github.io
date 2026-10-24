"""Read a submission out of a GitHub issue created from the issue form."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .redif import Author, clean

# Field labels exactly as in .github/ISSUE_TEMPLATE/working-paper.yml
FIELDS = {
    "Title": "title",
    "Authors": "authors",
    "Abstract": "abstract",
    "Date": "date",
    "JEL codes": "jel",
    "Keywords": "keywords",
    "Number of pages": "pages",
    "Paper PDF": "pdf",
    "Paper number": "number",
    "Contact e-mail": "contact",
    "Notes for the editor": "notes",
}

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# The PDF field holds either a GitHub attachment (dragged into the issue), which renders as
# [name.pdf](https://github.com/user-attachments/files/..), or a link pasted by the
# Power Automate flow (OneDrive / SharePoint share link, or any https link to the file).
_ATTACHMENT_RE = re.compile(r"\((https://github\.com/user-attachments/files/[^\s)]+)\)|"
                            r"(https://github\.com/user-attachments/files/\S+)")
_URL_RE = re.compile(r"https://[^\s<>()\[\]\"']+")
_ONEDRIVE_HOSTS = ("1drv.ms", "-my.sharepoint.com", ".sharepoint.com", "onedrive.live.com")


def find_pdf_link(text: str) -> str:
    """The download link in the 'Paper PDF' field, or '' if none."""
    m = _ATTACHMENT_RE.search(text or "")
    if m:
        return m.group(1) or m.group(2)
    for url in _URL_RE.findall(text or ""):
        return url.rstrip(".,;")
    return ""


def is_onedrive_link(url: str) -> bool:
    return any(h in url for h in _ONEDRIVE_HOSTS)


def download_url(url: str) -> str:
    """Turn a OneDrive/SharePoint *view* share link into a direct-download link."""
    if is_onedrive_link(url) and "download=1" not in url:
        return url + ("&" if "?" in url else "?") + "download=1"
    return url


def parse_fields(body: str) -> dict[str, str]:
    """Split an issue-form body ('### Label\\n\\nvalue') into {key: value}."""
    out: dict[str, str] = {}
    body = (body or "").replace("\r\n", "\n")
    parts = re.split(r"^### (.+)$", body, flags=re.MULTILINE)
    # parts = [preamble, label1, value1, label2, value2, ...]
    for label, value in zip(parts[1::2], parts[2::2]):
        key = FIELDS.get(label.strip())
        if not key:
            continue
        value = value.strip()
        if value == "_No response_":
            value = ""
        out[key] = value
    return out


def parse_authors(text: str) -> tuple[list[Author], list[str]]:
    """'Surname, First; email; affiliation; short-id' per line."""
    authors, errors = [], []
    for raw in (text or "").splitlines():
        line = raw.strip().strip("-").strip()
        if not line:
            continue
        cells = [c.strip() for c in line.split(";")]
        name = cells[0]
        if "," in name:
            last, first = [clean(x) for x in name.split(",", 1)]
        else:
            errors.append(f"Author '{name}': write the name as 'Surname, First names'.")
            parts = name.split()
            last, first = (parts[-1], " ".join(parts[:-1])) if len(parts) > 1 else (name, "")
        email = cells[1] if len(cells) > 1 else ""
        if email and not _EMAIL_RE.match(email):
            errors.append(f"Author '{name}': '{email}' is not an e-mail address.")
        authors.append(Author(first=first, last=last, email=email,
                              workplace=clean(cells[2]) if len(cells) > 2 else "",
                              person=cells[3] if len(cells) > 3 else ""))
    if not authors:
        errors.append("At least one author is required.")
    return authors, errors


@dataclass
class Submission:
    title: str = ""
    authors: list[Author] = field(default_factory=list)
    abstract: str = ""
    date: str = ""
    jel: str = ""
    keywords: str = ""
    pages: int | None = None
    pdf_url: str = ""
    number: str = ""          # as requested in the form; may be empty
    contact: str = ""
    notes: str = ""
    errors: list[str] = field(default_factory=list)

    @property
    def year(self) -> str:
        return self.date[:4]

    @property
    def author_names(self) -> str:
        return ", ".join(a.name for a in self.authors)


def parse_submission(body: str) -> Submission:
    f = parse_fields(body)
    s = Submission()
    s.title = clean(f.get("title", ""))
    if not s.title:
        s.errors.append("The title is required.")
    s.authors, author_errors = parse_authors(f.get("authors", ""))
    s.errors += author_errors
    s.abstract = f.get("abstract", "").strip()
    if len(clean(s.abstract)) < 50:
        s.errors.append("The abstract is required (at least 50 characters).")
    s.date = f.get("date", "").strip()
    if not re.match(r"^\d{4}-(0[1-9]|1[0-2])(-\d{2})?$", s.date):
        s.errors.append("The date must be in the form YYYY-MM.")
    s.jel = f.get("jel", "").strip()
    s.keywords = f.get("keywords", "").strip()
    pages = f.get("pages", "").strip()
    if pages:
        if pages.isdigit() and int(pages) > 0:
            s.pages = int(pages)
        else:
            s.errors.append("The number of pages must be a whole number.")
    s.pdf_url = find_pdf_link(f.get("pdf", ""))
    if not s.pdf_url:
        s.errors.append("No PDF found: drag and drop the PDF into the 'Paper PDF' box, "
                        "or paste a link to it.")
    s.number = f.get("number", "").strip()
    if s.number and not re.match(r"^\d{4}-\d{1,4}$", s.number):
        s.errors.append("The paper number must look like 2026-02 (or be left blank).")
    s.contact = f.get("contact", "").strip()
    s.notes = f.get("notes", "").strip()
    return s
