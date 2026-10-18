"""The 'no inspection in N months' search filter and the per-business audit trail."""

from datetime import datetime, timedelta, timezone

from backend.app.db.enums import EventTypeEnum
from backend.app.db.models.activity_event import ActivityEvent
from backend.app.services import corrections_service as corrections
from backend.app.services.review_service import reject_review_case


def _inspection(db, entity_id, days_ago):
    db.add(ActivityEvent(
        business_entity_id=entity_id,
        event_type=EventTypeEnum.INSPECTION,
        score=0.75,
        occurred_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
        payload={},
    ))
    db.commit()


def _ubids(client, token, query):
    body = client.get(f"/api/v1/business/search?{query}", headers=token("viewer")).json()
    return {r["ubid"] for r in body["items"]}


def test_no_inspection_filter_finds_uninspected_and_overdue_businesses(client, seed, token, db):
    _inspection(db, seed["acme_id"], days_ago=30)     # inspected last month
    # Beta has never been inspected

    assert _ubids(client, token, "no_inspection_months=18") == {"UBID000002"}

    # age Acme's inspection past the window and it joins the list
    _inspection(db, seed["beta_id"], days_ago=800)
    db.query(ActivityEvent).filter_by(business_entity_id=seed["acme_id"]).update(
        {"occurred_at": datetime.now(timezone.utc) - timedelta(days=700)}
    )
    db.commit()
    assert _ubids(client, token, "no_inspection_months=18") == {"UBID000001", "UBID000002"}
    assert _ubids(client, token, "no_inspection_months=24") == {"UBID000002"}


def test_business_trail_collects_every_kind_of_change(client, seed, token, db):
    reject_review_case(db, str(seed["review_id"]), "rev@test.local")           # review_case + new entity
    corrections.override_status(db, "UBID000001", "rev@test.local", "closed", "verified shut")

    acme = client.get(
        f"/api/v1/audit?business_id={seed['acme_id']}&limit=50", headers=token("viewer")
    ).json()["items"]
    beta = client.get(
        f"/api/v1/audit?business_id={seed['beta_id']}&limit=50", headers=token("viewer")
    ).json()["items"]

    assert "STATUS_OVERRIDDEN" in {e["action"] for e in acme}
    # The rejected case proposed Beta as the candidate, so it is part of Beta's story
    assert "REVIEW_REJECTED" in {e["action"] for e in beta}
    assert "REVIEW_REJECTED" not in {e["action"] for e in acme}


def test_trail_for_unknown_business_is_404(client, seed, token):
    resp = client.get("/api/v1/audit?business_id=00000000-0000-0000-0000-000000000000", headers=token("viewer"))
    assert resp.status_code == 404
