# ============================================================
# FILE: backend/app/api/v1/routes/review.py
# ============================================================

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.api.deps import ReviewerUser
from backend.app.db.session import get_db
from backend.app.db.models.review_case import ReviewCase
from backend.app.db.models.business_entity import BusinessEntity
from backend.app.db.models.source_record import SourceRecord
from backend.app.db.models.source_system import SourceSystem
from backend.app.schemas import (
    ReviewCaseItem,
    ReviewDecisionResponse,
    ReviewListResponse,
)
from backend.app.services.review_service import (
    approve_review_case,
    reject_review_case,
)

router = APIRouter()


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


@router.get("", response_model=ReviewListResponse)
@router.get("/", response_model=ReviewListResponse, include_in_schema=False)
def list_review_cases(
    db: Session = Depends(get_db),
    status: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    query = db.query(ReviewCase)
    if status:
        query = query.filter(ReviewCase.status == status.lower())

    total = query.with_entities(func.count(ReviewCase.id)).scalar() or 0

    rows = (
        query.order_by(ReviewCase.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    candidate_ids = {r.candidate_entity_id for r in rows if r.candidate_entity_id}
    candidates: dict = {}
    if candidate_ids:
        candidates = {
            b.id: b
            for b in db.query(BusinessEntity)
            .filter(BusinessEntity.id.in_(candidate_ids))
            .all()
        }

    record_ids = {r.source_record_id for r in rows if r.source_record_id}
    records: dict = {}
    if record_ids:
        for sr, ss in (
            db.query(SourceRecord, SourceSystem)
            .join(
                SourceSystem,
                SourceRecord.source_system_id == SourceSystem.id,
                isouter=True,
            )
            .filter(SourceRecord.id.in_(record_ids))
            .all()
        ):
            records[sr.id] = (sr, ss)

    def item(r: ReviewCase) -> ReviewCaseItem:
        cand = candidates.get(r.candidate_entity_id)
        sr_pair = records.get(r.source_record_id)
        return ReviewCaseItem(
            review_id=str(r.id),
            source_record_id=str(r.source_record_id),
            candidate_entity_id=str(r.candidate_entity_id)
            if r.candidate_entity_id
            else None,
            candidate_name=cand.legal_name if cand else None,
            candidate_ubid=cand.ubid_code if cand else None,
            source_system=sr_pair[1].name if sr_pair and sr_pair[1] else None,
            extracted_name=sr_pair[0].extracted_name if sr_pair else None,
            status=_enum_value(r.status),
            confidence=r.confidence,
            evidence=r.evidence,
            notes=r.notes,
            reviewer_id=r.reviewer_id,
            created_at=r.created_at,
            decided_at=r.decided_at,
        )

    return ReviewListResponse(
        total=int(total),
        limit=limit,
        offset=offset,
        items=[item(r) for r in rows],
    )


@router.post("/{review_id}/approve", response_model=ReviewDecisionResponse)
def approve_review(
    review_id: str,
    reviewer: ReviewerUser,
    db: Session = Depends(get_db),
):
    try:
        return approve_review_case(
            db=db, review_id=review_id, reviewer_id=reviewer.email
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{review_id}/reject", response_model=ReviewDecisionResponse)
def reject_review(
    review_id: str,
    reviewer: ReviewerUser,
    db: Session = Depends(get_db),
):
    try:
        return reject_review_case(
            db=db, review_id=review_id, reviewer_id=reviewer.email
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
