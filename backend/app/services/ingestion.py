# ============================================================
# FILE: backend/app/services/ingestion.py
# CSV / structured ingestion of departmental source records.
# ============================================================

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass, field
from typing import Any, Iterable

from sqlalchemy.orm import Session

from backend.app.db.models.entity_record_link import EntityRecordLink
from backend.app.db.models.review_case import ReviewCase
from backend.app.db.models.source_record import SourceRecord
from backend.app.db.models.source_system import SourceSystem
from backend.app.db.enums import ReviewCaseStatusEnum
from backend.app.services.matching_engine import process_source_record
from backend.app.services.scoring import normalize_phone, normalize_pin, normalize_text

# Header aliases — a department's export rarely uses our field names.
_ALIASES: dict[str, set[str]] = {
    "external_id": {
        "externalid", "id", "recordid", "regno", "registrationno",
        "licenseno", "licenceno", "srno", "serialno",
    },
    "name": {
        "name", "businessname", "legalname", "tradename", "unitname",
        "consumername", "firmname", "establishmentname", "shopname",
    },
    "pan": {"pan", "panno", "pannumber"},
    "gstin": {"gstin", "gst", "gstno", "gstinno", "gstnumber"},
    "address": {"address", "addr", "registeredaddress", "premises", "location"},
    "pin": {"pin", "pincode", "postalcode", "zip", "zipcode"},
    "email": {"email", "emailid", "mail", "contactemail"},
    "phone": {"phone", "phoneno", "mobile", "mobileno", "contact", "contactno", "telephone", "tel"},
}


def _canon(header: str) -> str:
    return "".join(c for c in header.lower() if c.isalnum())


@dataclass
class RowError:
    row: int
    error: str


@dataclass
class MatchingTally:
    auto_link: int = 0
    review: int = 0
    new_entity: int = 0
    failed: int = 0

    def add(self, decision: str) -> None:
        key = {
            "AUTO_LINK": "auto_link",
            "REVIEW": "review",
            "NEW_ENTITY": "new_entity",
        }.get(decision)
        if key:
            setattr(self, key, getattr(self, key) + 1)


@dataclass
class IngestionReport:
    source_system: str
    rows_read: int = 0
    created: int = 0
    skipped_duplicates: int = 0
    errors: list[RowError] = field(default_factory=list)
    matching: MatchingTally | None = None
    # Set when matching was deferred to a background job instead of running
    # inline (see `run_matching_for_ids` / job_handlers.py).
    job_id: str | None = None
    new_record_ids: list = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_system": self.source_system,
            "rows_read": self.rows_read,
            "created": self.created,
            "skipped_duplicates": self.skipped_duplicates,
            "errors": [{"row": e.row, "error": e.error} for e in self.errors],
            "matching": (
                {
                    "auto_link": self.matching.auto_link,
                    "review": self.matching.review,
                    "new_entity": self.matching.new_entity,
                    "failed": self.matching.failed,
                }
                if self.matching
                else None
            ),
            "job_id": self.job_id,
        }


CSV_TEMPLATE = (
    "external_id,name,pan,gstin,address,pin,email,phone\n"
    "L-1001,Punjab Steel Works,ABCDE1234F,03ABCDE1234F1Z5,"
    '"Plot 42, Focal Point Phase 3, Ludhiana",141001,accounts@punjabsteel.example,9876543210\n'
    'L-1002,M/S Sharma Traders,,,"Shop 7, Grain Market, Patiala",147001,,\n'
)


# ------------------------------------------------------------
# Parsing
# ------------------------------------------------------------

def parse_csv(raw: bytes) -> list[dict[str, str]]:
    """Parse CSV bytes into a list of {external_id,name,pan,gstin,address,pin,...,_extra}."""
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return []
    return rows_from_dicts(reader.fieldnames, reader)


def rows_from_dicts(fieldnames: Iterable[str], dict_rows: Iterable[dict]) -> list[dict[str, Any]]:
    """Map a department's own column names onto ours (shared by CSV and JSON feeds)."""
    # map each real header to one of our canonical fields (or keep as extra)
    field_map: dict[str, str] = {}
    for header in fieldnames:
        canon = _canon(str(header))
        for target, names in _ALIASES.items():
            if canon in names:
                field_map[header] = target
                break

    rows: list[dict[str, Any]] = []
    for raw_row in dict_rows:
        row: dict[str, Any] = {
            "external_id": "", "name": "", "pan": "",
            "gstin": "", "address": "", "pin": "", "email": "", "phone": "", "_extra": {},
        }
        for header, value in raw_row.items():
            if header is None:
                continue
            value = ("" if value is None else str(value)).strip()
            target = field_map.get(header)
            if target:
                row[target] = value
            elif value:
                row["_extra"][header] = value
        rows.append(row)
    return rows


