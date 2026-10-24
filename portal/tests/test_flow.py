import re

from app.publish import build_files
from tests.conftest import PDF, FakeGitHub, outbox, submission_form


def _submit(client, **over):
    return client.post("/submit", data=submission_form(**over),
                       files={"pdf": ("paper.pdf", PDF, "application/pdf")}, follow_redirects=False)


def _review_link(settings):
    admin_mail = [m for m in outbox(settings) if "New submission" in m["Subject"]][-1]
    body = admin_mail.get_payload(decode=True).decode()
    return re.search(r"http://portal.test(/review/\S+)", body).group(1)


def test_form_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert 'name="author_first"' in r.text and 'name="pdf"' in r.text


def test_submission_creates_pending_record_and_emails(client, settings):
    r = _submit(client)
    assert r.status_code == 303 and r.headers["location"].startswith("/submitted/")
    assert client.get(r.headers["location"]).status_code == 200

    subs = client.app.state.db.list()
    assert len(subs) == 1
    sub = subs[0]
    assert sub.status == "pending" and sub.number == "2026-01"
    assert [a.name for a in sub.authors] == ["Francesco Fusari", "Ada Lovelace"]
    assert "Handle: RePEc:nwc:wpaper:2026-01" in sub.template
    assert "Abstract: This paper shows" in sub.template and "\n\n" not in sub.template
    assert "Keywords: monetary policy, exchange rates" in sub.template
    assert (settings.uploads_dir / f"{sub.id}.pdf").read_bytes() == PDF

    mails = outbox(settings)
    assert [m["To"] for m in mails] == ["editor@example.ac.uk", "f.fusari@example.ac.uk"]
    assert "/review/" in mails[0].get_payload(decode=True).decode()
    assert sub.template.strip() in mails[0].get_payload(decode=True).decode()


def test_validation_errors(client, settings):
    r = client.post("/submit", data=submission_form(title="", creation_date="October 2026",
                                                     author_first=[], author_last=[]),
                    files={"pdf": ("x.pdf", b"not a pdf", "application/pdf")})
    assert r.status_code == 400
    for msg in ("title is required", "YYYY-MM", "not a PDF", "At least one author"):
        assert msg in r.text
    assert client.app.state.db.list() == [] and outbox(settings) == []


def test_submit_code_required(settings):
    settings.submit_code = "secret"
    from app.main import create_app
    from fastapi.testclient import TestClient
    c = TestClient(create_app(settings))
    assert _submit(c, submit_code="wrong").status_code == 400
    assert _submit(c, submit_code="secret").status_code == 303


def test_second_submission_gets_next_number(client):
    _submit(client)
    _submit(client, title="Another paper")
    assert sorted(s.number for s in client.app.state.db.list()) == ["2026-01", "2026-02"]


def test_proposed_number_skips_papers_already_in_archive(client, gh):
    _submit(client)  # the archive fixture already holds 2026-01
    assert client.app.state.db.list()[0].number == "2026-02"


def test_review_requires_valid_token(client):
    assert client.get("/review/garbage").status_code == 404
    _submit(client)
    sub = client.app.state.db.list()[0]
    from app.tokens import make_token
    wrong = make_token("other-secret", sub.id)
    assert client.get(f"/review/{wrong}").status_code == 404


