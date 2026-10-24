from app.config import Settings
from app.redif import (Author, Paper, append_template, archive_template, clean_list,
                       existing_numbers, next_number, paper_template, series_template,
                       update_index, valid_number)

S = Settings(archive_code="nwc", series_code="wpaper", site_url="https://x.github.io",
             rdf_dir="RePEc/nwc/wpaper", pdf_dir="papers",
             series_name="Newcastle Economics Discussion Papers")


def test_paper_template_fields_and_order():
    p = Paper(title="A  title\nwith newline", abstract="Line one.\n\nLine two.", number="2026-02",
              creation_date="2026-10", keywords="a; b ,c", jel="E52,F31", length_pages=12,
              authors=[Author("Ada", "Lovelace", "ada@x.org", "Analytical Engines", "pLo1"),
                       Author("Alan", "Turing")])
    t = paper_template(p, S)
    lines = t.splitlines()
    assert lines[0] == "Template-Type: ReDIF-Paper 1.0"
    assert "Author-Name: Lovelace, Ada" in lines
    assert "Author-Name-First" not in t  # this archive uses the 'Last, First' form only
    assert "Author-Email: ada@x.org" in lines
    assert "Author-Workplace-Name: Analytical Engines" in lines
    assert "Author-Person: pLo1" in lines
    assert "Author-Name: Turing, Alan" in lines
    assert "Title: A title with newline" in lines
    assert "Abstract: Line one. Line two." in lines
    assert "Length: 12 pages" in lines
    assert "Creation-Date: 2026-10" in lines
    assert "File-URL: https://x.github.io/papers/2026-02.pdf" in lines
    assert "File-Format: Application/pdf" in lines
    assert "File-Function" not in t
    assert "Number: 2026-02" in lines
    assert "Classification-JEL: E52, F31" in lines
    assert "Keywords: a, b, c" in lines
    assert lines[-1] == "Handle: RePEc:nwc:wpaper:2026-02"
    assert t.endswith("\n") and "\n\n" not in t
    # every line is a Field: value pair
    assert all(": " in ln for ln in lines)


def test_optional_fields_are_omitted():
    p = Paper(title="T", abstract="A", number="2026-01", creation_date="2026-01",
              authors=[Author("A", "B")])
    t = paper_template(p, S)
    assert "Author-Email" not in t and "Length:" not in t and "Keywords:" not in t


def test_archive_and_series_templates():
    a = archive_template(S, "Newcastle University Economics", "F. Fusari", "f@x.ac.uk")
    assert a.startswith("Template-Type: ReDIF-Archive 1.0\nHandle: RePEc:nwc\n")
    assert a.rstrip().endswith("URL: https://x.github.io/RePEc/nwc/")
    s = series_template(S, "Newcastle University Business School", "https://ncl.ac.uk",
                        "RePEc:edi:dencluk", "F. Fusari", "f@x.ac.uk")
    assert "Type: ReDIF-Paper" in s
    assert s.rstrip().endswith("Handle: RePEc:nwc:wpaper")


def test_existing_numbers_and_next_number():
    rdf = ("Template-Type: ReDIF-Paper 1.0\nNumber: 2026-01\nHandle: RePEc:nwc:wpaper:2026-01\n\n"
           "Template-Type: ReDIF-Paper 1.0\nHandle: RePEc:nwc:wpaper:2026-03\n")
    nums = existing_numbers(rdf)
    assert nums == {"2026-01", "2026-03"}
    assert next_number(2026, nums) == "2026-02"
    assert next_number(2026, nums | {"2026-02"}) == "2026-04"
    assert next_number(2027, nums) == "2027-01"
    assert next_number(2026, set(), width=3) == "2026-001"


def test_append_template():
    assert append_template(None, "A: 1\n") == "A: 1\n"
    assert append_template("", "A: 1") == "A: 1\n"
    assert append_template("A: 1\n", "B: 2\n") == "A: 1\n\nB: 2\n"
    assert append_template("A: 1\n\n\n", "B: 2") == "A: 1\n\nB: 2\n"


def test_update_index():
    fresh = update_index(None, ["nwc2026.rdf", "2026-01.pdf"], "Papers")
    assert '<a href="nwc2026.rdf">' in fresh and '<a href="2026-01.pdf">' in fresh
    assert fresh.startswith("<!DOCTYPE html>")
    existing = '<html><body><ul>\n<li><a href="nwc2026.rdf">nwc2026.rdf</a></li>\n</ul></body></html>'
    out = update_index(existing, ["nwc2026.rdf", "nwc2027.rdf"], "Papers")
    assert out.count("nwc2026.rdf") == 2  # unchanged, not duplicated
    assert '<li><a href="nwc2027.rdf">nwc2027.rdf</a></li>\n</ul>' in out
    bare = "<p>hello</p>"
    assert update_index(bare, ["x.rdf"], "P").endswith('<li><a href="x.rdf">x.rdf</a></li>\n')


def test_paths_follow_the_archive_layout():
    assert S.rdf_path("2026-03") == "RePEc/nwc/wpaper/nwc2026.rdf"
    assert S.rdf_index_path() == "RePEc/nwc/wpaper/index.html"
    assert S.pdf_path("2026-03") == "papers/2026-03.pdf"
    assert S.pdf_url("2026-03") == "https://x.github.io/papers/2026-03.pdf"
    assert S.paper_handle("2026-03") == "RePEc:nwc:wpaper:2026-03"
    assert S.ideas_url("2026-03") == "https://ideas.repec.org/p/nwc/wpaper/2026-03.html"
    assert S.econpapers_url("2026-03") == "https://econpapers.repec.org/paper/nwcwpaper/2026-03.htm"


def test_valid_number_and_clean_list():
    assert valid_number("2026-01") and valid_number("2026-123")
    assert not valid_number("26-01") and not valid_number("2026_01") and not valid_number("")
    assert clean_list(" E52 ;F31,, E4 ") == "E52, F31, E4"