# ------------------------------------------------------------
# Ingestion
# ------------------------------------------------------------

def _row_external_id(row: dict[str, Any]) -> str:
    if row.get("external_id"):
        return str(row["external_id"])[:255]
    digest = hashlib.sha1(
        "|".join(
            str(row.get(k, "")) for k in ("name", "pan", "gstin", "address", "pin")
        ).encode()
    ).hexdigest()
    return f"auto-{digest[:16]}"


def ingest_rows(
    db: Session,
    source_system_code: str,
    rows: Iterable[dict[str, Any]],
    process: bool = True,
) -> IngestionReport:
    system = (
        db.query(SourceSystem)
        .filter(SourceSystem.code == source_system_code.upper())
        .first()
    )
    if not system:
        raise ValueError(f"Unknown source system '{source_system_code}'")

    report = IngestionReport(source_system=system.code)
    new_ids: list = []

    for i, row in enumerate(rows, start=1):
        report.rows_read += 1
        name = (row.get("name") or "").strip()
        if not name:
            report.errors.append(RowError(i, "missing business name"))
            continue

        external_id = _row_external_id(row)
        exists = (
            db.query(SourceRecord.id)
            .filter(
                SourceRecord.source_system_id == system.id,
                SourceRecord.external_id == external_id,
            )
            .first()
        )
        if exists:
            report.skipped_duplicates += 1
            continue

        pin = normalize_pin(row.get("pin")) or None
        sr = SourceRecord(
            source_system_id=system.id,
            external_id=external_id,
            raw_payload={"name": name, **row.get("_extra", {})},
            normalized_payload={"name": normalize_text(name)},
            extracted_name=name,
            extracted_pan=(row.get("pan") or "").strip().upper() or None,
            extracted_gstin=(row.get("gstin") or "").strip().upper() or None,
            extracted_address=(row.get("address") or "").strip() or None,
            extracted_pin=pin,
            extracted_email=(row.get("email") or "").strip().lower()[:255] or None,
            extracted_phone=normalize_phone(row.get("phone")) or None,
        )
        db.add(sr)
        try:
            db.flush()
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            report.errors.append(RowError(i, str(exc)))
            continue

        report.created += 1
        new_ids.append(sr.id)

    db.commit()

    report.new_record_ids = [str(rid) for rid in new_ids]

    if process and new_ids:
        report.matching = run_matching_for_ids(db, new_ids)

    return report


def run_matching_for_ids(db: Session, ids: Iterable) -> MatchingTally:
    """Run the matcher over an explicit list of source_record ids.

    Shared by the synchronous `ingest_rows(process=True)` path and the
    CSV_MATCH background job handler.
    """
    tally = MatchingTally()
    for rid in ids:
        try:
            result = process_source_record(db, rid)
            tally.add(result["decision"])
        except Exception:  # noqa: BLE001
            db.rollback()
            tally.failed += 1
    return tally


def process_pending(db: Session, limit: int = 1000) -> dict[str, Any]:
    """Run the matcher over source records that are neither linked nor in review."""
    linked = db.query(EntityRecordLink.source_record_id)
    in_review = db.query(ReviewCase.source_record_id).filter(
        ReviewCase.status == ReviewCaseStatusEnum.OPEN
    )
    pending = (
        db.query(SourceRecord.id)
        .filter(SourceRecord.id.notin_(linked))
        .filter(SourceRecord.id.notin_(in_review))
        .limit(limit)
        .all()
    )

    tally = run_matching_for_ids(db, [rid for (rid,) in pending])

    return {
        "processed": tally.auto_link + tally.review + tally.new_entity,
        "auto_link": tally.auto_link,
        "review": tally.review,
        "new_entity": tally.new_entity,
        "failed": tally.failed,
    }


def pending_count(db: Session) -> int:
    linked = db.query(EntityRecordLink.source_record_id)
    in_review = db.query(ReviewCase.source_record_id).filter(
        ReviewCase.status == ReviewCaseStatusEnum.OPEN
    )
    return (
        db.query(SourceRecord.id)
        .filter(SourceRecord.id.notin_(linked))
        .filter(SourceRecord.id.notin_(in_review))
        .count()
    )
