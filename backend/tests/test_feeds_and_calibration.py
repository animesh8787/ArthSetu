"""Activity-event feeds, read-only connectors, the scheduler endpoint, contact matching
and calibration learned from reviewer decisions."""

import pytest

from backend.app.core.config import settings
from backend.app.db.enums import ReviewCaseStatusEnum
from backend.app.db.models.activity_event import ActivityEvent
from backend.app.db.models.business_entity import BusinessEntity
from backend.app.db.models.review_case import ReviewCase
from backend.app.db.models.source_record import SourceRecord
from backend.app.db.models.source_system import SourceSystem
from backend.app.services import calibration_ml, connectors, events_ingestion
from backend.app.services.matching_config_service import get_weights
from backend.app.services.matching_engine import _score_candidate


# ---------------------------------------------------------------- events

def test_events_resolve_by_ubid_gstin_and_department_record_id(db, seed):
    rows = [
        {"ubid": "UBID000001", "event_type": "gst_filed", "occurred_at": "2026-09-30"},
        {"gstin": "03ABCDE1234F1Z5", "event_type": "inspection", "occurred_at": "14-08-2026"},
        {"external_id": "ext-match", "event_type": "license_renewed", "occurred_at": "2026-07-01"},
    ]
    report = events_ingestion.ingest_events(db, rows, "LABOUR")

    assert (report.created, report.unresolved, report.errors) == (3, 0, [])
    assert db.query(ActivityEvent).filter_by(business_entity_id=seed["acme_id"]).count() == 3
    assert report.recomputed == 1  # one business touched


def test_resending_a_feed_is_harmless(db, seed):
    rows = [{"ubid": "UBID000001", "event_type": "gst_filed", "occurred_at": "2026-09-30"}]
    events_ingestion.ingest_events(db, rows)
    again = events_ingestion.ingest_events(db, rows)
    assert (again.created, again.skipped_duplicates) == (0, 1)


def test_bad_rows_are_reported_not_fatal(db, seed):
    report = events_ingestion.ingest_events(db, [
        {"ubid": "UBID000001", "event_type": "party", "occurred_at": "2026-09-30"},
        {"ubid": "UBID000001", "event_type": "gst_filed", "occurred_at": "soon"},
        {"ubid": "UBID999999", "event_type": "gst_filed", "occurred_at": "2026-09-30"},
        {"ubid": "UBID000002", "event_type": "closure_notice", "occurred_at": "2026-09-01"},
    ])
    assert report.created == 1 and report.unresolved == 1 and len(report.errors) == 3


def test_events_csv_endpoint_updates_the_status(client, seed, token, db):
    csv_body = b"UBID,Event Type,Date\nUBID000002,gst_filed,2026-10-01\nUBID000002,gst_filed,2026-09-20\n"
    resp = client.post(
        "/api/v1/ingest/events/csv", files={"file": ("e.csv", csv_body, "text/csv")}, headers=token("admin"),
    )
    assert resp.status_code == 200 and resp.json()["created"] == 2
    db.expire_all()
    # Beta Traders was CLOSED with no history; two fresh filings reopen it.
    assert db.get(BusinessEntity, seed["beta_id"]).status.value in {"active", "dormant"}


def test_events_endpoints_are_admin_only(client, seed, token):
    body = {"events": []}
    assert client.post("/api/v1/ingest/events", json=body, headers=token("reviewer")).status_code == 403
    assert client.post("/api/v1/ingest/events", json=body, headers=token("admin")).status_code == 200


# ------------------------------------------------------------ connectors

@pytest.mark.parametrize("url", [
    "http://example.com/x.csv", "https://localhost/x.csv", "https://127.0.0.1/x", "https://10.1.2.3/x",
    "https://169.254.169.254/latest/meta-data", "ftp://example.com/x",
])
def test_connector_urls_are_locked_down(url):
    with pytest.raises(ValueError):
        connectors.validate_pull_url(url)


def _system(db):
    system = db.query(SourceSystem).first()
    system.pull_url, system.pull_kind = "https://depts.example/labour.csv", "records"
    db.commit()
    return system


def test_sync_pulls_records_from_csv_and_matches_them(db, seed, monkeypatch):
    system = _system(db)
    monkeypatch.setattr(connectors, "validate_pull_url", lambda u: u)
    monkeypatch.setattr(connectors, "_fetch", lambda u: b"Reg No,Business Name,PAN\nR1,Acme Steel Works,ABCDE1234F\n")

    summary = connectors.sync_system(db, system)

    assert summary["ok"] and summary["created"] == 1
    assert summary["matching"]["auto_link"] + summary["matching"]["review"] == 1
    db.refresh(system)
    assert system.last_pull_at is not None and "1 records added" in system.last_pull_status


def test_sync_pulls_events_from_json(db, seed, monkeypatch):
    system = _system(db)
    system.pull_kind = "events"
    db.commit()
    monkeypatch.setattr(connectors, "validate_pull_url", lambda u: u)
    monkeypatch.setattr(
        connectors, "_fetch",
        lambda u: b'{"events": [{"ubid": "UBID000001", "type": "gst_filed", "date": "2026-10-01"}]}',
    )
    summary = connectors.sync_system(db, system)
    assert summary["ok"] and summary["created"] == 1


