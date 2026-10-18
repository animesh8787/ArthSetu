# ============================================================
# FILE: backend/app/api/v1/routes/jobs.py
# Read-only visibility into background jobs (see job_runner.py).
# ============================================================

from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.db.enums import JobStatusEnum, JobTypeEnum
from backend.app.db.session import get_db
from backend.app.db.models.job import Job
from backend.app.schemas import JobListResponse, JobOut
from backend.app.services.job_runner import to_dict as _out

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=JobListResponse)
def list_jobs(
    db: DbSession,
    job_type: Optional[JobTypeEnum] = None,
    status: Optional[JobStatusEnum] = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    q = db.query(Job)
    if job_type:
        q = q.filter(Job.job_type == job_type)
    if status:
        q = q.filter(Job.status == status)

    total = q.count()
    rows = q.order_by(Job.created_at.desc()).offset(offset).limit(limit).all()

    return JobListResponse(
        total=total, limit=limit, offset=offset, items=[_out(j) for j in rows]
    )


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: DbSession):
    try:
        job = db.get(Job, UUID(job_id))
    except (ValueError, TypeError):
        job = None
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _out(job)
