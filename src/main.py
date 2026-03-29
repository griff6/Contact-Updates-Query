from __future__ import annotations

import os
import secrets

from fastapi import FastAPI, HTTPException
from fastapi import Header
from fastapi.middleware.cors import CORSMiddleware

from .models import ContactUpdatesQueryRequest, ContactUpdatesQueryResponse
from .odoo_client import OdooAuthError, OdooCredentials, OdooQueryError, fetch_contact_updates


app = FastAPI(
    title="Contact Updates Query Builder API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


def _required_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if value:
        return value
    raise HTTPException(status_code=500, detail=f"Server is missing required environment variable: {name}")


def _get_odoo_credentials() -> OdooCredentials:
    return OdooCredentials(
        url=_required_env("ODOO_URL").rstrip("/"),
        db=_required_env("ODOO_DB"),
        username=_required_env("ODOO_USERNAME"),
        password=_required_env("ODOO_PASSWORD"),
    )


def _verify_internal_token(x_internal_token: str | None) -> None:
    expected = _required_env("INTERNAL_API_TOKEN")
    provided = (x_internal_token or "").strip()
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.post("/api/contact-updates/query", response_model=ContactUpdatesQueryResponse)
def query_contact_updates(
    payload: ContactUpdatesQueryRequest,
    x_internal_token: str | None = Header(default=None),
) -> ContactUpdatesQueryResponse:
    try:
        _verify_internal_token(x_internal_token)
        print(
            "INFO contact_updates_query:",
            {
                "start_date": str(payload.start_date),
                "end_date": str(payload.end_date),
                "updated_by_name": payload.updated_by_name,
                "contact_scope": payload.contact_scope,
                "timezone_name": payload.timezone_name,
                "limit": payload.limit,
            },
            flush=True,
        )
        start_date, end_date, contacts = fetch_contact_updates(
            _get_odoo_credentials(),
            start_date=payload.start_date,
            end_date=payload.end_date,
            updated_by_name=payload.updated_by_name,
            contact_scope=payload.contact_scope,
            timezone_name=payload.timezone_name,
            limit=payload.limit,
        )
        print(
            "INFO contact_updates_result:",
            {
                "updated_by_name": payload.updated_by_name,
                "contact_scope": payload.contact_scope,
                "contact_count": len(contacts),
            },
            flush=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OdooAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except OdooQueryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ContactUpdatesQueryResponse(
        start_date=start_date,
        end_date=end_date,
        timezone_name=payload.timezone_name,
        contact_count=len(contacts),
        contacts=contacts,
    )
