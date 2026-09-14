# ============================================================
# FILE: backend/app/api/v1/routes/status.py
# ============================================================

from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy.orm import Session

from backend.app.api.deps import AdminUser, require_admin
from backend.app.db.enums import JobTypeEnum
from backend.app.db.session import get_db
from backend.app.db.models.business_entity import BusinessEntity
from backend.app.schemas import JobOut, StatusResultResponse
from backend.app.services import job_runner
from backend.app.services.status_engine import infer_business_status

router = APIRouter()


@router.get("/{ubid}", response_model=StatusResultResponse)
def get_status(ubid: str, db: Session = Depends(get_db)):
    entity = (
        db.query(BusinessEntity)
        .filter(BusinessEntity.ubid_code == ubid)
        .first()
    )
    if not entity:
        raise HTTPException(status_code=404, detail="Business not found")

    return infer_business_status(db=db, business_entity_id=entity.id)


@router.post(
    "/run-all",
    response_model=JobOut,
    status_code=http_status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_admin)],
)
def run_all_status(admin: AdminUser, db: Session = Depends(get_db)):
    """Queue a batch status recompute for every business (admin / nightly / demo).

    Recomputing status touches every business row, which can take a while on
    a large dataset — this runs off the request thread. Poll the returned
    job via GET /jobs/{id}.
    """
    job = job_runner.submit_job(
        db, JobTypeEnum.STATUS_RUN_ALL, payload={}, created_by=admin.email
    )
    return job_runner.to_dict(job)
