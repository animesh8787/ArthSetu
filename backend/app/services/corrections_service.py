# ============================================================
# FILE: backend/app/services/corrections_service.py
# Reviewer edits to the identity graph: split, status override,
# event reassignment - each one reversible.
# ============================================================

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.db.enums import (
    AuditActorEnum,
    EntityStatusEnum,
    LinkDecisionEnum,
    ReviewCaseStatusEnum,
)
from backend.app.db.models.activity_event import ActivityEvent
from backend.app.db.models.audit_log import AuditLog
from backend.app.db.models.business_entity import BusinessEntity
from backend.app.db.models.entity_record_link import EntityRecordLink
from backend.app.db.models.review_case import ReviewCase
from backend.app.db.models.source_record import SourceRecord
from backend.app.db.models.status_snapshot import StatusSnapshot
from backend.app.services.scoring import normalize_address, normalize_pin, normalize_text
from backend.app.services.status_engine import infer_business_status
from backend.app.services.ubid_service import generate_ubid

REVERSIBLE_ACTIONS = {
    "REVIEW_APPROVED",
    "REVIEW_REJECTED",
    "LINK_SPLIT",
    "STATUS_OVERRIDDEN",
    "STATUS_OVERRIDE_CLEARED",
    "EVENT_REASSIGNED",
}


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _uuid(value: Any, label: str = "id") -> UUID:
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        raise ValueError(f"Invalid {label}")


def _audit(
    db: Session,
    *,
    reviewer: str,
    action: str,
    entity_type: str,
    entity_id: str,
    before: dict | None,
    after: dict | None,
) -> AuditLog:
    row = AuditLog(
        actor_type=AuditActorEnum.REVIEWER,
        actor_id=reviewer,
        entity_type=entity_type,
        entity_id=str(entity_id),
        action=action,
        before_state=before,
        after_state=after,
    )
    db.add(row)
    db.flush()
    return row


def is_undone(db: Session, audit_id: Any) -> bool:
    return (
        db.query(AuditLog.id)
        .filter(
            AuditLog.action == "CORRECTION_UNDONE",
            AuditLog.entity_id == str(audit_id),
        )
        .first()
        is not None
    )


def _entity_by_ubid(db: Session, ubid: str) -> BusinessEntity:
    entity = (
        db.query(BusinessEntity).filter(BusinessEntity.ubid_code == ubid).first()
    )
    if not entity:
        raise ValueError("Business not found")
    return entity


# ------------------------------------------------------------
# Split a link
# ------------------------------------------------------------

def split_link(
    db: Session, link_id: str, reviewer: str, reason: str, mode: str
) -> dict:
    link = db.get(EntityRecordLink, _uuid(link_id, "link id"))
    if not link:
        raise ValueError("Link not found")

    from_entity = db.get(BusinessEntity, link.business_entity_id)
    sr = db.get(SourceRecord, link.source_record_id)
    before = {
        "link_id": str(link.id),
        "source_record_id": str(link.source_record_id),
        "from_entity_id": str(link.business_entity_id),
        "from_ubid": from_entity.ubid_code if from_entity else None,
        "confidence": link.confidence,
        "decision": link.decision.value if link.decision else None,
    }

    detail: dict[str, Any] = {"mode": mode, "reason": reason}

    if mode == "new_entity":
        # Only carry over a strong id if no other entity already owns it —
        # a split says "this record is a *different* business".
        pan = sr.extracted_pan if sr else None
        gstin = sr.extracted_gstin if sr else None
        if pan and db.query(BusinessEntity.id).filter(BusinessEntity.pan == pan).first():
            pan = None
        if gstin and db.query(BusinessEntity.id).filter(BusinessEntity.gstin == gstin).first():
            gstin = None
        new_entity = BusinessEntity(
            ubid_code=generate_ubid(),
            legal_name=(sr.extracted_name if sr else None) or "UNKNOWN",
            normalized_name=normalize_text(sr.extracted_name if sr else None),
            pan=pan,
            gstin=gstin,
            address=sr.extracted_address if sr else None,
            normalized_address=normalize_address(sr.extracted_address if sr else None),
            pin_code=normalize_pin(sr.extracted_pin if sr else None) or None,
            status=EntityStatusEnum.UNKNOWN,
        )
        db.add(new_entity)
        db.flush()
        link.business_entity_id = new_entity.id
        link.decision = LinkDecisionEnum.MANUAL
        link.explanation = {"source": "reviewer_split", "reason": reason}
        detail["to_entity_id"] = str(new_entity.id)
        detail["to_ubid"] = new_entity.ubid_code
        detail["created_entity"] = True
    elif mode == "reopen_review":
        case = ReviewCase(
            source_record_id=link.source_record_id,
            candidate_entity_id=link.business_entity_id,
            status=ReviewCaseStatusEnum.OPEN,
            confidence=link.confidence,
            evidence={
                "candidate_entity_id": str(link.business_entity_id),
                "candidate_name": from_entity.legal_name if from_entity else None,
                "reasons": [f"Reopened by {reviewer}: {reason}"],
            },
            notes=f"Split from {from_entity.ubid_code if from_entity else '?'}: {reason}",
        )
        db.add(case)
        db.flush()
        db.delete(link)
        detail["review_case_id"] = str(case.id)
        detail["created_entity"] = False
    else:
        raise ValueError("mode must be 'new_entity' or 'reopen_review'")

    audit = _audit(
        db, reviewer=reviewer, action="LINK_SPLIT",
        entity_type="entity_record_link", entity_id=before["link_id"],
        before=before, after=detail,
    )
    db.commit()
    return {
        "message": "Link split",
        "audit_id": str(audit.id),
        "detail": detail,
    }


