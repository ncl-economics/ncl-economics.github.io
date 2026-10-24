from wp.issue import parse_authors, parse_fields, parse_submission
from wp.tests.conftest import ISSUE_BODY


def test_parse_fields_maps_labels_and_blanks():
    f = parse_fields(ISSUE_BODY)
    assert f["title"] == "High-Frequency Identification of UK Monetary Policy Shocks"
    assert f["number"] == "" and f["notes"] == ""
    assert f["pages"] == "42"
    assert f["abstract"].startswith("The paper shows") and "Second paragraph." in f["abstract"]


def test_parse_authors_format():
    authors, errors = parse_authors(
        "Dhamija, Vedanta; vedantadhamija@outlook.com; Centre for Macroeconomics\n"
        "Fusari, Francesco; ; NUBS; pfu123\n"
        "Miranda-Agrippino, Silvia\n")
    assert errors == []
    assert [a.redif_name for a in authors] == ["Dhamija, Vedanta", "Fusari, Francesco",
                                              "Miranda-Agrippino, Silvia"]
    assert authors[0].email == "vedantadhamija@outlook.com"
    assert authors[1].workplace == "NUBS" and authors[1].person == "pfu123"
    assert authors[2].name == "Silvia Miranda-Agrippino"


def test_parse_authors_reports_bad_lines():
    authors, errors = parse_authors("Ada Lovelace; not-an-email")
    assert len(authors) == 1 and authors[0].redif_name == "Lovelace, Ada"
    assert any("Surname, First names" in e for e in errors)
    assert any("not an e-mail" in e for e in errors)
    assert parse_authors("")[1] == ["At least one author is required."]


def test_parse_submission_ok():
    s = parse_submission(ISSUE_BODY)
    assert s.errors == []
    assert s.pdf_url == "https://github.com/user-attachments/files/12345/paper.pdf"
    assert s.pages == 42 and s.year == "2026" and s.number == ""
    assert s.author_names == "Francesco Fusari, Ada Lovelace"


def test_parse_submission_errors():
    body = ISSUE_BODY.replace("2026-10", "October 2026").replace("[paper.pdf](https://github.com/user-attachments/files/12345/paper.pdf)", "Drop the PDF file here.")
    body = body.replace("### Title\n\nHigh-Frequency Identification of UK Monetary Policy Shocks", "### Title\n\n")
    s = parse_submission(body)
    joined = " ".join(s.errors)
    assert "title is required" in joined and "YYYY-MM" in joined and "No PDF attachment" in joined


def test_bare_attachment_url_is_accepted():
    body = ISSUE_BODY.replace("[paper.pdf](https://github.com/user-attachments/files/12345/paper.pdf)",
                              "https://github.com/user-attachments/files/999/x.pdf")
    assert parse_submission(body).pdf_url == "https://github.com/user-attachments/files/999/x.pdf"
