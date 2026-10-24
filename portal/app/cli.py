"""Small command-line helpers.

    python -m app.cli secrets          # print fresh SECRET_KEY and ADMIN_PASSWORD values
    python -m app.cli init-templates --name "..." --maintainer-name "..." \
        --maintainer-email ... --provider-homepage ... --provider-institution RePEc:edi:xxxxxx
"""
from __future__ import annotations

import argparse
import secrets

from .config import Settings
from .redif import archive_template, series_template


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="wp-portal")
    sp = p.add_subparsers(dest="cmd", required=True)
    sp.add_parser("secrets", help="print random values for SECRET_KEY and ADMIN_PASSWORD")
    t = sp.add_parser("init-templates", help="print the archive and series ReDIF templates")
    t.add_argument("--name", required=True, help="archive name, e.g. 'Newcastle University Economics'")
    t.add_argument("--maintainer-name", required=True)
    t.add_argument("--maintainer-email", required=True)
    t.add_argument("--provider-name", default=None)
    t.add_argument("--provider-homepage", required=True)
    t.add_argument("--provider-institution", required=True, help="EDIRC handle, e.g. RePEc:edi:dencluk")
    t.add_argument("--description", default="")
    args = p.parse_args(argv)

    if args.cmd == "secrets":
        print(f"SECRET_KEY={secrets.token_urlsafe(48)}")
        print(f"ADMIN_PASSWORD={secrets.token_urlsafe(16)}")
        return

    s = Settings.from_env()
    if args.cmd == "init-templates":
        print(f"# {s.archive_code}arch.rdf")
        print(archive_template(s, args.name, args.maintainer_name, args.maintainer_email,
                               args.description))
        print(f"# {s.archive_code}seri.rdf")
        print(series_template(s, args.provider_name or args.name, args.provider_homepage,
                              args.provider_institution, args.maintainer_name,
                              args.maintainer_email))


if __name__ == "__main__":
    main()
