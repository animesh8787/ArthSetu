# ============================================================
# FILE: backend/app/api/v1/routes/corrections.py
# ============================================================

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import ReviewerUser
from backend.app.db.session import get_db
from backend.app.schemas import (
    CorrectionListResponse,
    CorrectionResult,
    ReassignEventRequest,
    SplitLinkRequest,
    StatusOverrideRequest,
)
from backend.app.services import corrections_service as svc

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]


def _guard(fn, *args):
    try:
        return fn(*args)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("", response_model=CorrectionListResponse)
@router.get("/", response_model=CorrectionListResponse, include_in_schema=False)
def history(
    _: ReviewerUser,
    db: DbSession,
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return svc.list_corrections(db, limit, offset)


@router.post("/links/{link_id}/split", response_model=CorrectionResult)
def split_link(
    link_id: str, body: SplitLinkRequest, reviewer: ReviewerUser, db: DbSession
):
    return _guard(
        svc.split_link, db, link_id, reviewer.email, body.reason, body.mode
    )


@router.post("/entities/{ubid}/status-override", response_model=CorrectionResult)
def override_status(
    ubid: str, body: StatusOverrideRequest, reviewer: ReviewerUser, db: DbSession
):
    return _guard(
        svc.override_status, db, ubid, reviewer.email, body.status, body.reason
    )


@router.post("/entities/{ubid}/status-override/clear", response_model=CorrectionResult)
def clear_status_override(ubid: str, reviewer: ReviewerUser, db: DbSession):
    return _guard(svc.clear_status_override, db, ubid, reviewer.email)


@router.post("/events/{event_id}/reassign", response_model=CorrectionResult)
def reassign_event(
    event_id: str,
    body: ReassignEventRequest,
    reviewer: ReviewerUser,
    db: DbSession,
):
    return _guard(
        svc.reassign_event, db, event_id, reviewer.email, body.target_ubid, body.reason
    )


@router.post("/undo/{audit_id}", response_model=CorrectionResult)
def undo(audit_id: str, reviewer: ReviewerUser, db: DbSession):
    return _guard(svc.undo, db, audit_id, reviewer.email)
