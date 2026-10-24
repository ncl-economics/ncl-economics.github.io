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
    authors, errors = parse_authors("Ada Lovelace; bad@email")
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
    assert "title is required" in joined and "YYYY-MM" in joined and "No PDF found" in joined


def test_bare_attachment_url_is_accepted():
    body = ISSUE_BODY.replace("[paper.pdf](https://github.com/user-attachments/files/12345/paper.pdf)",
                              "https://github.com/user-attachments/files/999/x.pdf")
    assert parse_submission(body).pdf_url == "https://github.com/user-attachments/files/999/x.pdf"


def test_pdf_links_from_power_automate():
    from wp.issue import download_url, find_pdf_link, is_onedrive_link
    share = "https://newcastle-my.sharepoint.com/:b:/g/personal/nxx123_newcastle_ac_uk/EaBcDeF?e=Xy1z"
    assert find_pdf_link(share) == share
    assert find_pdf_link(f"Here is the file: {share}.") == share
    assert find_pdf_link("Drop the PDF file here.") == ""
    assert is_onedrive_link(share) and is_onedrive_link("https://1drv.ms/b/s!x")
    assert download_url(share) == share + "&download=1"
    assert download_url("https://1drv.ms/b/s!x") == "https://1drv.ms/b/s!x?download=1"
    assert download_url(share + "&download=1") == share + "&download=1"
    gh = "https://github.com/user-attachments/files/1/x.pdf"
    assert download_url(gh) == gh
    # a GitHub attachment wins over other links in the same field
    assert find_pdf_link(f"[x.pdf]({gh}) see also https://example.org/a.pdf") == gh


def test_author_cells_in_any_order():
    authors, errors = parse_authors(
        "Fusari, Francesco; Newcastle University Business School\n"
        "Dhamija, Vedanta; vedantadhamija@outlook.com; Centre for Macroeconomics; pdh42\n"
        "Tara, Roshni; pta7; Centre for Macroeconomics; roshni@example.org\n")
    assert errors == []
    a, b, c = authors
    assert (a.workplace, a.email, a.person) == ("Newcastle University Business School", "", "")
    assert (b.workplace, b.email, b.person) == ("Centre for Macroeconomics", "vedantadhamija@outlook.com", "pdh42")
    assert (c.workplace, c.email, c.person) == ("Centre for Macroeconomics", "roshni@example.org", "pta7")


MINIMAL_BODY = """### Title

A minimal paper

### Authors

Fusari, Francesco; Newcastle University Business School

### Abstract

This abstract is long enough to pass the fifty character minimum check of the parser.

### Paper PDF

https://newcastle-my.sharepoint.com/:b:/g/personal/x/EaBc?e=1
"""


def test_minimal_form_defaults_the_date():
    s = parse_submission(MINIMAL_BODY, default_date="2026-10")
    assert s.errors == [] and s.date == "2026-10" and s.date_defaulted
    assert s.pages is None and s.jel == "" and s.contact == ""
    s2 = parse_submission(MINIMAL_BODY)
    assert any("YYYY-MM" in e for e in s2.errors)


THREE_BOX_BODY = """### Title

Fiscal anticipation and inequality

### Author names

Dhamija, Vedanta
Fusari, Francesco
Tara, Roshni

### Author e-mails

vedantadhamija@outlook.com

roshni.tara92@gmail.com

### Affiliations

Centre for Macroeconomics
Newcastle University Business School
Centre for Macroeconomics

### Abstract

Fiscal policy is often anticipated before implementation, yet little is known about how fiscal foresight shapes inequality.

### Paper PDF

https://newcastle-my.sharepoint.com/:b:/g/personal/x/EaBc?e=1
"""


def test_three_author_boxes():
    s = parse_submission(THREE_BOX_BODY, default_date="2026-10")
    assert s.errors == []
    assert [a.redif_name for a in s.authors] == ["Dhamija, Vedanta", "Fusari, Francesco", "Tara, Roshni"]
    assert [a.email for a in s.authors] == ["vedantadhamija@outlook.com", "", "roshni.tara92@gmail.com"]
    assert [a.workplace for a in s.authors] == ["Centre for Macroeconomics",
                                                "Newcastle University Business School",
                                                "Centre for Macroeconomics"]


def test_three_boxes_single_affiliation_applies_to_all_and_errors():
    from wp.issue import parse_author_boxes
    authors, errors = parse_author_boxes("Fusari, Francesco\nTara, Roshni", "", "NUBS")
    assert errors == [] and [a.workplace for a in authors] == ["NUBS", "NUBS"]
    authors, errors = parse_author_boxes("Fusari, Francesco", "a@b.c\nd@e.f", "x\ny")
    assert len(authors) == 1
    assert any("more e-mail lines" in e for e in errors) and any("more affiliation lines" in e for e in errors)
    authors, errors = parse_author_boxes("Francesco Fusari", "not-an-email", "")
    assert authors[0].redif_name == "Fusari, Francesco" and authors[0].email == ""
    assert any("Surname, First names" in e for e in errors) and any("not an e-mail" in e for e in errors)
