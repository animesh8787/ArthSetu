# ============================================================
# FILE: backend/app/api/v1/routes/audit.py
# ============================================================

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.db.models.activity_event import ActivityEvent
from backend.app.db.models.audit_log import AuditLog
from backend.app.db.models.business_entity import BusinessEntity
from backend.app.db.models.entity_record_link import EntityRecordLink
from backend.app.db.models.review_case import ReviewCase
from backend.app.schemas import AuditEntry, AuditListResponse

router = APIRouter()


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _business_scope(db: Session, business_id: UUID):
    """Audit rows are keyed by whatever object changed; collect the ones that belong to this business."""
    if db.get(BusinessEntity, business_id) is None:
        raise HTTPException(status_code=404, detail="Business not found")
    links = db.query(EntityRecordLink.id, EntityRecordLink.source_record_id).filter(
        EntityRecordLink.business_entity_id == business_id
    ).all()
    record_ids = {sr for _, sr in links}
    reviews = db.query(ReviewCase.id).filter(
        or_(
            ReviewCase.candidate_entity_id == business_id,
            ReviewCase.source_record_id.in_(record_ids) if record_ids else False,
        )
    ).all()
    events = db.query(ActivityEvent.id).filter(ActivityEvent.business_entity_id == business_id).limit(500).all()

    def ids(rows):
        return [str(r[0]) for r in rows]

    return or_(
        (AuditLog.entity_type == "business_entity") & (AuditLog.entity_id == str(business_id)),
        (AuditLog.entity_type == "entity_record_link") & AuditLog.entity_id.in_(ids(links)),
        # review audits use the case id; the matcher's REVIEW_CREATED uses the record id
        (AuditLog.entity_type == "review_case") & AuditLog.entity_id.in_(ids(reviews) + [str(r) for r in record_ids]),
        (AuditLog.entity_type == "activity_event") & AuditLog.entity_id.in_(ids(events)),
    )


@router.get("", response_model=AuditListResponse)
@router.get("/", response_model=AuditListResponse, include_in_schema=False)
def list_audit(
    db: Session = Depends(get_db),
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    business_id: UUID | None = Query(
        default=None,
        description="Everything that happened to one business: its own changes, its links, "
        "the review cases about it, and its events",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    query = db.query(AuditLog)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.filter(AuditLog.entity_id == entity_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if business_id:
        query = query.filter(_business_scope(db, business_id))

    total = query.with_entities(func.count(AuditLog.id)).scalar() or 0

    rows = (
        query.order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    return AuditListResponse(
        total=int(total),
        limit=limit,
        offset=offset,
        items=[
            AuditEntry(
                id=str(r.id),
                actor_type=_enum_value(r.actor_type),
                actor_id=r.actor_id,
                entity_type=r.entity_type,
                entity_id=r.entity_id,
                action=r.action,
                before_state=r.before_state,
                after_state=r.after_state,
                created_at=r.created_at,
            )
            for r in rows
        ],
    )
