# ============================================================
# FILE: backend/app/services/job_handlers.py
# Registers the background job handlers with job_runner. Imported once
# from the API router so registration happens at startup.
# ============================================================

from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.orm import Session

from backend.app.db.enums import JobTypeEnum
from backend.app.db.models.business_entity import BusinessEntity
from backend.app.services import connectors, ingestion, job_runner
from backend.app.services.status_engine import infer_business_status


@job_runner.register(JobTypeEnum.STATUS_RUN_ALL)
def _status_run_all(db: Session, payload: dict) -> Dict[str, Any]:
    rows = db.query(BusinessEntity).all()

    processed = failed = active = dormant = closed = 0
    errors: list[dict] = []

    for entity in rows:
        try:
            result = infer_business_status(db=db, business_entity_id=entity.id)
            processed += 1
            if result["status"] == "ACTIVE":
                active += 1
            elif result["status"] == "DORMANT":
                dormant += 1
            elif result["status"] == "CLOSED":
                closed += 1
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            failed += 1
            errors.append(
                {"business_id": str(entity.id), "ubid": entity.ubid_code, "error": str(exc)}
            )

    return {
        "message": "Status recomputation completed",
        "processed": processed,
        "failed": failed,
        "active": active,
        "dormant": dormant,
        "closed": closed,
        "errors": errors[:10],
    }


@job_runner.register(JobTypeEnum.PROCESS_PENDING)
def _process_pending(db: Session, payload: dict) -> Dict[str, Any]:
    limit = int(payload.get("limit") or 1000)
    return ingestion.process_pending(db, limit=limit)


@job_runner.register(JobTypeEnum.CSV_MATCH)
def _csv_match(db: Session, payload: dict) -> Dict[str, Any]:
    ids = payload.get("source_record_ids") or []
    tally = ingestion.run_matching_for_ids(db, ids)
    return {
        "auto_link": tally.auto_link,
        "review": tally.review,
        "new_entity": tally.new_entity,
        "failed": tally.failed,
    }


@job_runner.register(JobTypeEnum.SYNC_CONNECTORS)
def _sync_connectors(db: Session, payload: dict) -> Dict[str, Any]:
    """Pull connector exports; with ``full_cycle`` also match new records and refresh statuses."""
    summaries = connectors.sync_all(db, payload.get("code"))
    result: Dict[str, Any] = {
        "synced": len(summaries),
        "ok": sum(1 for s in summaries if s.get("ok")),
        "systems": summaries,
    }
    if payload.get("full_cycle"):
        result["matching"] = ingestion.process_pending(db, limit=5000)
        result["status"] = _status_run_all(db, {})
    return result
