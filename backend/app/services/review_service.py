# ============================================================
# FILE: backend/app/services/review_service.py
# ============================================================

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.db.models.review_case import ReviewCase
from backend.app.db.models.entity_record_link import EntityRecordLink
from backend.app.db.models.audit_log import AuditLog
from backend.app.db.models.source_record import SourceRecord
from backend.app.services.matching_engine import _create_new_entity

from backend.app.db.enums import (
    LinkDecisionEnum,
    ReviewCaseStatusEnum,
    AuditActorEnum,
)


class ReviewConflict(Exception):
    """The case was already decided, or the record was linked in the meantime."""


_DECIDABLE = (ReviewCaseStatusEnum.OPEN, ReviewCaseStatusEnum.IN_PROGRESS)


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _uuid(value: str) -> UUID:
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        raise ValueError("Invalid review id")


def _write_audit(
    db: Session,
    review_id,
    action: str,
    reviewer_id: str,
    before_state: dict,
    after_state: dict,
) -> None:
    db.add(
        AuditLog(
            actor_type=AuditActorEnum.REVIEWER,
            actor_id=reviewer_id,
            entity_type="review_case",
            entity_id=str(review_id),
            action=action,
            before_state=before_state,
            after_state=after_state,
        )
    )


def _load_case(db: Session, review_id: str) -> ReviewCase:
    row = db.get(ReviewCase, _uuid(review_id))
    if not row:
        raise ValueError("Review case not found")
    if row.status not in _DECIDABLE:
        raise ReviewConflict(f"Review case is already {_enum_value(row.status)}")
    return row


def _close_siblings(db: Session, row: ReviewCase) -> int:
    """Other open cases for the same record are moot once this one is decided."""
    siblings = (
        db.query(ReviewCase)
        .filter(
            ReviewCase.source_record_id == row.source_record_id,
            ReviewCase.id != row.id,
            ReviewCase.status.in_(_DECIDABLE),
        )
        .all()
    )
    for sibling in siblings:
        sibling.status = ReviewCaseStatusEnum.CLOSED
        sibling.decided_at = datetime.now(timezone.utc)
    return len(siblings)


# ------------------------------------------------------------
# Public API
# ------------------------------------------------------------

def approve_review_case(
    db: Session,
    review_id: str,
    reviewer_id: str = "reviewer_demo",
) -> Dict[str, Any]:
    """Approve a review case: confirm the proposed link (merge) and close it."""

    row = _load_case(db, review_id)
    before_status = _enum_value(row.status)

    link_id = None
    link_created = False
    elsewhere = (
        db.query(EntityRecordLink.id)
        .filter(
            EntityRecordLink.source_record_id == row.source_record_id,
            EntityRecordLink.business_entity_id != row.candidate_entity_id,
        )
        .first()
    )
    if elsewhere is not None:
        raise ReviewConflict("This record is already linked to a different business")
    if row.candidate_entity_id is not None:
        existing = (
            db.query(EntityRecordLink)
            .filter(
                EntityRecordLink.source_record_id == row.source_record_id,
                EntityRecordLink.business_entity_id == row.candidate_entity_id,
            )
            .first()
        )
        if existing:
            existing.decision = LinkDecisionEnum.MANUAL
            existing.confidence = row.confidence or existing.confidence
            link_id = existing.id
        else:
            link_created = True
            link = EntityRecordLink(
                source_record_id=row.source_record_id,
                business_entity_id=row.candidate_entity_id,
                confidence=row.confidence or 0.0,
                decision=LinkDecisionEnum.MANUAL,
                explanation={
                    "source": "review_approval",
                    "reviewer_id": reviewer_id,
                    "evidence": row.evidence,
                },
            )
            db.add(link)
            db.flush()
            link_id = link.id

    row.status = ReviewCaseStatusEnum.APPROVED
    row.reviewer_id = reviewer_id
    row.decided_at = datetime.now(timezone.utc)
    _close_siblings(db, row)

    _write_audit(
        db,
        review_id=row.id,
        action="REVIEW_APPROVED",
        reviewer_id=reviewer_id,
        before_state={"status": before_status},
        after_state={
            "status": _enum_value(row.status),
            "linked_entity_id": str(row.candidate_entity_id)
            if row.candidate_entity_id
            else None,
            "link_id": str(link_id) if link_id else None,
            "link_created": link_created,
        },
    )

    db.commit()
    db.refresh(row)

    return {
        "message": "Review approved and link confirmed",
        "review_id": str(row.id),
        "status": _enum_value(row.status),
        "linked_entity_id": str(row.candidate_entity_id)
        if row.candidate_entity_id
        else None,
        "link_id": str(link_id) if link_id else None,
    }


def reject_review_case(
    db: Session,
    review_id: str,
    reviewer_id: str = "reviewer_demo",
) -> Dict[str, Any]:
    """Reject a review case: the record is a different business and gets its own UBID."""

    row = _load_case(db, review_id)
    before_status = _enum_value(row.status)

    new_entity_id = None
    link_id = None
    sr = db.get(SourceRecord, row.source_record_id)
    already_linked = (
        db.query(EntityRecordLink.id)
        .filter(EntityRecordLink.source_record_id == row.source_record_id)
        .first()
    )
    if sr is not None and already_linked is None:
        created = _create_new_entity(db, sr)
        new_entity_id = created.business_entity_id
        link_id = (
            db.query(EntityRecordLink.id)
            .filter(EntityRecordLink.source_record_id == sr.id)
            .scalar()
        )

    row.status = ReviewCaseStatusEnum.REJECTED
    row.reviewer_id = reviewer_id
    row.decided_at = datetime.now(timezone.utc)
    _close_siblings(db, row)

    _write_audit(
        db,
        review_id=row.id,
        action="REVIEW_REJECTED",
        reviewer_id=reviewer_id,
        before_state={"status": before_status},
        after_state={
            "status": _enum_value(row.status),
            "new_entity_id": str(new_entity_id) if new_entity_id else None,
            "link_id": str(link_id) if link_id else None,
        },
    )

    db.commit()
    db.refresh(row)

    return {
        "message": "Review rejected - the record was given its own business identity",
        "review_id": str(row.id),
        "status": _enum_value(row.status),
    }