def test_review_edit_and_approve_publishes_and_notifies(client, settings, gh):
    _submit(client)
    link = _review_link(settings)
    r = client.get(link)
    assert r.status_code == 200 and "Approve" in r.text
    assert client.get(link + "/pdf").content == PDF

    # 2026-01 is taken in the archive, so 2026-02 was proposed; the editor renumbers to 2026-03.
    r = client.post(link, data={"action": "save", "number": "2026-03", "template": ""})
    assert r.status_code == 200 and "Saved." in r.text
    sub = client.app.state.db.list()[0]
    assert sub.number == "2026-03" and "Handle: RePEc:nwc:wpaper:2026-03" in sub.template
    assert "File-URL: https://ncl-economics.github.io/papers/2026-03.pdf" in sub.template
    # and back to 2026-02 for the rest of the test
    r = client.post(link, data={"action": "regenerate", "number": "2026-02", "template": ""})
    assert r.status_code == 200
    sub = client.app.state.db.list()[0]

    # Hand edit of the template is kept.
    edited = sub.template.replace("Length: 42 pages", "Length: 43 pages")
    r = client.post(link, data={"action": "approve", "number": "2026-02", "template": edited})
    assert r.status_code == 200 and "Published" in r.text

    sub = client.app.state.db.list()[0]
    assert sub.status == "approved" and sub.commit_url.startswith("https://github.com/")
    assert len(gh.commits) == 1
    files, message = gh.commits[0]
    assert message.startswith("Add working paper 2026-02:")
    assert set(files) == {"RePEc/nwc/wpaper/nwc2026.rdf", "papers/2026-02.pdf",
                          "RePEc/nwc/wpaper/index.html"}
    rdf = files["RePEc/nwc/wpaper/nwc2026.rdf"].decode()
    assert rdf.startswith("Template-Type: ReDIF-Paper 1.0\nAuthor-Name: Lovelace, Ada")  # kept
    assert "Author-Name: Fusari, Francesco" in rdf
    assert rdf.count("Template-Type: ReDIF-Paper 1.0") == 2
    assert "\n\nTemplate-Type" in rdf and "Length: 43 pages" in rdf
    assert rdf.rstrip().endswith("Handle: RePEc:nwc:wpaper:2026-02")
    assert files["papers/2026-02.pdf"] == PDF
    index = files["RePEc/nwc/wpaper/index.html"].decode()
    assert index == gh.files["RePEc/nwc/wpaper/index.html"].decode()  # same year: unchanged

    mails = outbox(settings)
    marketing = [m for m in mails if m["To"] == "marketing@example.ac.uk"]
    assert len(marketing) == 1
    m = marketing[0]
    assert m["Cc"] == "editor@example.ac.uk"
    assert m["Subject"].startswith("New working paper: High-Frequency")
    parts = m.get_payload()
    text = parts[0].get_payload(decode=True).decode()
    assert "https://ncl-economics.github.io/papers/2026-02.pdf" in text
    assert "https://ideas.repec.org/p/nwc/wpaper/2026-02.html" in text
    assert parts[1].get_content_type() == "application/pdf"
    assert parts[1].get_filename() == "2026-02.pdf"
    assert any("has been published (2026-02)" in m["Subject"] for m in mails
               if m["To"] == "f.fusari@example.ac.uk")

    # A second approval is refused.
    r = client.post(link, data={"action": "approve", "number": "2026-02", "template": ""})
    assert r.status_code == 409 and len(gh.commits) == 1


def test_approve_refuses_duplicate_number_in_archive(client, settings, gh):
    _submit(client)
    link = _review_link(settings)
    r = client.post(link, data={"action": "approve", "number": "2026-01", "template": ""})
    assert r.status_code == 502 and "already exists" in r.text
    assert gh.commits == []
    assert client.app.state.db.list()[0].status == "pending"


def test_handle_mismatch_is_caught(client, settings, gh):
    _submit(client)
    link = _review_link(settings)
    number = client.app.state.db.list()[0].number
    bad = "Template-Type: ReDIF-Paper 1.0\nTitle: x\nHandle: RePEc:nwc:wpaper:2026-09\n"
    r = client.post(link, data={"action": "save", "number": number, "template": bad})
    assert r.status_code == 400 and "Handle line does not match" in r.text


def test_reject_notifies_submitter(client, settings, gh):
    _submit(client)
    link = _review_link(settings)
    r = client.post(link, data={"action": "reject", "number": "2026-01", "template": "",
                                "decision_note": "Please add the JEL codes."})
    assert r.status_code == 200 and "Rejected" in r.text
    sub = client.app.state.db.list()[0]
    assert sub.status == "rejected" and sub.decision_note == "Please add the JEL codes."
    assert gh.commits == []
    m = outbox(settings)[-1]
    assert m["To"] == "f.fusari@example.ac.uk" and "not accepted" in m["Subject"]
    assert "Please add the JEL codes." in m.get_payload(decode=True).decode()
    # the rejected number is free again
    _submit(client, title="Another")
    assert client.app.state.db.list()[0].number == "2026-01"


def test_admin_list_requires_auth(client, settings):
    _submit(client)
    assert client.get("/admin").status_code == 401
    r = client.get("/admin", auth=("ed", "pw"))
    assert r.status_code == 200 and "High-Frequency" in r.text
    link = re.search(r'href="(http://portal.test/review/[^"]+)"', r.text).group(1)
    assert client.get(link.replace("http://portal.test", "")).status_code == 200


def test_build_files_new_year_creates_file_and_index(settings):
    from app.db import Submission
    from app.redif import Author
    sub = Submission(submitter_name="x", submitter_email="x@y.z", title="T", abstract="A",
                     creation_date="2027-01", authors=[Author("A", "B")], pdf_path="",
                     pdf_original_name="p.pdf", number="2027-01",
                     template="Template-Type: ReDIF-Paper 1.0\nHandle: RePEc:nwc:wpaper:2027-01\n")
    files = build_files(settings, sub, PDF, None, None)
    assert files["RePEc/nwc/wpaper/nwc2027.rdf"] == sub.template.encode()
    assert "<!DOCTYPE html>" in files["RePEc/nwc/wpaper/index.html"].decode()
    assert "nwc2027.rdf" in files["RePEc/nwc/wpaper/index.html"].decode()


