"""
Shared test fixtures.

A throwaway SQLite database is configured via env vars *before* any
`backend.app` module is imported, so the app's engine points at it.
"""

from __future__ import annotations

import itertools
import os
import tempfile
from collections.abc import Iterator
from types import SimpleNamespace

import pytest

_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP_DB.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB.name}"
# Background jobs run inline (no worker thread) so tests are deterministic —
# a job's result is available the instant submit_job() returns.
os.environ["JOBS_SYNC"] = "1"
# Matches the `seed` fixture's admin row so its is_bootstrap flag comes out
# true, the same as it would against a real BOOTSTRAP_ADMIN_EMAIL.
os.environ["BOOTSTRAP_ADMIN_EMAIL"] = "admin@test.local"

from typing import Annotated  # noqa: E402

from fastapi import Depends, HTTPException, status  # noqa: E402
from fastapi.security import HTTPAuthorizationCredentials  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from backend.app.api import deps  # noqa: E402
from backend.app.core import firebase  # noqa: E402
from backend.app.db import models  # noqa: E402,F401  (register tables)
from backend.app.db.base import Base  # noqa: E402
from backend.app.db.enums import (  # noqa: E402
    EntityStatusEnum,
    LinkDecisionEnum,
    ReviewCaseStatusEnum,
    UserRole,
)
from backend.app.db.models.business_entity import BusinessEntity  # noqa: E402
from backend.app.db.models.entity_record_link import EntityRecordLink  # noqa: E402
from backend.app.db.models.review_case import ReviewCase  # noqa: E402
from backend.app.db.models.source_record import SourceRecord  # noqa: E402
from backend.app.db.models.source_system import SourceSystem  # noqa: E402
from backend.app.db.models.user import User  # noqa: E402
from backend.app.db.session import SessionLocal, engine  # noqa: E402
from backend.app.services.scoring import normalize_address  # noqa: E402
from backend.app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_schema() -> Iterator[None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _teardown_file() -> None:
    try:
        os.unlink(_TMP_DB.name)
    except OSError:
        pass


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    _teardown_file()


@pytest.fixture
def db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


_TEST_UIDS = {
    "admin": "test-uid-admin",
    "reviewer": "test-uid-reviewer",
    "viewer": "test-uid-viewer",
    # A verified identity with deliberately no matching user_account row —
    # for testing that get_current_user 403s rather than auto-provisioning.
    "ghost": "test-uid-ghost",
}
_TEST_EMAILS = {
    "admin": "admin@test.local",
    "reviewer": "reviewer@test.local",
    "viewer": "viewer@test.local",
    "ghost": "ghost@test.local",
}


@pytest.fixture
def seed(db: Session) -> dict:
    """A small, deterministic dataset covering every role and match outcome."""

    users = {
        "admin": User(
            email=_TEST_EMAILS["admin"], full_name="Admin", role=UserRole.ADMIN,
            firebase_uid=_TEST_UIDS["admin"], is_active=True,
        ),
        "reviewer": User(
            email=_TEST_EMAILS["reviewer"], full_name="Reviewer", role=UserRole.REVIEWER,
            firebase_uid=_TEST_UIDS["reviewer"], is_active=True,
        ),
        "viewer": User(
            email=_TEST_EMAILS["viewer"], full_name="Viewer", role=UserRole.VIEWER,
            firebase_uid=_TEST_UIDS["viewer"], is_active=True,
        ),
    }
    db.add_all(users.values())

    system = SourceSystem(code="LABOUR", name="Labour Portal", department="Labour")
    db.add(system)
    db.flush()

    acme = BusinessEntity(
        ubid_code="UBID000001",
        legal_name="Acme Steel Works",
        normalized_name="acme steel works",
        pan="ABCDE1234F",
        gstin="03ABCDE1234F1Z5",
        address="Plot 42, Focal Point 3, Ludhiana, Punjab",
        normalized_address=normalize_address("Plot 42, Focal Point 3, Ludhiana, Punjab"),
        pin_code="141001",
        district="Ludhiana",
        sector="Manufacturing",
        status=EntityStatusEnum.ACTIVE,
    )
    beta = BusinessEntity(
        ubid_code="UBID000002",
        legal_name="Beta Traders",
        normalized_name="beta traders",
        pan="ZZZZZ9999Z",
        address="Shop 9, Grain Market, Mohali, Punjab",
        pin_code="160055",
        district="Mohali",
        sector="Retail",
        status=EntityStatusEnum.CLOSED,
    )
    db.add_all([acme, beta])
    db.flush()

    # A source record that clearly belongs to Acme (exact PAN + name).
    sr_match = SourceRecord(
        source_system_id=system.id,
        external_id="ext-match",
        raw_payload={"name": "ACME STEEL WORKS"},
        normalized_payload={"name": "acme steel works"},
        extracted_name="ACME STEEL WORKS",
        extracted_pan="ABCDE1234F",
        extracted_gstin="03ABCDE1234F1Z5",
        extracted_address="PLOT 42, FOCAL POINT, LUDHIANA",
        extracted_pin="141001",
    )
    # A source record with no plausible match.
    sr_new = SourceRecord(
        source_system_id=system.id,
        external_id="ext-new",
        raw_payload={"name": "Zephyr Logistics"},
        normalized_payload={"name": "zephyr logistics"},
        extracted_name="Zephyr Logistics",
        extracted_pan="QQQQQ0000Q",
        extracted_address="Plot 7, Transport Nagar, Amritsar",
        extracted_pin="143001",
    )
    db.add_all([sr_match, sr_new])
    db.flush()

    link = EntityRecordLink(
        source_record_id=sr_match.id,
        business_entity_id=acme.id,
        confidence=0.97,
        decision=LinkDecisionEnum.AUTO_LINK,
        explanation={"reasons": ["PAN exact match"]},
    )
    review = ReviewCase(
        source_record_id=sr_new.id,
        candidate_entity_id=beta.id,
        status=ReviewCaseStatusEnum.OPEN,
        confidence=0.6,
        evidence={"candidate_name": "Beta Traders", "reasons": ["weak name match"]},
        notes="needs a human",
    )
    db.add_all([link, review])
    db.commit()

    return {
        "acme_id": acme.id,
        "beta_id": beta.id,
        "sr_match_id": sr_match.id,
        "sr_new_id": sr_new.id,
        "review_id": review.id,
    }


class _FakeFirebaseAdmin:
    """In-memory stand-in for the bits of the Admin SDK user_service.py calls,
    so tests never touch a real Firebase project or the Auth Emulator."""

    def __init__(self) -> None:
        self._uid_by_email: dict[str, str] = {}
        self._counter = itertools.count(1)

    def create_user(self, *, email: str, password: str) -> SimpleNamespace:
        if email in self._uid_by_email:
            raise firebase.auth.EmailAlreadyExistsError("email already exists", None, None)
        uid = f"fake-uid-{next(self._counter)}"
        self._uid_by_email[email] = uid
        return SimpleNamespace(uid=uid)

    def update_user(self, uid: str, **changes) -> SimpleNamespace:
        return SimpleNamespace(uid=uid)

    def get_user_by_email(self, email: str) -> SimpleNamespace:
        uid = self._uid_by_email.get(email)
        if uid is None:
            raise firebase.auth.UserNotFoundError("no such user", None, None)
        return SimpleNamespace(uid=uid)

    def delete_user(self, uid: str) -> None:
        self._uid_by_email = {e: u for e, u in self._uid_by_email.items() if u != uid}


@pytest.fixture(autouse=True)
def fake_firebase_admin(monkeypatch: pytest.MonkeyPatch) -> _FakeFirebaseAdmin:
    fake = _FakeFirebaseAdmin()
    monkeypatch.setattr(firebase, "create_user", fake.create_user)
    monkeypatch.setattr(firebase, "update_user", fake.update_user)
    monkeypatch.setattr(firebase, "get_user_by_email", fake.get_user_by_email)
    monkeypatch.setattr(firebase, "delete_user", fake.delete_user)
    return fake


def _fake_verified_claims(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(deps.bearer_scheme)],
) -> dict[str, str]:
    """Replaces real Firebase token verification in tests: a fake bearer
    token of the form "fake:<role>" resolves straight to that role's fixed
    {uid, email} (matching the `seed` fixture's rows); a missing header or
    anything else 401s — same shape as a real missing/invalid token would."""
    role = creds.credentials.removeprefix("fake:") if creds else ""
    if role not in _TEST_UIDS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
    return {"uid": _TEST_UIDS[role], "email": _TEST_EMAILS[role]}


@pytest.fixture(autouse=True)
def _fake_auth_dependency() -> Iterator[None]:
    app.dependency_overrides[deps.get_verified_firebase_claims] = _fake_verified_claims
    yield
    app.dependency_overrides.pop(deps.get_verified_firebase_claims, None)


@pytest.fixture
def token():
    """token('admin'|'reviewer'|'viewer') -> Authorization header dict.

    The role is encoded directly in the (fake) bearer token, so — unlike a
    single shared dependency override — headers for different roles
    obtained earlier in a test stay valid regardless of what's called in
    between (matches how the old real-JWT fixture of the same name behaved).
    """

    def _for(role: str = "admin") -> dict[str, str]:
        return {"Authorization": f"Bearer fake:{role}"}

    return _for
