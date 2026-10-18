# ============================================================
# FILE: backend/app/api/v1/routes/ingest.py
# ============================================================

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status as http_status
from fastapi.responses import PlainTextResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.api.deps import AdminUser, require_admin
from backend.app.db.enums import JobStatusEnum, JobTypeEnum
from backend.app.db.session import get_db
from backend.app.db.models.source_record import SourceRecord
from backend.app.db.models.source_system import SourceSystem
from backend.app.schemas import (
    IngestionReportOut,
    IngestRequest,
    JobOut,
    PendingCountResponse,
    SourceSystemOut,
)
from backend.app.services import ingestion, job_runner

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]

MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8 MB


def _create_then_queue_matching(
    db: DbSession,
    admin: AdminUser,
    source_system_code: str,
    rows: list[dict],
    process: bool,
) -> ingestion.IngestionReport:
    """Create records synchronously (fast), then hand matching off to a job.

    Row creation stays on the request thread — it's cheap. Matching runs the
    scoring engine per record, which is the slow part on a large batch, so
    it's queued as a background job instead of blocking the upload response.
    """
    report = ingestion.ingest_rows(db, source_system_code, rows, process=False)

    if process and report.new_record_ids:
        job = job_runner.submit_job(
            db,
            JobTypeEnum.CSV_MATCH,
            payload={"source_record_ids": report.new_record_ids},
            created_by=admin.email,
        )
        report.job_id = str(job.id)
        # In JOBS_SYNC mode the job has already finished by the time
        # submit_job returns — surface its result inline like before.
        if job.status == JobStatusEnum.SUCCEEDED and job.result:
            report.matching = ingestion.MatchingTally(**job.result)

    return report


@router.get("/source-systems", response_model=list[SourceSystemOut])
def list_source_systems(db: DbSession):
    counts = dict(
        db.query(SourceRecord.source_system_id, func.count(SourceRecord.id))
        .group_by(SourceRecord.source_system_id)
        .all()
    )
    return [
        SourceSystemOut(
            code=s.code,
            name=s.name,
            department=s.department,
            record_count=int(counts.get(s.id, 0)),
        )
        for s in db.query(SourceSystem).order_by(SourceSystem.code).all()
    ]


@router.get("/pending", response_model=PendingCountResponse)
def pending(db: DbSession):
    return PendingCountResponse(pending=ingestion.pending_count(db))


@router.get(
    "/template",
    response_class=PlainTextResponse,
    responses={200: {"content": {"text/csv": {}}}},
)
def csv_template():
    return PlainTextResponse(
        ingestion.CSV_TEMPLATE,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="arthsetu_import_template.csv"'},
    )


@router.post(
    "/csv",
    response_model=IngestionReportOut,
    dependencies=[Depends(require_admin)],
)
async def ingest_csv(
    db: DbSession,
    admin: AdminUser,
    source_system_code: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    process: Annotated[bool, Form()] = True,
):
    raw = await file.read(MAX_UPLOAD_BYTES + 1)  # never buffer more than the limit
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 8 MB limit")
    if not raw.strip():
        raise HTTPException(status_code=400, detail="Empty file")

    rows = ingestion.parse_csv(raw)
    if not rows:
        raise HTTPException(status_code=400, detail="No data rows found in CSV")

    try:
        report = _create_then_queue_matching(db, admin, source_system_code, rows, process)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return report.as_dict()


@router.post(
    "/records",
    response_model=IngestionReportOut,
    dependencies=[Depends(require_admin)],
)
def ingest_records(body: IngestRequest, db: DbSession, admin: AdminUser):
    rows = [
        {
            "external_id": r.external_id or "",
            "name": r.name,
            "pan": r.pan or "",
            "gstin": r.gstin or "",
            "address": r.address or "",
            "pin": r.pin or "",
            "_extra": {},
        }
        for r in body.records
    ]
    try:
        report = _create_then_queue_matching(
            db, admin, body.source_system_code, rows, body.process
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return report.as_dict()


@router.post(
    "/process-pending",
    response_model=JobOut,
    status_code=http_status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_admin)],
)
def process_pending(
    db: DbSession,
    admin: AdminUser,
    limit: int = Query(default=1000, ge=1, le=5000),
):
    """Queue matching over every unresolved source record (runs off-thread)."""
    job = job_runner.submit_job(
        db, JobTypeEnum.PROCESS_PENDING, payload={"limit": limit}, created_by=admin.email
    )
    return job_runner.to_dict(job)