def test_github_publisher_single_commit():
    """Drive GitHubPublisher against a fake GitHub API and check the Git Data flow."""
    import base64, json
    import httpx
    from app.github_publisher import GitHubPublisher

    store = {"RePEc/nwc/wpaper/index.html": "<ul></ul>"}
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append((req.method, req.url.path))
        p = req.url.path
        if p.startswith("/repos/o/r/contents/"):
            path = p[len("/repos/o/r/contents/"):]
            if path not in store:
                return httpx.Response(404, json={"message": "Not Found"})
            return httpx.Response(200, json={"encoding": "base64",
                                             "content": base64.b64encode(store[path].encode()).decode()})
        if p == "/repos/o/r/git/ref/heads/main":
            return httpx.Response(200, json={"object": {"sha": "head"}})
        if p == "/repos/o/r/git/commits/head":
            return httpx.Response(200, json={"tree": {"sha": "basetree"}})
        if p == "/repos/o/r/git/blobs":
            body = json.loads(req.content)
            return httpx.Response(201, json={"sha": "blob" + str(len(body["content"]))})
        if p == "/repos/o/r/git/trees":
            body = json.loads(req.content)
            assert body["base_tree"] == "basetree" and len(body["tree"]) == 2
            return httpx.Response(201, json={"sha": "newtree"})
        if p == "/repos/o/r/git/commits":
            body = json.loads(req.content)
            assert body["parents"] == ["head"] and body["tree"] == "newtree"
            return httpx.Response(201, json={"sha": "c1", "html_url": "https://github.com/o/r/commit/c1"})
        if p == "/repos/o/r/git/refs/heads/main" and req.method == "PATCH":
            assert json.loads(req.content)["sha"] == "c1"
            return httpx.Response(200, json={})
        return httpx.Response(500, text="unexpected " + p)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    gh = GitHubPublisher("tok", "o/r", "main", client=client)
    assert client.headers["Authorization"] == "Bearer tok"
    assert gh.get_text("RePEc/nwc/wpaper/index.html") == "<ul></ul>"
    assert gh.get_text("RePEc/nwc/wpaper/nwc2026.rdf") is None
    url = gh.commit_files({"a.rdf": b"x", "b.pdf": b"yy"}, "msg")
    assert url == "https://github.com/o/r/commit/c1"
    assert ("PATCH", "/repos/o/r/git/refs/heads/main") == calls[-1]


def test_new_year_file_is_added_to_the_real_index(settings, gh):
    from app.db import Submission
    from app.redif import Author
    sub = Submission(submitter_name="x", submitter_email="x@y.z", title="T", abstract="A",
                     creation_date="2027-02", authors=[Author("A", "B")], pdf_path="",
                     pdf_original_name="p.pdf", number="2027-01",
                     template="Template-Type: ReDIF-Paper 1.0\nHandle: RePEc:nwc:wpaper:2027-01\n")
    files = build_files(settings, sub, PDF, None, gh.get_text("RePEc/nwc/wpaper/index.html"))
    index = files["RePEc/nwc/wpaper/index.html"].decode()
    assert ('<li><a href="nwc2026.rdf">nwc2026.rdf</a></li>\n'
            '<li><a href="nwc2027.rdf">nwc2027.rdf</a></li>\n</ul>') in index
    assert index.startswith("<!DOCTYPE html>\n<html>\n<head>")


def test_cover_metadata_and_hook(settings, tmp_path):
    from app.db import Submission
    from app.publish import apply_cover, cover_metadata
    from app.redif import Author
    sub = Submission(submitter_name="x", submitter_email="x@y.z", title="Fiscal anticipation",
                     abstract="A", creation_date="2026-10", pdf_path="", pdf_original_name="p.pdf",
                     number="2026-02", authors=[Author("Vedanta", "Dhamija", workplace="CFM"),
                                                Author("Francesco", "Fusari", workplace="NUBS")])
    meta = cover_metadata(sub)
    assert meta == {"title": "Fiscal anticipation", "number": "2026-02", "date": "October 2026",
                    "authors": [["Vedanta Dhamija", "CFM"], ["Francesco Fusari", "NUBS"]]}
    # a stand-in cover command: copies the input and appends the metadata file name
    script = tmp_path / "cover.py"
    script.write_text("import sys, json, shutil\n"
                      "meta = json.load(open(sys.argv[3]))\n"
                      "open(sys.argv[2], 'wb').write(open(sys.argv[1], 'rb').read() + "
                      "meta['number'].encode())\n")
    settings.cover_command = f"python3 {script} {{input}} {{output}} {{meta}}"
    assert apply_cover(settings, sub, PDF) == PDF + b"2026-02"
    settings.cover_command = ""
    assert apply_cover(settings, sub, PDF) == PDF
