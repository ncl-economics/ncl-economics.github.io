"""Archive layout. Edit here if the series or the directory structure changes."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    archive_code: str = "nwc"
    series_code: str = "wpaper"
    series_name: str = "Newcastle Economics Discussion Papers"
    site_url: str = "https://ncl-economics.github.io"
    rdf_dir: str = "RePEc/nwc/wpaper"     # yearly template files + index.html
    pdf_dir: str = "papers"               # one PDF per paper
    number_width: int = 2                 # 2026-01
    cover_script: str = "tools/make_cover.py"

    @property
    def series_handle(self) -> str:
        return f"RePEc:{self.archive_code}:{self.series_code}"

    def paper_handle(self, number: str) -> str:
        return f"{self.series_handle}:{number}"

    def rdf_path(self, number: str) -> str:
        year = number.split("-")[0]
        return f"{self.rdf_dir}/{self.archive_code}{year}.rdf"

    def rdf_index_path(self) -> str:
        return f"{self.rdf_dir}/index.html"

    def pdf_path(self, number: str) -> str:
        return f"{self.pdf_dir}/{number}.pdf"

    def pdf_url(self, number: str) -> str:
        return f"{self.site_url}/{self.pdf_path(number)}"

    @property
    def archive_url(self) -> str:
        parent = self.rdf_dir.rsplit("/", 1)[0]
        return f"{self.site_url}/{parent}/"

    def ideas_url(self, number: str) -> str:
        return f"https://ideas.repec.org/p/{self.archive_code}/{self.series_code}/{number}.html"

    def econpapers_url(self, number: str) -> str:
        return (f"https://econpapers.repec.org/paper/"
                f"{self.archive_code}{self.series_code}/{number}.htm")


CONFIG = Config()
