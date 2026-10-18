import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError

from backend.app.api.v1.router import router as api_router
from backend.app.core.config import settings
from backend.app.db.models.user import User
from backend.app.db.session import SessionLocal
from backend.app.services.job_runner import recover_interrupted_jobs
from backend.app.services.user_service import create_user


log = logging.getLogger("arthsetu")


def _bootstrap_admin() -> None:
    """First boot on an empty deployment: create the admin account from
    BOOTSTRAP_ADMIN_EMAIL/PASSWORD (in Firebase and locally) so there's a
    way to log in at all - the dev seeder (seed_dev.py) is demo tooling,
    not something you'd run against a real deployment.

    If the Firebase project already knows the email (database reset, Firebase
    kept), that account is adopted rather than left stranded. Only a lost race
    between concurrently starting workers is silent; any other failure is
    logged, because a missing admin means nobody can log in.
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
                adopt_existing=True,
            )
        except IntegrityError:  # another worker created the same admin first
            db.rollback()
        except Exception:  # noqa: BLE001
            db.rollback()
            log.exception("Bootstrap admin could not be created - nobody can sign in")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _bootstrap_admin()
    recover_interrupted_jobs()
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
    allow_credentials=False,  # bearer tokens, not cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")
