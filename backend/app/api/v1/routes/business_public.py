# ============================================================
# FILE: backend/app/api/v1/routes/business_public.py
# ============================================================

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.app.db.enums import EntityStatusEnum
from backend.app.db.session import get_db
from backend.app.db.models.business_entity import BusinessEntity
from backend.app.db.models.entity_record_link import EntityRecordLink
from backend.app.db.models.source_record import SourceRecord
from backend.app.db.models.source_system import SourceSystem
from backend.app.db.models.activity_event import ActivityEvent
from backend.app.db.models.status_snapshot import StatusSnapshot
from backend.app.schemas import (
    BusinessProfileResponse,
    BusinessSearchItem,
    BusinessSearchResponse,
    LinkedRecord,
    MatchingEvidence,
    StatusHistoryPoint,
    TimelineEvent,
)

router = APIRouter()


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


@router.get("/search", response_model=BusinessSearchResponse)
def search_businesses(
    db: Session = Depends(get_db),
    q: str | None = Query(default=None, description="UBID, name, PAN or GSTIN"),
    status: EntityStatusEnum | None = Query(default=None),
    district: str | None = Query(default=None),
    pin: str | None = Query(default=None, description="6-digit PIN code"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    query = db.query(BusinessEntity)

    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                BusinessEntity.ubid_code.ilike(like),
                BusinessEntity.legal_name.ilike(like),
                BusinessEntity.normalized_name.ilike(like),
                BusinessEntity.pan.ilike(like),
                BusinessEntity.gstin.ilike(like),
                BusinessEntity.address.ilike(like),
            )
        )
    if status:
        query = query.filter(BusinessEntity.status == status)
    if district == "Unknown":  # analytics labels null districts "Unknown"
        query = query.filter(BusinessEntity.district.is_(None))
    elif district:
        query = query.filter(BusinessEntity.district.ilike(f"%{district}%"))
    if pin:
        query = query.filter(BusinessEntity.pin_code == pin.strip())

    total = query.with_entities(func.count(BusinessEntity.id)).scalar() or 0

    rows = (
        query.order_by(BusinessEntity.legal_name.asc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    return BusinessSearchResponse(
        total=int(total),
        limit=limit,
        offset=offset,
        items=[
            BusinessSearchItem(
                ubid=r.ubid_code,
                business_name=r.legal_name,
                status=_enum_value(r.status),
                district=r.district,
                pin_code=r.pin_code,
                pan=r.pan,
                gstin=r.gstin,
            )
            for r in rows
        ],
    )


@router.get("/{ubid}", response_model=BusinessProfileResponse)
def get_business_profile(ubid: str, db: Session = Depends(get_db)):
    entity = (
        db.query(BusinessEntity)
        .filter(BusinessEntity.ubid_code == ubid)
        .first()
    )
    if not entity:
        raise HTTPException(status_code=404, detail="Business not found")

    link_rows = (
        db.query(EntityRecordLink, SourceRecord, SourceSystem)
        .join(SourceRecord, EntityRecordLink.source_record_id == SourceRecord.id)
        .join(
            SourceSystem,
            SourceRecord.source_system_id == SourceSystem.id,
            isouter=True,
        )
        .filter(EntityRecordLink.business_entity_id == entity.id)
        .all()
    )

    linked_records = [
        LinkedRecord(
            link_id=str(link.id),
            source_record_id=str(sr.id),
            source_system=ss.name if ss else None,
            department=ss.department if ss else None,
            external_id=sr.external_id,
            extracted_name=sr.extracted_name,
            extracted_address=sr.extracted_address,
            extracted_pin=sr.extracted_pin,
            confidence=link.confidence,
            decision=_enum_value(link.decision) if link.decision else None,
        )
        for link, sr, ss in link_rows
    ]

    # Matching evidence: best link's explanation + strong-ID checks.
    evidence: list[MatchingEvidence] = []
    if link_rows:
        best = max(link_rows, key=lambda t: t[0].confidence or 0)
        best_link = best[0]
        if best_link.confidence is not None:
            evidence.append(
                MatchingEvidence(
                    signal="Best link confidence",
                    value=f"{round(best_link.confidence * 100)}%",
                )
            )
        expl = best_link.explanation
        reasons = []
        if isinstance(expl, dict):
            reasons = expl.get("reasons") or []
        elif isinstance(expl, list):
            reasons = expl
        for reason in reasons[:6]:
            evidence.append(MatchingEvidence(signal="Signal", value=str(reason)))
    if entity.gstin:
        evidence.append(MatchingEvidence(signal="GSTIN on file", value=entity.gstin))
    if entity.pan:
        evidence.append(MatchingEvidence(signal="PAN on file", value=entity.pan))
    if entity.pin_code:
        evidence.append(MatchingEvidence(signal="PIN code", value=entity.pin_code))
    if entity.address:
        evidence.append(MatchingEvidence(signal="Address on file", value=entity.address))

    events = (
        db.query(ActivityEvent)
        .filter(ActivityEvent.business_entity_id == entity.id)
        .order_by(
            func.coalesce(ActivityEvent.occurred_at, ActivityEvent.created_at).desc()
        )
        .limit(25)
        .all()
    )
    timeline = [
        TimelineEvent(
            id=str(e.id),
            date=e.event_date,
            event=_enum_value(e.event_type),
            score=e.score,
        )
        for e in events
    ]

    snaps = (
        db.query(StatusSnapshot)
        .filter(StatusSnapshot.business_entity_id == entity.id)
        .order_by(StatusSnapshot.created_at.asc())
        .all()
    )
    status_history = [
        StatusHistoryPoint(
            date=s.created_at,
            status=_enum_value(s.status),
            confidence=s.confidence,
        )
        for s in snaps
    ]

    return BusinessProfileResponse(
        id=str(entity.id),
        ubid=entity.ubid_code,
        business_name=entity.legal_name,
        status=_enum_value(entity.status),
        status_locked=bool(entity.status_locked),
        status_override_reason=entity.status_override_reason,
        pan=entity.pan,
        gstin=entity.gstin,
        address=entity.address,
        pin_code=entity.pin_code,
        district=entity.district,
        sector=entity.sector,
        linked_records_count=len(linked_records),
        linked_records=linked_records,
        matching_evidence=evidence,
        timeline=timeline,
        status_history=status_history,
    )
