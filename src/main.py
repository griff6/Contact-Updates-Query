from __future__ import annotations

from fastapi import FastAPI, HTTPException
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


@app.post("/api/contact-updates/query", response_model=ContactUpdatesQueryResponse)
def query_contact_updates(payload: ContactUpdatesQueryRequest) -> ContactUpdatesQueryResponse:
    try:
        start_date, end_date, contacts = fetch_contact_updates(
            OdooCredentials(
                url=payload.odoo_url,
                db=payload.odoo_db,
                username=payload.odoo_username,
                password=payload.odoo_password,
            ),
            start_date=payload.start_date,
            end_date=payload.end_date,
            timezone_name=payload.timezone_name,
            limit=payload.limit,
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

