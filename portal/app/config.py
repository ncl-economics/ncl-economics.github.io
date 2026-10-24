"""Settings, read from environment variables (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _list(value: str | None) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


@dataclass
class Settings:
    # Portal
    base_url: str = "http://localhost:8000"
    secret_key: str = "dev-secret-change-me"
    data_dir: Path = Path("./data")
    submit_code: str = ""
    admin_user: str = "admin"
    admin_password: str = "admin"
    token_max_age_days: int = 30
    max_pdf_mb: int = 50

    # RePEc archive
    archive_code: str = "nwc"
    series_code: str = "wpaper"
    series_name: str = "Newcastle Economics Discussion Papers"
    site_url: str = "https://ncl-economics.github.io"
    rdf_dir: str = "RePEc/nwc/wpaper"
    pdf_dir: str = "papers"
    rdf_file_pattern: str = "{archive}{year}.rdf"
    pdf_file_pattern: str = "{number}.pdf"
    number_width: int = 2
    default_workplace: str = "Newcastle University Business School"
    cover_command: str = ""

    # GitHub
    github_token: str = ""
    github_repo: str = "ncl-economics/ncl-economics.github.io"
    github_branch: str = "main"
    github_api: str = "https://api.github.com"

    # E-mail
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_ssl: bool = False
    mail_from: str = "Working Paper Portal <noreply@example.org>"
    admin_email: str = ""
    marketing_emails: list[str] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "Settings":
        e = os.environ.get
        d = cls()
        return cls(
            base_url=e("BASE_URL", d.base_url).rstrip("/"),
            secret_key=e("SECRET_KEY", d.secret_key),
            data_dir=Path(e("DATA_DIR", str(d.data_dir))),
            submit_code=e("SUBMIT_CODE", ""),
            admin_user=e("ADMIN_USER", d.admin_user),
            admin_password=e("ADMIN_PASSWORD", d.admin_password),
            token_max_age_days=int(e("TOKEN_MAX_AGE_DAYS", d.token_max_age_days)),
            max_pdf_mb=int(e("MAX_PDF_MB", d.max_pdf_mb)),
            archive_code=e("ARCHIVE_CODE", d.archive_code),
            series_code=e("SERIES_CODE", d.series_code),
            series_name=e("SERIES_NAME", d.series_name),
            site_url=e("SITE_URL", d.site_url).rstrip("/"),
            rdf_dir=e("RDF_DIR", d.rdf_dir).strip("/"),
            pdf_dir=e("PDF_DIR", d.pdf_dir).strip("/"),
            rdf_file_pattern=e("RDF_FILE_PATTERN", d.rdf_file_pattern),
            pdf_file_pattern=e("PDF_FILE_PATTERN", d.pdf_file_pattern),
            number_width=int(e("NUMBER_WIDTH", d.number_width)),
            default_workplace=e("DEFAULT_WORKPLACE", d.default_workplace),
            cover_command=e("COVER_COMMAND", ""),
            github_token=e("GITHUB_TOKEN", ""),
            github_repo=e("GITHUB_REPO", d.github_repo),
            github_branch=e("GITHUB_BRANCH", d.github_branch),
            github_api=e("GITHUB_API", d.github_api).rstrip("/"),
            smtp_host=e("SMTP_HOST", ""),
            smtp_port=int(e("SMTP_PORT", d.smtp_port)),
            smtp_user=e("SMTP_USER", ""),
            smtp_password=e("SMTP_PASSWORD", ""),
            smtp_ssl=_bool(e("SMTP_SSL"), False),
            mail_from=e("MAIL_FROM", d.mail_from),
            admin_email=e("ADMIN_EMAIL", ""),
            marketing_emails=_list(e("MARKETING_EMAILS")),
        )

    # ---- derived helpers -------------------------------------------------
    @property
    def series_handle(self) -> str:
        return f"RePEc:{self.archive_code}:{self.series_code}"

    def paper_handle(self, number: str) -> str:
        return f"{self.series_handle}:{number}"

    def _fmt(self, pattern: str, number: str) -> str:
        year = number.split("-")[0]
        return pattern.format(
            archive=self.archive_code, series=self.series_code, year=year, number=number
        )

    def rdf_path(self, number: str) -> str:
        return f"{self.rdf_dir}/{self._fmt(self.rdf_file_pattern, number)}"

    def rdf_index_path(self) -> str:
        return f"{self.rdf_dir}/index.html"

    def pdf_path(self, number: str) -> str:
        return f"{self.pdf_dir}/{self._fmt(self.pdf_file_pattern, number)}"

    def pdf_url(self, number: str) -> str:
        return f"{self.site_url}/{self.pdf_path(number)}"

    @property
    def archive_url(self) -> str:
        """URL of the archive directory (holds <archive>arch.rdf), with trailing slash."""
        parent = self.rdf_dir.rsplit("/", 1)[0] if "/" in self.rdf_dir else ""
        return f"{self.site_url}/{parent}/" if parent else f"{self.site_url}/"

    def ideas_url(self, number: str) -> str:
        return f"https://ideas.repec.org/p/{self.archive_code}/{self.series_code}/{number}.html"

    def econpapers_url(self, number: str) -> str:
        return (
            f"https://econpapers.repec.org/paper/"
            f"{self.archive_code}{self.series_code}/{number}.htm"
        )

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def outbox_dir(self) -> Path:
        return self.data_dir / "outbox"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "portal.sqlite3"
