# ============================================================
# FILE: backend/app/services/job_runner.py
# Minimal in-process background job runner.
#
# Endpoints that would otherwise block the request thread (batch status
# recompute, bulk matching) submit a Job row and hand execution to a small
# thread pool. There's no external queue/broker — this is a single-process
# app, and a DB-tracked Job row already gives callers a pollable status and
# an audit trail without extra infrastructure.
# ============================================================

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.enums import JobStatusEnum, JobTypeEnum
from backend.app.db.models.job import Job
from backend.app.db.session import SessionLocal

JobHandler = Callable[[Session, dict], dict]

_HANDLERS: Dict[str, JobHandler] = {}
_executor: Optional[ThreadPoolExecutor] = None


def register(job_type: JobTypeEnum):
    """Decorator: register a handler `(db, payload) -> result_dict` for a job type."""

    def _wrap(fn: JobHandler) -> JobHandler:
        _HANDLERS[job_type.value] = fn
        return fn

    return _wrap


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(
            max_workers=settings.JOBS_MAX_WORKERS,
            thread_name_prefix="arthsetu-job",
        )
    return _executor


def submit_job(
    db: Session,
    job_type: JobTypeEnum,
    payload: Optional[dict] = None,
    created_by: Optional[str] = None,
) -> Job:
    """Create a Job row and schedule its execution.

    In `settings.JOBS_SYNC` mode (tests, or any environment that wants
    deterministic behaviour) the job runs inline before this returns.
    """

    job = Job(
        job_type=job_type,
        status=JobStatusEnum.PENDING,
        payload=payload or {},
        created_by=created_by,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    job_id = job.id
    if settings.JOBS_SYNC:
        _execute(job_id)
        db.refresh(job)
    else:
        _get_executor().submit(_execute, job_id)

    return job


def _execute(job_id: UUID) -> None:
    """Runs on the worker thread (or inline, in sync mode) with its own session."""

    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job is None:
            return

        job_type = job.job_type.value if hasattr(job.job_type, "value") else job.job_type
        handler = _HANDLERS.get(job_type)

        job.status = JobStatusEnum.RUNNING
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        if handler is None:
            raise ValueError(f"No handler registered for job type '{job_type}'")

        result = handler(db, job.payload or {})

        job.status = JobStatusEnum.SUCCEEDED
        job.result = result
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        job = db.get(Job, job_id)
        if job is not None:
            job.status = JobStatusEnum.FAILED
            job.error = str(exc)[:2000]
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()


# A job still pending/running this long after it was created lost its worker thread
# (restart, free-tier spin-down). Younger ones may belong to a sibling worker process.
STALE_AFTER = timedelta(minutes=10)


def recover_interrupted_jobs() -> int:
    """Fail jobs orphaned by a restart so they stop showing as running forever."""
    db = SessionLocal()
    try:
        stale = (
            db.query(Job)
            .filter(
                Job.status.in_([JobStatusEnum.PENDING, JobStatusEnum.RUNNING]),
                Job.created_at < datetime.now(timezone.utc) - STALE_AFTER,
            )
            .all()
        )
        for job in stale:
            job.status = JobStatusEnum.FAILED
            job.error = "Interrupted by a server restart - run it again"
            job.finished_at = datetime.now(timezone.utc)
        db.commit()
        return len(stale)
    finally:
        db.close()


def to_dict(job: Job) -> Dict[str, Any]:
    return {
        "id": str(job.id),
        "job_type": job.job_type.value if hasattr(job.job_type, "value") else job.job_type,
        "status": job.status.value if hasattr(job.status, "value") else job.status,
        "payload": job.payload,
        "result": job.result,
        "error": job.error,
        "created_by": job.created_by,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
    }
