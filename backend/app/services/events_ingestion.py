# ============================================================
# FILE: backend/app/services/events_ingestion.py
# Departmental activity feeds (GST filings, licence renewals, inspections,
# power usage ...) -> ActivityEvent rows, which the status engine turns into
# Active / Dormant / Closed. Re-sending the same feed is harmless.
# ============================================================

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.db.enums import EventTypeEnum
from backend.app.db.models.activity_event import ActivityEvent
from backend.app.db.models.business_entity import BusinessEntity
from backend.app.db.models.entity_record_link import EntityRecordLink
from backend.app.db.models.source_record import SourceRecord
from backend.app.db.models.source_system import SourceSystem
from backend.app.services.event_scoring import EVENT_BASE_WEIGHTS
from backend.app.services.status_engine import infer_business_status

# Recomputing inline keeps the feed -> status loop immediate for small feeds;
# larger ones are left to the next scheduled recompute.
INLINE_RECOMPUTE_LIMIT = 200

_ALIASES: dict[str, set[str]] = {
    "ubid": {"ubid", "ubidcode", "ubidno"},
    "gstin": {"gstin", "gst", "gstno", "gstinno"},
    "pan": {"pan", "panno"},
    "external_id": {"externalid", "recordid", "regno", "registrationno", "licenseno", "licenceno", "id"},
    "event_type": {"eventtype", "event", "type", "activity", "activitytype"},
    "occurred_at": {"occurredat", "date", "eventdate", "filedon", "filingdate", "activitydate"},
}

EVENTS_CSV_TEMPLATE = (
    "ubid,gstin,external_id,event_type,occurred_at\n"
    "UBID000001,,,gst_filed,2026-09-30\n"
    ",03ABCDE1234F1Z5,,inspection,2026-08-14\n"
    ",,L-1001,license_renewed,2026-07-01\n"
)


@dataclass
class EventRowError:
    row: int
    error: str


@dataclass
class EventsReport:
    rows_read: int = 0
    created: int = 0
    skipped_duplicates: int = 0
    unresolved: int = 0
    errors: list[EventRowError] = field(default_factory=list)
    recomputed: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "rows_read": self.rows_read,
            "created": self.created,
            "skipped_duplicates": self.skipped_duplicates,
            "unresolved": self.unresolved,
            "errors": [{"row": e.row, "error": e.error} for e in self.errors[:50]],
            "recomputed": self.recomputed,
        }


def _canon(header: str) -> str:
    return "".join(c for c in header.lower() if c.isalnum())


def parse_events_csv(raw: bytes) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig", errors="replace")))
    if not reader.fieldnames:
        return []
    return event_rows_from_dicts(reader.fieldnames, reader)


def event_rows_from_dicts(fieldnames: Iterable[str], dict_rows: Iterable[dict]) -> list[dict[str, str]]:
    field_map = {
        h: target
        for h in fieldnames
        for target, names in _ALIASES.items()
        if _canon(str(h)) in names
    }
    rows = []
    for raw_row in dict_rows:
        row = {k: "" for k in _ALIASES}
        for header, value in raw_row.items():
            if header in field_map:
                row[field_map[header]] = ("" if value is None else str(value)).strip()
        rows.append(row)
    return rows


def _parse_date(value: str) -> datetime:
    text = (value or "").strip()
    if not text:
        raise ValueError("missing date")
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"unrecognised date '{text}' (use YYYY-MM-DD)")
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _parse_type(value: str) -> EventTypeEnum:
    key = (value or "").strip().lower().replace(" ", "_").replace("-", "_")
    try:
        return EventTypeEnum(key)
    except ValueError:
        allowed = ", ".join(e.value for e in EventTypeEnum)
        raise ValueError(f"unknown event_type '{value}' (one of: {allowed})")


def _resolve_entity(db: Session, row: dict[str, Any], default_system: SourceSystem | None):
    """The business an event row is about: UBID, else GSTIN, else PAN, else the
    department's own record id (via the record's link)."""
    ubid = (row.get("ubid") or "").strip().upper()
    if ubid:
        return db.query(BusinessEntity).filter(BusinessEntity.ubid_code == ubid).first()
    gstin = (row.get("gstin") or "").strip().upper()
    if gstin:
        return db.query(BusinessEntity).filter(BusinessEntity.gstin == gstin).first()
    pan = (row.get("pan") or "").strip().upper()
    if pan:
        return db.query(BusinessEntity).filter(BusinessEntity.pan == pan).first()
    external_id = (row.get("external_id") or "").strip()
    if external_id and default_system is not None:
        return (
            db.query(BusinessEntity)
            .join(EntityRecordLink, EntityRecordLink.business_entity_id == BusinessEntity.id)
            .join(SourceRecord, SourceRecord.id == EntityRecordLink.source_record_id)
            .filter(
                SourceRecord.source_system_id == default_system.id,
                SourceRecord.external_id == external_id,
            )
            .first()
        )
    return None


def ingest_events(
    db: Session,
    rows: Iterable[dict[str, Any]],
    source_system_code: str | None = None,
) -> EventsReport:
    system = None
    if source_system_code:
        system = (
            db.query(SourceSystem)
            .filter(SourceSystem.code == source_system_code.upper())
            .first()
        )
        if system is None:
            raise ValueError(f"Unknown source system '{source_system_code}'")

    report = EventsReport()
    touched: set[UUID] = set()

    for i, row in enumerate(rows, start=1):
        report.rows_read += 1
        try:
            event_type = _parse_type(str(row.get("event_type") or ""))
            occurred_at = _parse_date(str(row.get("occurred_at") or ""))
        except ValueError as exc:
            report.errors.append(EventRowError(i, str(exc)))
            continue

        entity = _resolve_entity(db, row, system)
        if entity is None:
            report.unresolved += 1
            report.errors.append(
                EventRowError(i, "no matching business (give a ubid, gstin, pan or known external_id)")
            )
            continue

        duplicate = (
            db.query(ActivityEvent.id)
            .filter(
                ActivityEvent.business_entity_id == entity.id,
                ActivityEvent.event_type == event_type,
                ActivityEvent.occurred_at == occurred_at,
            )
            .first()
        )
        if duplicate:
            report.skipped_duplicates += 1
            continue

        db.add(
            ActivityEvent(
                business_entity_id=entity.id,
                event_type=event_type,
                score=EVENT_BASE_WEIGHTS.get(event_type.name, 0.0),
                occurred_at=occurred_at,
                payload={"source": system.code if system else "api"},
            )
        )
        db.flush()
        touched.add(entity.id)
        report.created += 1

    db.commit()

    if len(touched) <= INLINE_RECOMPUTE_LIMIT:
        for entity_id in touched:
            try:
                infer_business_status(db, entity_id)
                report.recomputed += 1
            except Exception:  # noqa: BLE001 - a bad entity must not fail the whole feed
                db.rollback()
    return report