# ------------------------------------------------------------
# Status override
# ------------------------------------------------------------

def override_status(
    db: Session, ubid: str, reviewer: str, status: str, reason: str
) -> dict:
    entity = _entity_by_ubid(db, ubid)
    before = {
        "status": entity.status.value if hasattr(entity.status, "value") else str(entity.status),
        "status_locked": bool(entity.status_locked),
        "reason": entity.status_override_reason,
        "overridden_by": entity.status_overridden_by,
    }
    entity.status = EntityStatusEnum(status)
    entity.status_locked = True
    entity.status_override_reason = reason
    entity.status_overridden_by = reviewer

    audit = _audit(
        db, reviewer=reviewer, action="STATUS_OVERRIDDEN",
        entity_type="business_entity", entity_id=str(entity.id),
        before=before,
        after={"status": status, "status_locked": True, "reason": reason, "ubid": ubid},
    )
    db.commit()
    return {"message": f"Status pinned to {status}", "audit_id": str(audit.id),
            "detail": {"status": status, "ubid": ubid}}


def clear_status_override(db: Session, ubid: str, reviewer: str) -> dict:
    entity = _entity_by_ubid(db, ubid)
    if not entity.status_locked:
        raise ValueError("Status is not overridden")
    before = {
        "status": entity.status.value if hasattr(entity.status, "value") else str(entity.status),
        "status_locked": True,
        "reason": entity.status_override_reason,
        "overridden_by": entity.status_overridden_by,
    }
    entity.status_locked = False
    entity.status_override_reason = None
    entity.status_overridden_by = None
    db.flush()

    audit = _audit(
        db, reviewer=reviewer, action="STATUS_OVERRIDE_CLEARED",
        entity_type="business_entity", entity_id=str(entity.id),
        before=before, after={"status_locked": False, "ubid": ubid},
    )
    db.commit()
    infer_business_status(db, entity.id)  # recompute now that the lock is off
    return {"message": "Override cleared; status recomputed",
            "audit_id": str(audit.id), "detail": {"ubid": ubid}}


# ------------------------------------------------------------
# Reassign an activity event
# ------------------------------------------------------------

def reassign_event(
    db: Session, event_id: str, reviewer: str, target_ubid: str, reason: str
) -> dict:
    event = db.get(ActivityEvent, _uuid(event_id, "event id"))
    if not event:
        raise ValueError("Activity event not found")
    target = _entity_by_ubid(db, target_ubid)
    source_entity_id = event.business_entity_id
    if str(source_entity_id) == str(target.id):
        raise ValueError("Event is already assigned to that business")

    from_entity = db.get(BusinessEntity, source_entity_id)
    before = {
        "event_id": str(event.id),
        "from_entity_id": str(source_entity_id),
        "from_ubid": from_entity.ubid_code if from_entity else None,
    }
    event.business_entity_id = target.id

    audit = _audit(
        db, reviewer=reviewer, action="EVENT_REASSIGNED",
        entity_type="activity_event", entity_id=str(event.id),
        before=before,
        after={"to_entity_id": str(target.id), "to_ubid": target_ubid, "reason": reason},
    )
    db.commit()

    for eid in (source_entity_id, target.id):
        try:
            infer_business_status(db, eid)
        except Exception:  # noqa: BLE001
            db.rollback()

    return {"message": "Event reassigned", "audit_id": str(audit.id),
            "detail": {"from_ubid": before["from_ubid"], "to_ubid": target_ubid}}


