"""ReDIF template generation and parsing.

ReDIF is the metadata format RePEc reads: plain-text records made of
``Field: value`` lines, records separated by a blank line, with ``Handle``
conventionally last. See https://ideas.repec.org/t/papertemplate.html.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from .config import Settings


@dataclass
class Author:
    first: str
    last: str
    email: str = ""
    workplace: str = ""
    person: str = ""  # RePEc Short-ID, e.g. pfu123

    @property
    def name(self) -> str:
        """Display form, 'First Last'."""
        return f"{self.first} {self.last}".strip()

    @property
    def redif_name(self) -> str:
        """ReDIF form used in this archive, 'Last, First'."""
        return f"{self.last}, {self.first}" if self.first else self.last


@dataclass
class Paper:
    title: str
    authors: list[Author]
    abstract: str
    number: str
    creation_date: str  # YYYY-MM or YYYY-MM-DD
    keywords: str = ""
    jel: str = ""
    length_pages: int | None = None
    file_url: str = ""
    extra: dict[str, str] = field(default_factory=dict)


def clean(text: str) -> str:
    """Collapse all whitespace (including newlines) into single spaces.

    ReDIF values may span lines only with continuation indentation; keeping
    every value on one line is the robust choice for generated files.
    """
    return re.sub(r"\s+", " ", (text or "")).strip()


def clean_list(text: str) -> str:
    """Normalise a comma/semicolon separated list to 'a, b, c'."""
    items = [clean(x) for x in re.split(r"[;,]", text or "")]
    return ", ".join(x for x in items if x)


def _line(key: str, value: str | None) -> list[str]:
    value = clean(value or "")
    return [f"{key}: {value}"] if value else []


def paper_template(paper: Paper, settings: Settings) -> str:
    lines: list[str] = ["Template-Type: ReDIF-Paper 1.0"]
    for a in paper.authors:
        lines += _line("Author-Name", a.redif_name)
        lines += _line("Author-Email", a.email)
        lines += _line("Author-Workplace-Name", a.workplace)
        lines += _line("Author-Person", a.person)
    lines += _line("Title", paper.title)
    lines += _line("Abstract", paper.abstract)
    if paper.length_pages:
        lines += _line("Length", f"{paper.length_pages} pages")
    lines += _line("Creation-Date", paper.creation_date)
    file_url = paper.file_url or settings.pdf_url(paper.number)
    lines += _line("File-URL", file_url)
    lines += _line("File-Format", "Application/pdf")
    lines += _line("Number", paper.number)
    lines += _line("Classification-JEL", clean_list(paper.jel))
    lines += _line("Keywords", clean_list(paper.keywords))
    for k, v in paper.extra.items():
        lines += _line(k, v)
    lines += _line("Handle", settings.paper_handle(paper.number))
    return "\n".join(lines) + "\n"


def archive_template(settings: Settings, name: str, maintainer_name: str,
                     maintainer_email: str, description: str = "") -> str:
    lines = [
        "Template-Type: ReDIF-Archive 1.0",
        f"Handle: RePEc:{settings.archive_code}",
        f"Name: {clean(name)}",
        f"Maintainer-Email: {clean(maintainer_email)}",
        f"Maintainer-Name: {clean(maintainer_name)}",
    ]
    if description:
        lines.append(f"Description: {clean(description)}")
    lines.append(f"URL: {settings.archive_url}")
    return "\n".join(lines) + "\n"


def series_template(settings: Settings, provider_name: str, provider_homepage: str,
                    provider_institution: str, maintainer_name: str,
                    maintainer_email: str) -> str:
    lines = [
        "Template-Type: ReDIF-Series 1.0",
        f"Name: {clean(settings.series_name)}",
        f"Provider-Name: {clean(provider_name)}",
        f"Provider-Homepage: {clean(provider_homepage)}",
        f"Provider-Institution: {clean(provider_institution)}",
        f"Maintainer-Name: {clean(maintainer_name)}",
        f"Maintainer-Email: {clean(maintainer_email)}",
        "Type: ReDIF-Paper",
        f"Handle: {settings.series_handle}",
    ]
    return "\n".join(lines) + "\n"


# ---- working with existing files ---------------------------------------

_NUMBER_RE = re.compile(r"^Number:\s*(\S+)\s*$", re.MULTILINE)
_HANDLE_RE = re.compile(r"^Handle:\s*(\S+)\s*$", re.MULTILINE)


def existing_numbers(rdf_text: str) -> set[str]:
    """Paper numbers already present in a ReDIF file (from Number and Handle)."""
    found = set(_NUMBER_RE.findall(rdf_text or ""))
    for h in _HANDLE_RE.findall(rdf_text or ""):
        parts = h.split(":")
        if len(parts) >= 4 and parts[0] == "RePEc":
            found.add(parts[-1])
    return found


def append_template(existing: str | None, template: str) -> str:
    """Append a record to a (possibly empty) ReDIF file, blank-line separated."""
    template = template.strip() + "\n"
    if not existing or not existing.strip():
        return template
    return existing.rstrip() + "\n\n" + template


def next_number(year: int | str, taken: Iterable[str], width: int = 2) -> str:
    """First free number of the form YYYY-NN for the given year."""
    prefix = f"{year}-"
    used = set()
    for n in taken:
        if n.startswith(prefix) and n[len(prefix):].isdigit():
            used.add(int(n[len(prefix):]))
    i = 1
    while i in used:
        i += 1
    return f"{prefix}{i:0{width}d}"


_NUMBER_FORMAT = re.compile(r"^\d{4}-\d{1,4}$")


def valid_number(number: str) -> bool:
    return bool(_NUMBER_FORMAT.match(number or ""))


# ---- index.html listings -------------------------------------------------

def _link_html(name: str) -> str:
    return f'<li><a href="{name}">{name}</a></li>'


def update_index(existing: str | None, filenames: list[str], title: str) -> str:
    """Ensure a directory listing links to each of ``filenames``.

    RePEc's mirroring software discovers .rdf files by following the links
    in the directory's index.html, so every template file must be listed.
    Existing content is preserved; missing links are inserted before the
    closing </ul> if there is one, else before </body>, else appended.
    """
    if not existing or not existing.strip():
        items = "\n".join(_link_html(n) for n in filenames)
        return (
            "<!DOCTYPE html>\n<html>\n<head><meta charset=\"utf-8\">"
            f"<title>{title}</title></head>\n<body>\n<h1>{title}</h1>\n"
            f"<ul>\n{items}\n</ul>\n</body>\n</html>\n"
        )
    text = existing
    for name in filenames:
        if re.search(rf'href=["\']\.?/?{re.escape(name)}["\']', text):
            continue
        line = _link_html(name) + "\n"
        for anchor in ("</ul>", "</body>"):
            idx = text.lower().rfind(anchor)
            if idx != -1:
                text = text[:idx] + line + text[idx:]
                break
        else:
            text = text.rstrip() + "\n" + line
    return text
