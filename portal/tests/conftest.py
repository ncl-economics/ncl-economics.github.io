import email
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import publish
from app.config import Settings
from app.main import create_app


class FakeGitHub:
    """Stands in for GitHubPublisher: remembers an in-memory repo."""

    def __init__(self, files: dict[str, str] | None = None):
        self.files: dict[str, bytes] = {k: v.encode() for k, v in (files or {}).items()}
        self.commits: list[tuple[dict[str, bytes], str]] = []

    def get_text(self, path):
        data = self.files.get(path)
        return data.decode() if data is not None else None

    def commit_files(self, files, message):
        self.files.update(files)
        self.commits.append((files, message))
        return f"https://github.com/example/repec/commit/{len(self.commits):040x}"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        base_url="http://portal.test", secret_key="test-secret", data_dir=tmp_path / "data",
        admin_user="ed", admin_password="pw", archive_code="nwc", series_code="wpaper",
        series_name="Newcastle Economics Discussion Papers",
        site_url="https://ncl-economics.github.io", rdf_dir="RePEc/nwc/wpaper", pdf_dir="papers",
        github_token="t", github_repo="ncl-economics/ncl-economics.github.io",
        admin_email="editor@example.ac.uk", marketing_emails=["marketing@example.ac.uk"],
    )


@pytest.fixture(autouse=True)
def no_real_github(monkeypatch):
    """Never touch api.github.com from the tests: default to an empty fake archive."""
    monkeypatch.setattr(publish, "GitHubPublisher", lambda *a, **k: FakeGitHub())


@pytest.fixture
def gh(monkeypatch) -> FakeGitHub:
    fake = FakeGitHub({
        "RePEc/nwc/wpaper/nwc2026.rdf": (
            "Template-Type: ReDIF-Paper 1.0\nAuthor-Name: Lovelace, Ada\nTitle: First paper\n"
            "File-URL: https://ncl-economics.github.io/papers/2026-01.pdf\n"
            "Number: 2026-01\nHandle: RePEc:nwc:wpaper:2026-01\n"
        ),
        "RePEc/nwc/wpaper/index.html": (
            "<!DOCTYPE html>\n<html>\n<head><meta charset=\"utf-8\">"
            "<title>RePEc archive nwc: wpaper</title></head>\n<body>\n"
            "<h1>Index of /RePEc/nwc/wpaper/</h1>\n<ul>\n"
            "<li><a href=\"nwc2026.rdf\">nwc2026.rdf</a></li>\n</ul>\n</body>\n</html>\n"
        ),
    })
    monkeypatch.setattr(publish, "GitHubPublisher", lambda *a, **k: fake)
    return fake


@pytest.fixture
def client(settings) -> TestClient:
    return TestClient(create_app(settings))


def outbox(settings: Settings) -> list[email.message.Message]:
    msgs = []
    for p in sorted(settings.outbox_dir.glob("*.eml")) if settings.outbox_dir.exists() else []:
        msgs.append(email.message_from_bytes(p.read_bytes()))
    return msgs


PDF = b"%PDF-1.4\n%fake test pdf\n%%EOF\n"


def submission_form(**over):
    data = {
        "submitter_name": "Francesco Fusari", "submitter_email": "f.fusari@example.ac.uk",
        "title": "High-Frequency Identification of UK Monetary Policy Shocks",
        "abstract": "This paper shows that the exchange-rate surprise recovers the conventional "
                    "monetary policy shock in a small open economy.\n\nSecond paragraph.",
        "keywords": "monetary policy; exchange rates", "jel": "E52,F31",
        "creation_date": "2026-10", "length_pages": "42", "notes": "",
        "author_first": ["Francesco", "Ada"], "author_last": ["Fusari", "Lovelace"],
        "author_email": ["f.fusari@example.ac.uk", ""],
        "author_workplace": ["Newcastle University Business School", "Analytical Engines"],
        "author_person": ["pfu123", ""],
    }
    data.update(over)
    return data
