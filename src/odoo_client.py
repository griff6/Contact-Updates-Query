from __future__ import annotations

import html
import re
import xmlrpc.client
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .models import ContactActivityRecord, ContactNoteRecord, ContactUpdateRecord


BODY_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")
LINEBREAK_TAG_RE = re.compile(r"(?i)<\s*br\s*/?\s*>|<\s*/p\s*>|<\s*/div\s*>")
MULTI_NEWLINE_RE = re.compile(r"\n{3,}")


class OdooAuthError(Exception):
    pass


class OdooQueryError(Exception):
    pass


@dataclass(slots=True)
class OdooCredentials:
    url: str
    db: str
    username: str
    password: str


def resolve_date_range(
    start_date: date | None,
    end_date: date | None,
    timezone_name: str,
) -> tuple[date, date, datetime, datetime]:
    tz = ZoneInfo(timezone_name)
    today = datetime.now(tz).date()

    if end_date is None:
        end_date = today
    if start_date is None:
        start_date = end_date - timedelta(days=6)
    if start_date > end_date:
        raise ValueError("start_date cannot be after end_date")

    start_local = datetime.combine(start_date, time.min, tzinfo=tz)
    end_local = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=tz)
    return start_date, end_date, start_local.astimezone(UTC), end_local.astimezone(UTC)


