# ============================================================
# FILE: backend/app/services/status_engine.py
# ============================================================

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.services.event_scoring import (
    HARD_CLOSURE_EVENTS,
    score_event,
)
from backend.app.services.snapshot_service import save_status_snapshot

from backend.app.db.models.business_entity import BusinessEntity
from backend.app.db.models.activity_event import ActivityEvent
from backend.app.db.enums import EntityStatusEnum


# ------------------------------------------------------------
# Thresholds (on the recency-weighted average event score)
# ------------------------------------------------------------

ACTIVE_THRESHOLD = 0.45
DORMANT_THRESHOLD = 0.15
RECENT_DENSITY_BONUS = 0.10
RECENT_DENSITY_MIN_EVENTS = 3


# ============================================================
# PUBLIC API
# ============================================================

def infer_business_status(
    db: Session,
    business_entity_id: str,
) -> Dict[str, Any]:
    """Infer one business status from its activity stream and persist it."""

    entity = db.get(BusinessEntity, business_entity_id)
    if not entity:
        raise ValueError("BusinessEntity not found")

    try:
        events = _fetch_events(db, business_entity_id)
        result = _infer_from_events(events)

        reasons = list(result["reasons"])
        if entity.status_locked:
            reasons.insert(
                0,
                f"Status pinned to {entity.status.value if hasattr(entity.status, 'value') else entity.status} "
                f"by reviewer — engine opinion recorded only",
            )

        save_status_snapshot(
            db=db,
            business_entity_id=entity.id,
            status=result["status_enum"],
            confidence=result["confidence"],
            reasons=reasons,
        )

        if not entity.status_locked:
            entity.status = result["status_enum"]
        db.commit()

        effective = (
            (entity.status.value if hasattr(entity.status, "value") else str(entity.status)).upper()
            if entity.status_locked
            else result["status"]
        )
        return {
            "business_entity_id": str(entity.id),
            "ubid_code": entity.ubid_code,
            "status": effective,
            "engine_status": result["status"],
            "locked": bool(entity.status_locked),
            "confidence": result["confidence"],
            "reasons": reasons,
        }

    except Exception:
        db.rollback()
        raise


def infer_all_businesses(
    db: Session,
    limit: int | None = None,
) -> List[Dict[str, Any]]:
    query = db.query(BusinessEntity)
    if limit:
        query = query.limit(limit)

    results = []
    for entity in query.all():
        try:
            results.append(infer_business_status(db, entity.id))
        except Exception:
            db.rollback()
    return results


# ============================================================
# INTERNALS
# ============================================================

def _fetch_events(
    db: Session,
    business_entity_id: str,
) -> List[ActivityEvent]:
    return (
        db.query(ActivityEvent)
        .filter(ActivityEvent.business_entity_id == business_entity_id)
        .order_by(func.coalesce(ActivityEvent.occurred_at, ActivityEvent.created_at).desc())
        .all()
    )


def _event_type_value(event: ActivityEvent) -> str:
    et = event.event_type
    return et.value if hasattr(et, "value") else str(et)


def _infer_from_events(events: List[ActivityEvent]) -> Dict[str, Any]:
    if not events:
        # No evidence either way is not evidence of closure.
        return {
            "status": "UNKNOWN",
            "status_enum": EntityStatusEnum.UNKNOWN,
            "confidence": 0.0,
            "reasons": ["No activity history on record"],
        }

    # 1. Hard closure signals win outright.
    for event in events:
        key = _event_type_value(event).upper().replace(" ", "_")
        if key in HARD_CLOSURE_EVENTS:
            return {
                "status": "CLOSED",
                "status_enum": EntityStatusEnum.CLOSED,
                "confidence": 0.97,
                "reasons": [f"Hard closure signal: {key}"],
            }

    # 2. Recency-weighted average of every event.
    scores: List[float] = []
    reasons: List[str] = []
    recent_count = 0

    for event in events:
        es = score_event(_event_type_value(event), event.event_date)
        scores.append(es.value)
        reasons.append(es.reason)
        if es.is_recent:
            recent_count += 1

    avg_score = sum(scores) / len(scores)

    if recent_count >= RECENT_DENSITY_MIN_EVENTS:
        avg_score += RECENT_DENSITY_BONUS
        reasons.append(
            f"Recent-activity density bonus (+{RECENT_DENSITY_BONUS}, "
            f"{recent_count} recent events)"
        )

    avg_score = max(min(avg_score, 1.0), 0.0)

    if avg_score >= ACTIVE_THRESHOLD:
        return {
            "status": "ACTIVE",
            "status_enum": EntityStatusEnum.ACTIVE,
            "confidence": round(avg_score, 4),
            "reasons": reasons[:10],
        }

    if avg_score >= DORMANT_THRESHOLD:
        return {
            "status": "DORMANT",
            "status_enum": EntityStatusEnum.DORMANT,
            "confidence": round(avg_score, 4),
            "reasons": reasons[:10],
        }

    return {
        "status": "CLOSED",
        "status_enum": EntityStatusEnum.CLOSED,
        "confidence": round(1 - avg_score, 4),
        "reasons": reasons[:10],
    }
