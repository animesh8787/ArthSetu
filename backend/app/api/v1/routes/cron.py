# ============================================================
# FILE: backend/app/api/v1/routes/cron.py
# One endpoint for an external scheduler (see .github/workflows/scheduled-sync.yml)
# to call: pull every connector, match new records, refresh statuses.
# Authenticated by a shared secret rather than a user token, since nobody is
# signed in when a schedule fires. Disabled while CRON_SECRET is empty.
# ============================================================

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status as http_status
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.enums import JobTypeEnum
from backend.app.db.session import get_db
from backend.app.schemas import JobOut
from backend.app.services import job_runner

router = APIRouter()


@router.post("/tick", response_model=JobOut, status_code=http_status.HTTP_202_ACCEPTED)
def tick(
    db: Annotated[Session, Depends(get_db)],
    x_cron_secret: Annotated[str | None, Header()] = None,
):
    if not settings.CRON_SECRET:
        raise HTTPException(status_code=404, detail="Scheduled sync is not enabled")
    if not hmac.compare_digest(x_cron_secret or "", settings.CRON_SECRET):
        raise HTTPException(status_code=401, detail="Bad cron secret")
    job = job_runner.submit_job(
        db,
        JobTypeEnum.SYNC_CONNECTORS,
        payload={"full_cycle": True},
        created_by="scheduler",
    )
    return job_runner.to_dict(job)
