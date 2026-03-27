from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date

from .odoo_client import OdooAuthError, OdooCredentials, OdooQueryError, fetch_contact_updates


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Query Odoo for contacts with note/activity updates and print the results.",
    )
    parser.add_argument("--odoo-url", default=os.getenv("ODOO_URL", "").strip())
    parser.add_argument("--odoo-db", default=os.getenv("ODOO_DB", "").strip())
    parser.add_argument("--odoo-username", default=os.getenv("ODOO_USERNAME", "").strip())
    parser.add_argument("--odoo-password", default=os.getenv("ODOO_PASSWORD", "").strip())
    parser.add_argument("--start-date", default="")
    parser.add_argument("--end-date", default="")
    parser.add_argument("--timezone", default=os.getenv("TIMEZONE_NAME", "America/Regina").strip())
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output style for terminal testing.",
    )
    return parser.parse_args()


def _parse_iso_date(value: str) -> date | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    return date.fromisoformat(cleaned)


def _require(value: str, name: str) -> str:
    if value.strip():
        return value.strip()
    raise ValueError(f"Missing required value for {name}")


def _print_table(records: list[dict[str, object]]) -> None:
    if not records:
        print("No matching contacts found.")
        return

    for index, record in enumerate(records, start=1):
        print(f"{index}. {record['name']} (ID: {record['partner_id']})")
        print(f"   Updated: {record['last_update_at']}")
        print(f"   Sources: {', '.join(record['update_sources']) or '-'}")
        print(f"   Company: {record['company_name'] or record['parent_company'] or '-'}")
        print(f"   Email: {record['email'] or '-'}")
        print(f"   Phone: {record['phone'] or record['mobile'] or '-'}")
        print(f"   Latest note: {record['latest_note_preview'] or '-'}")
        print(
            "   Latest activity: "
            f"{record['latest_activity_summary'] or record['latest_activity_note'] or '-'}"
        )
        print("")


def main() -> int:
    args = _parse_args()

    try:
        start_date, end_date, contacts = fetch_contact_updates(
            OdooCredentials(
                url=_require(args.odoo_url, "--odoo-url or ODOO_URL"),
                db=_require(args.odoo_db, "--odoo-db or ODOO_DB"),
                username=_require(args.odoo_username, "--odoo-username or ODOO_USERNAME"),
                password=_require(args.odoo_password, "--odoo-password or ODOO_PASSWORD"),
            ),
            start_date=_parse_iso_date(args.start_date),
            end_date=_parse_iso_date(args.end_date),
            timezone_name=args.timezone,
            limit=args.limit,
        )
    except (ValueError, OdooAuthError, OdooQueryError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(
        f"Found {len(contacts)} contact(s) from {start_date.isoformat()} to {end_date.isoformat()} "
        f"using timezone {args.timezone}."
    )

    contact_rows = [contact.model_dump() for contact in contacts]
    if args.format == "json":
        print(json.dumps(contact_rows, indent=2))
    else:
        print("")
        _print_table(contact_rows)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