# ------------------------------------------------------------
# Undo
# ------------------------------------------------------------

def undo(db: Session, audit_id: str, reviewer: str) -> dict:
    original = db.get(AuditLog, _uuid(audit_id, "audit id"))
    if not original:
        raise ValueError("Audit entry not found")
    if original.action not in REVERSIBLE_ACTIONS:
        raise ValueError(f"'{original.action}' cannot be undone")
    if is_undone(db, original.id):
        raise ValueError("This action has already been undone")

    before = original.before_state or {}
    after = original.after_state or {}
    _ensure_latest(db, original, before, after)
    summary = _reverse(db, original.action, before, after, original.entity_id)

    _audit(
        db, reviewer=reviewer, action="CORRECTION_UNDONE",
        entity_type=original.entity_type or "correction",
        entity_id=str(original.id),
        before=after, after={"undid_action": original.action, "note": summary},
    )
    db.commit()
    return {"message": summary, "audit_id": str(original.id), "detail": None}


_REF_KEYS = ("link_id", "source_record_id", "review_case_id", "new_entity_id")


def _refs(row_entity_id: Any, *states: dict) -> set[str]:
    refs = {str(row_entity_id)} if row_entity_id else set()
    for state in states:
        refs.update(str(state[k]) for k in _REF_KEYS if state.get(k))
    return refs


def _ensure_latest(db: Session, original: AuditLog, before: dict, after: dict) -> None:
    """Refuse an undo while a later, still-active correction builds on the same records."""
    mine = _refs(original.entity_id, before, after)
    later = (
        db.query(AuditLog)
        .filter(
            AuditLog.action.in_(REVERSIBLE_ACTIONS),
            AuditLog.created_at > original.created_at,
            AuditLog.id != original.id,
        )
        .all()
    )
    for row in later:
        if is_undone(db, row.id):
            continue
        if mine & _refs(row.entity_id, row.before_state or {}, row.after_state or {}):
            raise ValueError(
                f"A later change ({row.action.replace('_', ' ').lower()}) depends on this one - "
                "undo that first"
            )


def _reverse(
    db: Session, action: str, before: dict, after: dict, subject_id: str | None
) -> str:
    if action == "REVIEW_APPROVED":
        link_id = after.get("link_id")
        if link_id:
            link = db.get(EntityRecordLink, _uuid(link_id))
            if link:
                if after.get("link_created"):
                    db.delete(link)
                else:  # a pre-existing auto link was promoted - just revert it
                    link.decision = LinkDecisionEnum.AUTO_LINK
        _reopen_case(db, subject_id)
        return "Approval undone - link reverted, case reopened"

    if action == "REVIEW_REJECTED":
        entity_id = after.get("new_entity_id")
        if entity_id:
            entity = db.get(BusinessEntity, _uuid(entity_id))
            if entity is not None:
                if _entity_in_use(db, entity.id, ignore_link=after.get("link_id")):
                    raise ValueError(
                        "This business has gained links or history since the rejection, "
                        "so it cannot be removed"
                    )
                link = db.get(EntityRecordLink, _uuid(after["link_id"])) if after.get("link_id") else None
                if link is not None:
                    db.delete(link)
                    db.flush()
                db.delete(entity)
        _reopen_case(db, subject_id)
        return "Rejection undone - the new business was removed and the case reopened"

    if action == "LINK_SPLIT":
        return _reverse_split(db, before, after)

    if action in ("STATUS_OVERRIDDEN", "STATUS_OVERRIDE_CLEARED"):
        return _reverse_status(db, before, after)

    if action == "EVENT_REASSIGNED":
        event = db.get(ActivityEvent, _uuid(before["event_id"]))
        if event:
            event.business_entity_id = _uuid(before["from_entity_id"])
            try:
                infer_business_status(db, event.business_entity_id)
            except Exception:  # noqa: BLE001
                db.rollback()
        return "Event reassignment undone"

    raise ValueError(f"No reverse handler for {action}")


def _entity_in_use(db: Session, entity_id: Any, ignore_link: str | None = None) -> bool:
    """True when anything besides one known founding link points at the entity."""
    links = db.query(EntityRecordLink.id).filter(
        EntityRecordLink.business_entity_id == entity_id
    )
    if ignore_link:
        links = links.filter(EntityRecordLink.id != _uuid(ignore_link))
    return any(
        q.first() is not None
        for q in (
            links,
            db.query(ActivityEvent.id).filter(ActivityEvent.business_entity_id == entity_id),
            db.query(StatusSnapshot.id).filter(StatusSnapshot.business_entity_id == entity_id),
            db.query(ReviewCase.id).filter(ReviewCase.candidate_entity_id == entity_id),
        )
    )


