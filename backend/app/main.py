from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from backend.app.api.v1.router import router as api_router
from backend.app.core.config import settings
from backend.app.db.models.user import User
from backend.app.db.session import SessionLocal
from backend.app.services.user_service import create_user


def _bootstrap_admin() -> None:
    """First boot on an empty deployment: create the admin account from
    BOOTSTRAP_ADMIN_EMAIL/PASSWORD (in Firebase and locally) so there's a
    way to log in at all — the dev seeder (seed_dev.py) is demo tooling,
    not something you'd run against a real deployment.

    Guarded for multiple worker processes starting concurrently: if another
    worker already won the race, the unique email/firebase_uid constraint
    makes this a no-op rather than a crash.
    """
    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            return
        try:
            create_user(
                db,
                email=settings.BOOTSTRAP_ADMIN_EMAIL,
                full_name="System Administrator",
                password=settings.BOOTSTRAP_ADMIN_PASSWORD,
                role="admin",
            )
        except Exception:  # noqa: BLE001 — lost the race to another worker
            db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _bootstrap_admin()
    yield


app = FastAPI(
    title="ArthSetu API",
    description="Government-grade Business Identity & Activity Intelligence Platform",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")
