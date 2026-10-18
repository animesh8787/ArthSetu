# ============================================================
# FILE: backend/app/api/v1/routes/ingest.py
# ============================================================

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status as http_status
from fastapi.responses import PlainTextResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.api.deps import AdminUser, CurrentUser, require_admin
from backend.app.db.enums import JobStatusEnum, JobTypeEnum, UserRole
from backend.app.db.session import get_db
from backend.app.db.models.source_record import SourceRecord
from backend.app.db.models.source_system import SourceSystem
from backend.app.schemas import (
    ConnectorUpdate,
    EventsIngestRequest,
    EventsReportOut,
    IngestionReportOut,
    IngestRequest,
    JobOut,
    PendingCountResponse,
    SourceSystemOut,
)
from backend.app.services import connectors, events_ingestion, ingestion, job_runner

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
def list_source_systems(db: DbSession, user: CurrentUser):
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
            # a connector URL may carry an access key, so only admins see it
            pull_url=s.pull_url if user.role == UserRole.ADMIN else None,
            pull_kind=s.pull_kind,
            last_pull_at=s.last_pull_at,
            last_pull_status=s.last_pull_status,
        )
        for s in db.query(SourceSystem).order_by(SourceSystem.code).all()
    ]


def _system_or_404(db: Session, code: str) -> SourceSystem:
    system = db.query(SourceSystem).filter(SourceSystem.code == code.upper()).first()
    if system is None:
        raise HTTPException(status_code=404, detail=f"Unknown source system '{code}'")
    return system


@router.put(
    "/source-systems/{code}/connector",
    response_model=SourceSystemOut,
    dependencies=[Depends(require_admin)],
)
def set_connector(code: str, body: ConnectorUpdate, db: DbSession):
    """Point a source system at the CSV/JSON export it publishes (read-only pull)."""
    system = _system_or_404(db, code)
    if body.pull_url:
        try:
            system.pull_url = connectors.validate_pull_url(body.pull_url)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        system.pull_kind = body.pull_kind
    else:
        system.pull_url = system.pull_kind = None
        system.last_pull_at = system.last_pull_status = None
    db.commit()
    count = db.query(func.count(SourceRecord.id)).filter(SourceRecord.source_system_id == system.id).scalar()
    return SourceSystemOut(
        code=system.code, name=system.name, department=system.department,
        record_count=int(count or 0), pull_url=system.pull_url, pull_kind=system.pull_kind,
        last_pull_at=system.last_pull_at, last_pull_status=system.last_pull_status,
    )


@router.post(
    "/source-systems/{code}/sync",
    response_model=JobOut,
    status_code=http_status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_admin)],
)
def sync_connector(code: str, db: DbSession, admin: AdminUser):
    """Pull this system's export now (runs off-thread; poll the job)."""
    system = _system_or_404(db, code)
    if not system.pull_url:
        raise HTTPException(status_code=409, detail="No connector configured for this system")
    job = job_runner.submit_job(
        db, JobTypeEnum.SYNC_CONNECTORS, payload={"code": system.code}, created_by=admin.email
    )
    return job_runner.to_dict(job)


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
            "email": r.email or "",
            "phone": r.phone or "",
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


# ------------------------------------------------------------
# Activity events (filings, renewals, inspections, power usage ...)
# ------------------------------------------------------------

@router.get(
    "/events/template",
    response_class=PlainTextResponse,
    responses={200: {"content": {"text/csv": {}}}},
)
def events_csv_template():
    return PlainTextResponse(
        events_ingestion.EVENTS_CSV_TEMPLATE,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="arthsetu_events_template.csv"'},
    )


@router.post(
    "/events",
    response_model=EventsReportOut,
    dependencies=[Depends(require_admin)],
)
def ingest_events(body: EventsIngestRequest, db: DbSession):
    rows = [e.model_dump() for e in body.events]
    try:
        return events_ingestion.ingest_events(db, rows, body.source_system_code).as_dict()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/events/csv",
    response_model=EventsReportOut,
    dependencies=[Depends(require_admin)],
)
async def ingest_events_csv(
    db: DbSession,
    file: Annotated[UploadFile, File()],
    source_system_code: Annotated[str | None, Form()] = None,
):
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 8 MB limit")
    rows = events_ingestion.parse_events_csv(raw)
    if not rows:
        raise HTTPException(status_code=400, detail="No data rows found in CSV")
    try:
        return events_ingestion.ingest_events(db, rows, source_system_code or None).as_dict()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
