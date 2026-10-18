from fastapi import APIRouter, Depends

from backend.app.api.deps import get_current_user, require_admin, require_reviewer
from backend.app.api.v1.routes import (
    analytics,
    audit,
    auth,
    business_public,
    corrections,
    cron,
    dashboard,
    health,
    ingest,
    jobs,
    matching,
    review,
    status,
)

# Registers job_runner handlers (status run-all, process-pending, csv match).
from backend.app.services import job_handlers  # noqa: F401

router = APIRouter()

# --- Public ---------------------------------------------------------------
router.include_router(health.router, tags=["Health"])
router.include_router(auth.router, prefix="/auth", tags=["Auth"])
# Shared-secret auth of its own (no user is signed in when a schedule fires).
router.include_router(cron.router, prefix="/cron", tags=["Scheduler"])

# --- Authenticated (any active user) ------------------------------------
_auth = [Depends(get_current_user)]
router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"], dependencies=_auth)
router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"], dependencies=_auth)
router.include_router(business_public.router, prefix="/business", tags=["Business"], dependencies=_auth)
router.include_router(audit.router, prefix="/audit", tags=["Audit"], dependencies=_auth)
router.include_router(review.router, prefix="/reviews", tags=["Review"], dependencies=_auth)
# ingest: read routes need auth; write routes carry their own require_admin.
router.include_router(ingest.router, prefix="/ingest", tags=["Ingestion"], dependencies=_auth)

# --- Reviewer or above --------------------------------------------------
router.include_router(
    status.router, prefix="/status", tags=["Status"],
    dependencies=[Depends(require_reviewer)],
)
router.include_router(
    corrections.router, prefix="/corrections", tags=["Corrections"],
    dependencies=[Depends(require_reviewer)],
)

# --- Admin only --------------------------------------------------------
router.include_router(
    matching.router, prefix="/matching", tags=["Matching"],
    dependencies=[Depends(require_admin)],
)
router.include_router(
    jobs.router, prefix="/jobs", tags=["Jobs"],
    dependencies=[Depends(require_admin)],
)