def _dt_to_odoo(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _text_from_html(value: Any, preserve_newlines: bool = False) -> str:
    raw = str(value or "")
    if preserve_newlines:
        raw = LINEBREAK_TAG_RE.sub("\n", raw)
        raw = BODY_TAG_RE.sub(" ", raw)
        raw = html.unescape(raw)
        raw = raw.replace("\r", "")
        raw = re.sub(r"[ \t]+\n", "\n", raw)
        raw = re.sub(r"\n[ \t]+", "\n", raw)
        raw = MULTI_NEWLINE_RE.sub("\n\n", raw)
        return raw.strip()

    raw = html.unescape(BODY_TAG_RE.sub(" ", raw))
    return WHITESPACE_RE.sub(" ", raw).strip()


def _m2o_name(value: Any) -> str:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return str(value[1] or "").strip()
    return ""


def _normalized_person_name(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).casefold()


def _normalized_scope(value: str) -> str:
    return re.sub(r"[\s_]+", "", (value or "").strip()).casefold()


def _execute_kw(
    models: Any,
    credentials: OdooCredentials,
    uid: int,
    model: str,
    method: str,
    args: list[Any],
    kwargs: dict[str, Any] | None = None,
) -> Any:
    kwargs = kwargs or {}
    try:
        return models.execute_kw(
            credentials.db,
            uid,
            credentials.password,
            model,
            method,
            args,
            kwargs,
        )
    except xmlrpc.client.Fault as exc:
        raise OdooQueryError(f"Odoo query failed on {model}.{method}: {exc.faultString}") from exc
    except Exception as exc:
        raise OdooQueryError(f"Odoo query failed on {model}.{method}: {exc}") from exc


def _get_model_fields(
    models: Any,
    credentials: OdooCredentials,
    uid: int,
    model: str,
) -> set[str]:
    fields = _execute_kw(
        models,
        credentials,
        uid,
        model,
        "fields_get",
        [],
        {"attributes": ["string"]},
    )
    if not isinstance(fields, dict):
        raise OdooQueryError(f"Odoo returned an unexpected fields_get response for {model}.")
    return set(fields)


def _filter_existing_fields(
    models: Any,
    credentials: OdooCredentials,
    uid: int,
    model: str,
    fields: list[str],
) -> list[str]:
    existing_fields = _get_model_fields(models, credentials, uid, model)
    return [field for field in fields if field == "id" or field in existing_fields]


def connect_odoo(credentials: OdooCredentials) -> tuple[int, Any]:
    try:
        common = xmlrpc.client.ServerProxy(
            f"{credentials.url}/xmlrpc/2/common",
            allow_none=True,
            use_datetime=True,
        )
        uid = common.authenticate(
            credentials.db,
            credentials.username,
            credentials.password,
            {},
        )
        if not uid:
            raise OdooAuthError("Authentication failed. Check the Odoo database and credentials.")
        models = xmlrpc.client.ServerProxy(
            f"{credentials.url}/xmlrpc/2/object",
            allow_none=True,
            use_datetime=True,
        )
        return int(uid), models
    except OdooAuthError:
        raise
    except Exception as exc:
        raise OdooQueryError(f"Failed to connect to Odoo: {exc}") from exc


def _search_read_all(
    models: Any,
    credentials: OdooCredentials,
    uid: int,
    model: str,
    domain: list[Any],
    fields: list[str],
    order: str,
    page_size: int = 200,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0

    while True:
        remaining = None if limit is None else max(limit - len(rows), 0)
        if remaining == 0:
            break

        fetch_size = page_size if remaining is None else min(page_size, remaining)
        batch = _execute_kw(
            models,
            credentials,
            uid,
            model,
            "search_read",
            [domain],
            {
                "fields": fields,
                "order": order,
                "limit": fetch_size,
                "offset": offset,
            },
        )
        if not batch:
            break

        rows.extend(batch)
        offset += len(batch)
        if len(batch) < fetch_size:
            break

    return rows


def _fetch_partner_notes(
    models: Any,
    credentials: OdooCredentials,
    uid: int,
    start_utc: datetime,
    end_utc: datetime,
    updated_by_name: str = "",
) -> dict[int, dict[str, Any]]:
    rows = _search_read_all(
        models,
        credentials,
        uid,
        "mail.message",
        [
            ("model", "=", "res.partner"),
            ("message_type", "=", "comment"),
            ("write_date", ">=", _dt_to_odoo(start_utc)),
            ("write_date", "<", _dt_to_odoo(end_utc)),
        ],
        ["res_id", "subject", "body", "write_date", "subtype_id", "author_id"],
        "write_date desc",
    )

    notes_by_partner: dict[int, dict[str, Any]] = {}
    filter_name = _normalized_person_name(updated_by_name)
    for row in rows:
        partner_id = int(row.get("res_id") or 0)
        if not partner_id:
            continue

        subtype_name = _m2o_name(row.get("subtype_id")).lower()
        if subtype_name and "note" not in subtype_name:
            continue

        author_name = _m2o_name(row.get("author_id"))
        if filter_name and _normalized_person_name(author_name) != filter_name:
            continue

        note_at = str(row.get("write_date") or "")
        note_subject = str(row.get("subject") or "").strip()
        note_text = _text_from_html(row.get("body"), preserve_newlines=True)

        note_entry = ContactNoteRecord(
            note_at=note_at,
            subject=note_subject,
            text=note_text,
            author_name=author_name,
        )

        existing = notes_by_partner.setdefault(
            partner_id,
            {
                "latest_note_at": "",
                "latest_note_subject": "",
                "latest_note_text": "",
                "notes": [],
            },
        )
        existing["notes"].append(note_entry)

        if not existing["latest_note_at"]:
            existing["latest_note_at"] = note_at
            existing["latest_note_subject"] = note_subject
            existing["latest_note_text"] = note_text

    return notes_by_partner


def _fetch_partner_activities(
    models: Any,
    credentials: OdooCredentials,
    uid: int,
    start_utc: datetime,
    end_utc: datetime,
    updated_by_name: str = "",
) -> dict[int, dict[str, Any]]:
    rows = _search_read_all(
        models,
        credentials,
        uid,
        "mail.activity",
        [
            ("res_model", "=", "res.partner"),
            ("write_date", ">=", _dt_to_odoo(start_utc)),
            ("write_date", "<", _dt_to_odoo(end_utc)),
        ],
        ["res_id", "summary", "note", "write_date", "user_id"],
        "write_date desc",
    )

    activities_by_partner: dict[int, dict[str, Any]] = {}
    filter_name = _normalized_person_name(updated_by_name)
    for row in rows:
        partner_id = int(row.get("res_id") or 0)
        if not partner_id:
            continue

        user_name = _m2o_name(row.get("user_id"))
        if filter_name and _normalized_person_name(user_name) != filter_name:
            continue

        activity_at = str(row.get("write_date") or "")
        activity_summary = str(row.get("summary") or "").strip()
        activity_note = _text_from_html(row.get("note"), preserve_newlines=True)

        activity_entry = ContactActivityRecord(
            activity_at=activity_at,
            summary=activity_summary,
            note=activity_note,
            user_name=user_name,
        )

        existing = activities_by_partner.setdefault(
            partner_id,
            {
                "latest_activity_at": "",
                "latest_activity_summary": "",
                "latest_activity_note": "",
                "activities": [],
            },
        )
        existing["activities"].append(activity_entry)

        if not existing["latest_activity_at"]:
            existing["latest_activity_at"] = activity_at
            existing["latest_activity_summary"] = activity_summary
            existing["latest_activity_note"] = activity_note

    return activities_by_partner


def _fetch_partners(
    models: Any,
    credentials: OdooCredentials,
    uid: int,
    partner_ids: list[int],
    contact_scope: str,
) -> dict[int, dict[str, Any]]:
    if not partner_ids:
        return {}

    scope = _normalized_scope(contact_scope)
    domain: list[Any] = [("id", "in", partner_ids)]

    if scope in {"companies", "company", "companiesonly"}:
        domain.append(("is_company", "=", True))
    elif scope in {"coop", "co-op"}:
        tag_rows = _execute_kw(
            models,
            credentials,
            uid,
            "res.partner.category",
            "search_read",
            [[("name", "=", "Co Op")]],
            {"fields": ["id"], "limit": 10},
        )
        tag_ids = [int(row["id"]) for row in tag_rows if row.get("id")]
        if not tag_ids:
            return {}
        domain.append(("category_id", "in", tag_ids))

    partner_fields = _filter_existing_fields(
        models,
        credentials,
        uid,
        "res.partner",
        ["id", "name", "email", "phone", "mobile", "company_name", "parent_id", "write_date", "is_company"],
    )
    rows = _search_read_all(
        models,
        credentials,
        uid,
        "res.partner",
        domain,
        partner_fields,
        "name asc",
    )
    return {int(row["id"]): row for row in rows if row.get("id")}


def fetch_contact_updates(
    credentials: OdooCredentials,
    start_date: date | None,
    end_date: date | None,
    updated_by_name: str,
    contact_scope: str,
    timezone_name: str,
    limit: int,
) -> tuple[date, date, list[ContactUpdateRecord]]:
    resolved_start, resolved_end, start_utc, end_utc = resolve_date_range(
        start_date,
        end_date,
        timezone_name,
    )
    uid, models = connect_odoo(credentials)

    notes_by_partner = _fetch_partner_notes(
        models,
        credentials,
        uid,
        start_utc,
        end_utc,
        updated_by_name=updated_by_name,
    )
    activities_by_partner = _fetch_partner_activities(
        models,
        credentials,
        uid,
        start_utc,
        end_utc,
        updated_by_name=updated_by_name,
    )

    partner_ids = sorted(set(notes_by_partner) | set(activities_by_partner))
    partners = _fetch_partners(models, credentials, uid, partner_ids, contact_scope=contact_scope)

    records: list[ContactUpdateRecord] = []
    for partner_id in partner_ids:
        partner = partners.get(partner_id)
        if not partner:
            continue

        note_info = notes_by_partner.get(partner_id, {})
        activity_info = activities_by_partner.get(partner_id, {})
        timestamps = [
            value
            for value in [
                note_info.get("latest_note_at", ""),
                activity_info.get("latest_activity_at", ""),
                str(partner.get("write_date") or ""),
            ]
            if value
        ]

        sources: list[str] = []
        if note_info:
            sources.append("note")
        if activity_info:
            sources.append("activity")

        latest_note_text = note_info.get("latest_note_text", "")

        records.append(
            ContactUpdateRecord(
                partner_id=partner_id,
                name=str(partner.get("name") or ""),
                email=str(partner.get("email") or ""),
                phone=str(partner.get("phone") or ""),
                mobile=str(partner.get("mobile") or ""),
                company_name=str(partner.get("company_name") or ""),
                parent_company=_m2o_name(partner.get("parent_id")),
                partner_write_date=str(partner.get("write_date") or ""),
                last_update_at=max(timestamps) if timestamps else "",
                update_sources=sources,
                latest_note_at=note_info.get("latest_note_at", ""),
                latest_note_subject=note_info.get("latest_note_subject", ""),
                latest_note_text=latest_note_text,
                latest_note_preview=latest_note_text,
                latest_activity_at=activity_info.get("latest_activity_at", ""),
                latest_activity_summary=activity_info.get("latest_activity_summary", ""),
                latest_activity_note=activity_info.get("latest_activity_note", ""),
                notes=note_info.get("notes", []),
                activities=activity_info.get("activities", []),
            )
        )

    records.sort(key=lambda row: (row.last_update_at, row.name.lower()), reverse=True)
    return resolved_start, resolved_end, records[:limit]
