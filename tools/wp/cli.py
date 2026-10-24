"""Command-line entry points used by the GitHub Actions workflows.

    python3 tools/wp/cli.py preview --issue-json-env ISSUE_JSON --out wp-preview.md
    python3 tools/wp/cli.py publish --issue-json issue.json --result wp-result.json --email wp-email.txt
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # make 'wp' importable

from wp import pipeline  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def _issue_body(args) -> str:
    if args.issue_json_env:
        data = json.loads(os.environ[args.issue_json_env])
    else:
        data = json.loads(Path(args.issue_json).read_text(encoding="utf-8"))
    return data.get("body") or ""


def _set_outputs(values: dict[str, str]) -> None:
    """Expose values as step outputs when running inside GitHub Actions."""
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        for k, v in values.items():
            f.write(f"{k}={str(v).replace(chr(10), ' ')}\n")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="wp")
    sp = p.add_subparsers(dest="cmd", required=True)
    for name in ("preview", "publish"):
        c = sp.add_parser(name)
        c.add_argument("--issue-json", help="file with the issue JSON (GitHub API shape)")
        c.add_argument("--issue-json-env", help="environment variable holding the issue JSON")
        c.add_argument("--root", default=str(ROOT), help="repository root (default: this repo)")
    sp.choices["preview"].add_argument("--out", required=True)
    sp.choices["preview"].add_argument("--no-pdf-check", action="store_true",
                                       help="do not try to fetch the PDF link")
    sp.choices["publish"].add_argument("--result", required=True)
    sp.choices["publish"].add_argument("--email", required=True)
    sp.choices["publish"].add_argument("--no-cover", action="store_true")
    args = p.parse_args(argv)
    if not (args.issue_json or args.issue_json_env):
        p.error("--issue-json or --issue-json-env is required")
    root = Path(args.root)
    body = _issue_body(args)

    if args.cmd == "preview":
        download = (lambda url, dest: dest.write_bytes(b"%PDF-skipped")) if args.no_pdf_check else None
        Path(args.out).write_text(pipeline.preview_markdown(body, root, download=download),
                                  encoding="utf-8")
        return 0

    try:
        result = pipeline.publish(body, root, cover=not args.no_cover)
    except ValueError as exc:
        print(f"::error::{exc}")
        return 1
    Path(args.result).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    Path(args.email).write_text(result["email_body"], encoding="utf-8")
    _set_outputs({k: result[k] for k in ("number", "title", "subject", "pdf_url",
                                          "ideas_url", "econpapers_url", "handle")})
    print(f"Published {result['number']}: {result['title']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
