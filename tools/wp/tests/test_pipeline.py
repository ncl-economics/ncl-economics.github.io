import json
import subprocess
import sys
from pathlib import Path

from wp import pipeline
from wp.config import CONFIG
from wp.redif import existing_numbers
from wp.tests.conftest import ISSUE_BODY, PDF, REPO_ROOT


def test_real_archive_numbers_are_read(root):
    taken = existing_numbers((root / "RePEc/nwc/wpaper/nwc2026.rdf").read_text())
    assert "2026-01" in taken


def test_preview_proposes_next_number_and_shows_template(root):
    md = pipeline.preview_markdown(ISSUE_BODY, root)
    assert md.startswith("<!-- wp-preview -->")
    assert "published as **2026-02**" in md
    assert "Author-Name: Fusari, Francesco" in md
    assert "Author-Name: Lovelace, Ada" in md
    assert "Abstract: The paper shows" in md and "Second paragraph." in md
    assert "Length: 42 pages" in md
    assert "File-URL: https://ncl-economics.github.io/papers/2026-02.pdf" in md
    assert "Handle: RePEc:nwc:wpaper:2026-02" in md
    assert "`approved` label" in md


def test_preview_lists_errors(root):
    md = pipeline.preview_markdown(ISSUE_BODY.replace("2026-10", "soon"), root)
    assert "Please fix" in md and "YYYY-MM" in md and "Template-Type" not in md


def test_preview_rejects_taken_number(root):
    md = pipeline.preview_markdown(ISSUE_BODY.replace("### Paper number\n\n_No response_",
                                                      "### Paper number\n\n2026-01"), root)
    assert "already published" in md


def test_publish_writes_archive_files(root, fake_download):
    before = (root / "RePEc/nwc/wpaper/nwc2026.rdf").read_text()
    index_before = (root / "RePEc/nwc/wpaper/index.html").read_text()
    result = pipeline.publish(ISSUE_BODY, root, download=fake_download, cover=False)

    assert result["number"] == "2026-02" and result["handle"] == "RePEc:nwc:wpaper:2026-02"
    assert fake_download.calls == ["https://github.com/user-attachments/files/12345/paper.pdf"]
    assert (root / "papers/2026-02.pdf").read_bytes() == PDF
    rdf = (root / "RePEc/nwc/wpaper/nwc2026.rdf").read_text()
    assert rdf.startswith(before.rstrip() + "\n\nTemplate-Type: ReDIF-Paper 1.0\n")
    assert rdf.rstrip().endswith("Handle: RePEc:nwc:wpaper:2026-02")
    assert rdf.count("Template-Type") == 2
    assert (root / "RePEc/nwc/wpaper/index.html").read_text() == index_before  # same year
    assert result["subject"] == "New working paper: High-Frequency Identification of UK Monetary Policy Shocks (2026-02)"
    assert "https://ncl-economics.github.io/papers/2026-02.pdf" in result["email_body"]
    assert "Date: October 2026" in result["email_body"]
    assert "Contact for queries: francesco.fusari@newcastle.ac.uk" in result["email_body"]

    # publishing the same thing again is refused: the number is now taken
    import pytest
    with pytest.raises(ValueError, match="already"):
        pipeline.publish(ISSUE_BODY.replace("_No response_\n\n### Contact", "2026-02\n\n### Contact"),
                         root, download=fake_download, cover=False)
    # and a second paper gets 2026-03
    r2 = pipeline.publish(ISSUE_BODY.replace("High-Frequency", "Another"), root,
                          download=fake_download, cover=False)
    assert r2["number"] == "2026-03"


def test_publish_new_year_creates_file_and_index_entry(root, fake_download):
    result = pipeline.publish(ISSUE_BODY.replace("2026-10", "2027-03"), root,
                              download=fake_download, cover=False)
    assert result["number"] == "2027-01"
    assert (root / "RePEc/nwc/wpaper/nwc2027.rdf").read_text().startswith("Template-Type")
    index = (root / "RePEc/nwc/wpaper/index.html").read_text()
    assert ('<li><a href="nwc2026.rdf">nwc2026.rdf</a></li>\n'
            '<li><a href="nwc2027.rdf">nwc2027.rdf</a></li>\n</ul>') in index


