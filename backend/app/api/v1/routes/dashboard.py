# ============================================================
# FILE: backend/app/api/v1/routes/dashboard.py
# ============================================================

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.db.models.business_entity import BusinessEntity
from backend.app.db.models.review_case import ReviewCase
from backend.app.db.models.entity_record_link import EntityRecordLink
from backend.app.db.enums import (
    EntityStatusEnum,
    LinkDecisionEnum,
    ReviewCaseStatusEnum,
)
from backend.app.schemas import DashboardResponse

router = APIRouter()


@router.get("", response_model=DashboardResponse)
@router.get("/", response_model=DashboardResponse, include_in_schema=False)
def get_dashboard(db: Session = Depends(get_db)):
    """Single-call executive dashboard summary."""

    status_counts = dict(
        db.query(BusinessEntity.status, func.count(BusinessEntity.id))
        .group_by(BusinessEntity.status)
        .all()
    )

    def count_for(status: EntityStatusEnum) -> int:
        return int(status_counts.get(status, 0) or 0)

    total = sum(int(v or 0) for v in status_counts.values())

    pending_reviews = (
        db.query(func.count(ReviewCase.id))
        .filter(ReviewCase.status == ReviewCaseStatusEnum.OPEN)
        .scalar()
        or 0
    )

    total_links = db.query(func.count(EntityRecordLink.id)).scalar() or 0
    # Founding links (a record that opened a brand-new business) carry no score, so
    # they are not "matches" and stay out of the auto-match rate.
    scored = EntityRecordLink.confidence.isnot(None)
    scored_links = (
        db.query(func.count(EntityRecordLink.id)).filter(scored).scalar() or 0
    )
    auto_links = (
        db.query(func.count(EntityRecordLink.id))
        .filter(scored, EntityRecordLink.decision == LinkDecisionEnum.AUTO_LINK)
        .scalar()
        or 0
    )
    auto_match_rate = (
        round((auto_links / scored_links) * 100, 2) if scored_links else 0.0
    )

    return DashboardResponse(
        total_businesses=total,
        active=count_for(EntityStatusEnum.ACTIVE),
        dormant=count_for(EntityStatusEnum.DORMANT),
        closed=count_for(EntityStatusEnum.CLOSED),
        unknown=count_for(EntityStatusEnum.UNKNOWN),
        pending_reviews=int(pending_reviews),
        total_links=int(total_links),
        auto_match_rate=auto_match_rate,
    )
