from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator


class ContactUpdatesQueryRequest(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    updated_by_name: str = ""
    timezone_name: str = "America/Regina"
    limit: int = 250

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("limit must be greater than 0")
        if value > 1000:
            raise ValueError("limit must be 1000 or less")
        return value


class ContactUpdateRecord(BaseModel):
    partner_id: int
    name: str
    email: str = ""
    phone: str = ""
    mobile: str = ""
    company_name: str = ""
    parent_company: str = ""
    partner_write_date: str = ""
    last_update_at: str = ""
    update_sources: list[str] = Field(default_factory=list)
    latest_note_at: str = ""
    latest_note_subject: str = ""
    latest_note_text: str = ""
    latest_note_preview: str = ""
    latest_activity_at: str = ""
    latest_activity_summary: str = ""
    latest_activity_note: str = ""
    notes: list["ContactNoteRecord"] = Field(default_factory=list)
    activities: list["ContactActivityRecord"] = Field(default_factory=list)


class ContactNoteRecord(BaseModel):
    note_at: str = ""
    subject: str = ""
    text: str = ""
    author_name: str = ""


class ContactActivityRecord(BaseModel):
    activity_at: str = ""
    summary: str = ""
    note: str = ""
    user_name: str = ""


class ContactUpdatesQueryResponse(BaseModel):
    start_date: date
    end_date: date
    timezone_name: str
    contact_count: int
    contacts: list[ContactUpdateRecord]
