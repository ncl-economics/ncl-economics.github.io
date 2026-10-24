import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # tools/ -> import wp

REPO_ROOT = Path(__file__).resolve().parents[3]

ISSUE_BODY = """### Title

High-Frequency Identification of UK Monetary Policy Shocks

### Authors

Fusari, Francesco; francesco.fusari@newcastle.ac.uk; Newcastle University Business School; pfu123
Lovelace, Ada; ; Analytical Engines

### Abstract

The paper shows that in a small open economy the event-window exchange-rate surprise is the present value of the revised policy path.

Second paragraph.

### Date

2026-10

### JEL codes

E52,F31

### Keywords

monetary policy; exchange rates

### Number of pages

42

### Paper PDF

[paper.pdf](https://github.com/user-attachments/files/12345/paper.pdf)

### Paper number

_No response_

### Contact e-mail

francesco.fusari@newcastle.ac.uk

### Notes for the editor

_No response_
"""

PDF = b"%PDF-1.4\n%fake test pdf\n%%EOF\n"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A copy of the real archive files (templates and index) in a temp repo root."""
    src = REPO_ROOT / "RePEc"
    shutil.copytree(src, tmp_path / "RePEc")
    (tmp_path / "papers").mkdir()
    return tmp_path


@pytest.fixture
def fake_download():
    calls = []

    def download(url: str, dest: Path) -> None:
        calls.append(url)
        dest.write_bytes(PDF)

    download.calls = calls
    return download