def _reopen_case(db: Session, review_case_id: str | None) -> None:
    if not review_case_id:
        return
    try:
        case = db.get(ReviewCase, _uuid(review_case_id))
    except ValueError:
        return
    if case is None:
        return
    case.status = ReviewCaseStatusEnum.OPEN
    case.reviewer_id = None
    case.decided_at = None


def _reverse_split(db: Session, before: dict, after: dict) -> str:
    from_entity_id = _uuid(before["from_entity_id"])
    if after.get("mode") == "new_entity":
        link = db.get(EntityRecordLink, _uuid(before["link_id"]))
        if link:
            created_id = link.business_entity_id
            link.business_entity_id = from_entity_id
            link.decision = LinkDecisionEnum(before["decision"]) if before.get("decision") else LinkDecisionEnum.MANUAL
            link.confidence = before.get("confidence") or link.confidence
            link.explanation = {"source": "split_undo"}
            db.flush()
            # drop the entity we created only if it is still a bare shell - never
            # delete history (events, snapshots, cases) to make an undo succeed
            if after.get("created_entity") and not _entity_in_use(db, created_id):
                stray = db.get(BusinessEntity, created_id)
                if stray:
                    db.delete(stray)
        return "Split undone - record relinked to the original business"

    # reopen_review mode: delete the reopened case, recreate the link
    case_id = after.get("review_case_id")
    if case_id:
        case = db.get(ReviewCase, _uuid(case_id))
        if case:
            db.delete(case)
    db.add(
        EntityRecordLink(
            source_record_id=_uuid(before["source_record_id"]),
            business_entity_id=from_entity_id,
            confidence=before.get("confidence") or 0.0,
            decision=LinkDecisionEnum.MANUAL,
            explanation={"source": "split_undo"},
        )
    )
    return "Split undone - record relinked to the original business"


def _reverse_status(db: Session, before: dict, after: dict) -> str:
    ubid = after.get("ubid")
    if not ubid:
        raise ValueError("Cannot resolve business for status undo")
    entity = _entity_by_ubid(db, ubid)
    # Restore the exact prior state; the engine will refresh it on its next run.
    if before.get("status"):
        entity.status = EntityStatusEnum(before["status"])
    entity.status_locked = bool(before.get("status_locked"))
    entity.status_override_reason = before.get("reason")
    entity.status_overridden_by = before.get("overridden_by")
    db.flush()
    return "Status change undone"


# ------------------------------------------------------------
# History
# ------------------------------------------------------------

_CORRECTION_ACTIONS = REVERSIBLE_ACTIONS | {"CORRECTION_UNDONE"}


def list_corrections(db: Session, limit: int, offset: int) -> dict:
    q = db.query(AuditLog).filter(AuditLog.action.in_(_CORRECTION_ACTIONS))
    total = q.count()
    rows = q.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset).all()

    undone_ids = {
        str(r.entity_id)
        for r in db.query(AuditLog.entity_id)
        .filter(AuditLog.action == "CORRECTION_UNDONE")
        .all()
    }

    items = []
    for r in rows:
        after = r.after_state or {}
        reversible = r.action in REVERSIBLE_ACTIONS
        items.append(
            {
                "audit_id": str(r.id),
                "action": r.action,
                "actor_id": r.actor_id,
                "entity_type": r.entity_type,
                "entity_id": r.entity_id,
                "summary": _summary(r.action, after),
                "reason": after.get("reason") or after.get("note"),
                "created_at": r.created_at,
                "undone": str(r.id) in undone_ids,
                "reversible": reversible and str(r.id) not in undone_ids,
            }
        )
    return {"total": total, "limit": limit, "offset": offset, "items": items}


def _summary(action: str, after: dict) -> str:
    return {
        "REVIEW_APPROVED": "Review approved - link confirmed",
        "REVIEW_REJECTED": "Review rejected",
        "LINK_SPLIT": f"Link split ({after.get('mode', '?')})",
        "STATUS_OVERRIDDEN": f"Status pinned to {after.get('status', '?')}",
        "STATUS_OVERRIDE_CLEARED": "Status override cleared",
        "EVENT_REASSIGNED": f"Event moved to {after.get('to_ubid', '?')}",
        "CORRECTION_UNDONE": f"Undid: {after.get('undid_action', '?')}",
    }.get(action, action)