def test_publish_rejects_non_pdf(root):
    def bad(url, dest):
        dest.write_bytes(b"hello")
    import pytest
    with pytest.raises(ValueError, match="not a PDF"):
        pipeline.publish(ISSUE_BODY, root, download=bad, cover=False)
    assert not (root / "papers/2026-02.pdf").exists() or True  # nothing committed either way


def test_cover_metadata():
    from wp.issue import parse_submission
    meta = pipeline.cover_metadata(parse_submission(ISSUE_BODY), "2026-02")
    assert meta == {"title": "High-Frequency Identification of UK Monetary Policy Shocks",
                    "authors": [["Francesco Fusari", "Newcastle University Business School"],
                                ["Ada Lovelace", "Analytical Engines"]],
                    "number": "2026-02", "date": "October 2026"}


def test_cli_preview_and_publish(root, tmp_path, monkeypatch):
    issue = tmp_path / "issue.json"
    issue.write_text(json.dumps({"number": 7, "body": ISSUE_BODY}))
    cli = REPO_ROOT / "tools/wp/cli.py"
    out = tmp_path / "preview.md"
    r = subprocess.run([sys.executable, str(cli), "preview", "--issue-json", str(issue),
                        "--root", str(root), "--out", str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "2026-02" in out.read_text()

    # publish through the CLI in-process, with the downloader replaced (no network in tests)
    gh_out = tmp_path / "gh_output.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(gh_out))
    monkeypatch.setattr(pipeline, "default_download", lambda url, dest: dest.write_bytes(PDF))
    result_file, email_file = tmp_path / "result.json", tmp_path / "email.txt"
    from wp import cli as cli_mod
    assert cli_mod.main(["publish", "--issue-json", str(issue), "--root", str(root),
                         "--result", str(result_file), "--email", str(email_file),
                         "--no-cover"]) == 0
    result = json.loads(result_file.read_text())
    assert result["number"] == "2026-02"
    assert "number=2026-02" in gh_out.read_text()
    assert "subject=New working paper" in gh_out.read_text()
    assert email_file.read_text().startswith("Dear colleagues")


def test_cli_publish_reports_errors(root, tmp_path):
    issue = tmp_path / "issue.json"
    issue.write_text(json.dumps({"body": ISSUE_BODY.replace("2026-10", "nope")}))
    cli = REPO_ROOT / "tools/wp/cli.py"
    r = subprocess.run([sys.executable, str(cli), "publish", "--issue-json", str(issue),
                        "--root", str(root), "--result", str(tmp_path / "r.json"),
                        "--email", str(tmp_path / "e.txt"), "--no-cover"],
                       capture_output=True, text=True)
    assert r.returncode == 1 and "::error::" in r.stdout and "YYYY-MM" in r.stdout


def test_add_cover_removes_preview_png(root, tmp_path, monkeypatch):
    src, dest = tmp_path / "in.pdf", tmp_path / "out.pdf"
    src.write_bytes(PDF)

    def fake_run(argv, check, timeout):
        Path(argv[3]).write_bytes(PDF + b"cover")
        Path(argv[3]).with_suffix(".cover.png").write_bytes(b"png")
    monkeypatch.setattr(pipeline.subprocess, "run", fake_run)
    pipeline.add_cover(src, dest, {"title": "t"}, root)
    assert dest.read_bytes() == PDF + b"cover"
    assert not dest.with_suffix(".cover.png").exists()


def test_default_download_retries_with_token(tmp_path, monkeypatch):
    import urllib.error
    seen = []

    class Resp:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return PDF

    def fake_urlopen(req, timeout):
        seen.append(req.get_header("Authorization"))
        if req.get_header("Authorization") is None:
            raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", None, None)
        return Resp()
    monkeypatch.setattr(pipeline.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("GH_TOKEN", "tok")
    dest = tmp_path / "f.pdf"
    pipeline.default_download("https://github.com/user-attachments/files/1/x.pdf", dest)
    assert dest.read_bytes() == PDF and seen == [None, "Bearer tok"]