def test_a_failing_feed_is_recorded_not_raised(db, seed, monkeypatch):
    system = _system(db)
    monkeypatch.setattr(connectors, "validate_pull_url", lambda u: u)

    def boom(_):
        raise ValueError("Source answered HTTP 503")

    monkeypatch.setattr(connectors, "_fetch", boom)
    summary = connectors.sync_system(db, system)
    assert summary["ok"] is False
    db.refresh(system)
    assert "503" in system.last_pull_status


def test_connector_config_rejects_private_addresses(client, seed, token):
    resp = client.put(
        "/api/v1/ingest/source-systems/LABOUR/connector",
        json={"pull_url": "https://127.0.0.1/export.csv", "pull_kind": "records"},
        headers=token("admin"),
    )
    assert resp.status_code == 422


def test_connector_url_is_hidden_from_non_admins(client, seed, token, db):
    _system(db)
    seen = lambda role: client.get("/api/v1/ingest/source-systems", headers=token(role)).json()[0]["pull_url"]
    assert seen("admin") == "https://depts.example/labour.csv"
    assert seen("viewer") is None


# ------------------------------------------------------------ scheduler

def test_cron_tick_needs_the_shared_secret(client, seed, monkeypatch):
    monkeypatch.setattr(settings, "CRON_SECRET", "")
    assert client.post("/api/v1/cron/tick").status_code == 404

    monkeypatch.setattr(settings, "CRON_SECRET", "s3cret")
    assert client.post("/api/v1/cron/tick", headers={"X-Cron-Secret": "nope"}).status_code == 401
    resp = client.post("/api/v1/cron/tick", headers={"X-Cron-Secret": "s3cret"})
    assert resp.status_code == 202 and resp.json()["status"] == "succeeded"  # JOBS_SYNC in tests


# ------------------------------------------------------------ contact signal

def _record(**kw):
    return SourceRecord(external_id="c", raw_payload={}, normalized_payload={}, **kw)


def test_matching_phone_lifts_the_score_but_only_for_a_related_name(db, seed):
    weights = get_weights(db)
    acme = db.get(BusinessEntity, seed["acme_id"])
    acme.phone = "9876543210"

    same_name = _record(extracted_name="Acme Steel Works", extracted_phone="+91 98765 43210")
    other_name = _record(extracted_name="Zzz Unrelated", extracted_phone="9876543210")
    plain = _record(extracted_name="Acme Steel Works")

    boosted, reasons = _score_candidate(same_name, acme, weights)
    base, _ = _score_candidate(plain, acme, weights)
    ignored, ignored_reasons = _score_candidate(other_name, acme, weights)

    assert boosted == pytest.approx(base + weights.contact_weight)
    assert "Contact match (phone)" in reasons
    assert "Contact match (phone)" not in ignored_reasons


# ------------------------------------------------------------ learned calibration

def _decided(db, seed, n, approved, name_sim, address_sim):
    for i in range(n):
        db.add(ReviewCase(
            source_record_id=seed["sr_new_id"],
            candidate_entity_id=seed["beta_id"],
            status=ReviewCaseStatusEnum.APPROVED if approved else ReviewCaseStatusEnum.REJECTED,
            confidence=0.8,
            evidence={"reasons": [f"Name similarity {name_sim}", f"Address similarity {address_sim + (i % 3) / 100}"]},
        ))
    db.commit()


def test_suggestion_waits_for_enough_decisions(db, seed):
    result = calibration_ml.suggestion(db)
    assert result["ready"] is False and "at least" in result["message"]


def test_suggestion_learns_that_name_matters_and_is_explainable(db, seed):
    _decided(db, seed, 15, True, 0.95, 0.4)
    _decided(db, seed, 15, False, 0.35, 0.4)  # same address score either way: no information

    result = calibration_ml.suggestion(db)

    assert result["ready"] and result["accuracy"] >= 0.95
    by_field = {s["field"]: s for s in result["signals"]}
    assert by_field["name_weight"]["learned"] and by_field["name_weight"]["coefficient"] > 0
    assert by_field["name_weight"]["approved_avg"] > by_field["name_weight"]["rejected_avg"]
    assert not by_field["gstin_weight"]["learned"]  # never varied, left alone
    assert by_field["gstin_weight"]["suggested_weight"] == by_field["gstin_weight"]["current_weight"]


def test_applying_the_suggestion_changes_the_weights_within_bounds(client, seed, token, db):
    _decided(db, seed, 15, True, 0.95, 0.4)
    _decided(db, seed, 15, False, 0.35, 0.4)
    before = get_weights(db).name_weight

    resp = client.post("/api/v1/matching/calibration/apply", headers=token("admin"))

    assert resp.status_code == 200
    after = resp.json()["name_weight"]
    assert before * 0.25 <= after <= min(1.0, before * 2.5)
    assert "learned from 30 reviews" in resp.json()["updated_by"]
    assert client.post("/api/v1/matching/calibration/apply", headers=token("reviewer")).status_code == 403
