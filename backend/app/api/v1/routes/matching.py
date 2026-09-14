# ============================================================
# FILE: backend/app/api/v1/routes/matching.py
# ============================================================

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.api.deps import AdminUser
from backend.app.db.session import get_db
from backend.app.schemas import (
    MatchingCalibrationResponse,
    MatchingResultResponse,
    MatchingWeightsOut,
    MatchingWeightsUpdate,
)
from backend.app.services import matching_config_service as config_svc
from backend.app.services.matching_engine import process_source_record

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]


@router.post("/process/{source_record_id}", response_model=MatchingResultResponse)
def run_matching(source_record_id: str, db: DbSession):
    try:
        return process_source_record(db=db, source_record_id=source_record_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/weights", response_model=MatchingWeightsOut)
def get_weights(db: DbSession):
    return config_svc.get_config_out(db)


@router.put("/weights", response_model=MatchingWeightsOut)
def update_weights(body: MatchingWeightsUpdate, admin: AdminUser, db: DbSession):
    updates = body.model_dump(exclude_unset=True)
    return config_svc.update_weights(db, updates, admin.email)


@router.get("/calibration", response_model=MatchingCalibrationResponse)
def calibration(db: DbSession):
    return config_svc.calibration_report(db)
