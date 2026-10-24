"""SQLite storage for submissions."""
from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .redif import Author

SCHEMA = """
CREATE TABLE IF NOT EXISTS submissions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    submitter_name TEXT NOT NULL,
    submitter_email TEXT NOT NULL,
    title TEXT NOT NULL,
    abstract TEXT NOT NULL,
    keywords TEXT NOT NULL DEFAULT '',
    jel TEXT NOT NULL DEFAULT '',
    creation_date TEXT NOT NULL,
    length_pages INTEGER,
    authors_json TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    number TEXT,
    pdf_path TEXT NOT NULL,
    pdf_original_name TEXT NOT NULL,
    template TEXT NOT NULL DEFAULT '',
    decided_at TEXT,
    decision_note TEXT NOT NULL DEFAULT '',
    commit_url TEXT NOT NULL DEFAULT ''
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Submission:
    submitter_name: str
    submitter_email: str
    title: str
    abstract: str
    creation_date: str
    authors: list[Author]
    pdf_path: str
    pdf_original_name: str
    keywords: str = ""
    jel: str = ""
    length_pages: int | None = None
    notes: str = ""
    number: str | None = None
    template: str = ""
    status: str = "pending"
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: str = field(default_factory=now_iso)
    decided_at: str | None = None
    decision_note: str = ""
    commit_url: str = ""

    @property
    def year(self) -> int:
        return int(self.creation_date[:4])

    @property
    def author_names(self) -> str:
        return ", ".join(a.name for a in self.authors)

    def to_row(self) -> dict:
        d = asdict(self)
        d["authors_json"] = json.dumps([asdict(a) for a in self.authors])
        del d["authors"]
        return d

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Submission":
        d = dict(row)
        d["authors"] = [Author(**a) for a in json.loads(d.pop("authors_json"))]
        return cls(**d)


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self._conn() as c:
            c.executescript(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def insert(self, sub: Submission) -> None:
        row = sub.to_row()
        cols = ", ".join(row)
        marks = ", ".join(f":{k}" for k in row)
        with self._conn() as c:
            c.execute(f"INSERT INTO submissions ({cols}) VALUES ({marks})", row)

    def update(self, sub: Submission) -> None:
        row = sub.to_row()
        sets = ", ".join(f"{k} = :{k}" for k in row if k != "id")
        with self._conn() as c:
            c.execute(f"UPDATE submissions SET {sets} WHERE id = :id", row)

    def get(self, sub_id: str) -> Submission | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM submissions WHERE id = ?", (sub_id,)).fetchone()
        return Submission.from_row(row) if row else None

    def list(self) -> list[Submission]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM submissions ORDER BY created_at DESC").fetchall()
        return [Submission.from_row(r) for r in rows]

    def numbers_in_use(self) -> set[str]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT number FROM submissions WHERE number IS NOT NULL AND status != 'rejected'"
            ).fetchall()
        return {r["number"] for r in rows if r["number"]}
