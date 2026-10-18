"""Smaller reliability fixes: bootstrap adoption, thresholds, job recovery, email changes, filters."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import Settings, settings
from backend.app.db.enums import JobStatusEnum, JobTypeEnum
from backend.app.db.models.job import Job
from backend.app.db.models.user import User
from backend.app.main import app
from backend.app.services import job_runner


def test_bootstrap_adopts_an_existing_firebase_account(db, fake_firebase_admin):
    # DB was reset but the Firebase project kept the admin: the old code left nobody able to sign in.
    fake_firebase_admin.create_user(email=settings.BOOTSTRAP_ADMIN_EMAIL, password="x")

    with TestClient(app):
        pass

    user = db.query(User).filter(User.email == settings.BOOTSTRAP_ADMIN_EMAIL).one()
    assert user.role.value == "admin"
    assert user.firebase_uid == "fake-uid-1"


def test_threshold_order_is_enforced(client, seed, token):
    resp = client.put(
        "/api/v1/matching/weights",
        json={"review_threshold": 0.95, "auto_link_threshold": 0.9},
        headers=token("admin"),
    )
    assert resp.status_code == 422


def test_calibration_buckets_follow_live_thresholds(client, seed, token):
    client.put(
        "/api/v1/matching/weights",
        json={"review_threshold": 0.5, "auto_link_threshold": 0.8},
        headers=token("admin"),
    )
    labels = [b["label"] for b in client.get("/api/v1/matching/calibration", headers=token("admin")).json()["buckets"]]
    assert labels[0].startswith("0.50") and labels[-1].startswith("0.80")


def test_orphaned_jobs_are_failed_on_restart(db):
    old = datetime.now(timezone.utc) - timedelta(minutes=30)
    stuck = Job(job_type=JobTypeEnum.STATUS_RUN_ALL, status=JobStatusEnum.RUNNING, payload={}, created_at=old)
    fresh = Job(job_type=JobTypeEnum.STATUS_RUN_ALL, status=JobStatusEnum.RUNNING, payload={})
    db.add_all([stuck, fresh])
    db.commit()

    assert job_runner.recover_interrupted_jobs() == 1

    db.refresh(stuck)
    db.refresh(fresh)
    assert stuck.status is JobStatusEnum.FAILED
    assert fresh.status is JobStatusEnum.RUNNING  # may belong to a sibling worker


@pytest.mark.parametrize("path", ["/api/v1/reviews?status=bogus", "/api/v1/business/search?status=bogus", "/api/v1/jobs?status=bogus"])
def test_bad_status_filter_is_422_not_500(client, seed, token, path):
    assert client.get(path, headers=token("admin")).status_code == 422


def test_deciding_a_decided_review_is_409(client, seed, token):
    url = f"/api/v1/reviews/{seed['review_id']}"
    assert client.post(f"{url}/reject", headers=token("reviewer")).status_code == 200
    assert client.post(f"{url}/approve", headers=token("reviewer")).status_code == 409


def test_unknown_district_filter_matches_null_districts(client, seed, token, db):
    from backend.app.db.models.business_entity import BusinessEntity

    db.add(BusinessEntity(ubid_code="UBIDNULL01", legal_name="No District Ltd", normalized_name="no district ltd"))
    db.commit()
    body = client.get("/api/v1/business/search?district=Unknown", headers=token("viewer")).json()
    assert [r["business_name"] for r in body["items"]] == ["No District Ltd"]


def test_email_change_moves_the_firebase_login_too(client, seed, token, db, monkeypatch):
    from backend.app.core import firebase

    calls = []
    monkeypatch.setattr(firebase, "update_user", lambda uid, **kw: calls.append((uid, kw)))
    viewer = db.query(User).filter(User.email == "viewer@test.local").one()

    resp = client.patch(f"/api/v1/auth/users/{viewer.id}", json={"email": "new@test.local"}, headers=token("admin"))

    assert resp.status_code == 200
    assert calls == [("test-uid-viewer", {"email": "new@test.local"})]


def test_postgres_scheme_is_normalised():
    assert Settings(DATABASE_URL="postgres://u:p@h/db").DATABASE_URL == "postgresql://u:p@h/db"
