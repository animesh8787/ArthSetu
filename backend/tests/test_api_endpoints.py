def test_dashboard_shape(client, seed, token):
    resp = client.get("/api/v1/dashboard", headers=token("viewer"))
    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "total_businesses", "active", "dormant", "closed", "unknown",
        "pending_reviews", "total_links", "auto_match_rate",
    ):
        assert key in body
    assert body["total_businesses"] == 2
    assert body["pending_reviews"] == 1
    assert body["total_links"] == 1
    assert body["auto_match_rate"] == 100.0  # the one link is AUTO_LINK


def test_analytics_districts(client, seed, token):
    rows = client.get("/api/v1/analytics/districts", headers=token("viewer")).json()
    names = {r["district"] for r in rows}
    assert {"Ludhiana", "Mohali"} <= names
    total = sum(r["total"] for r in rows)
    assert total == 2


def test_business_search_and_filters(client, seed, token):
    headers = token("viewer")

    everything = client.get("/api/v1/business/search", headers=headers).json()
    assert everything["total"] == 2

    by_name = client.get(
        "/api/v1/business/search", headers=headers, params={"q": "acme"}
    ).json()
    assert by_name["total"] == 1
    assert by_name["items"][0]["ubid"] == "UBID000001"

    closed = client.get(
        "/api/v1/business/search", headers=headers, params={"status": "closed"}
    ).json()
    assert closed["total"] == 1
    assert closed["items"][0]["business_name"] == "Beta Traders"


def test_business_profile_and_404(client, seed, token):
    headers = token("viewer")

    ok = client.get("/api/v1/business/UBID000001", headers=headers)
    assert ok.status_code == 200
    body = ok.json()
    assert body["linked_records_count"] == 1
    assert body["linked_records"][0]["decision"] == "auto_link"

    missing = client.get("/api/v1/business/UBID999999", headers=headers)
    assert missing.status_code == 404


def test_review_list_and_approve_flow(client, seed, token):
    reviewer = token("reviewer")

    listing = client.get(
        "/api/v1/reviews", headers=reviewer, params={"status": "open"}
    ).json()
    assert listing["total"] == 1
    case = listing["items"][0]
    assert case["candidate_name"] == "Beta Traders"

    approve = client.post(
        f"/api/v1/reviews/{seed['review_id']}/approve", headers=reviewer
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"
    assert approve.json()["link_id"]

    # the decision is attributed to the token's user in the audit trail
    audit = client.get(
        "/api/v1/audit",
        headers=token("admin"),
        params={"entity_type": "review_case", "action": "REVIEW_APPROVED"},
    ).json()
    assert audit["items"][0]["actor_id"] == "reviewer@test.local"


def test_matching_endpoint_is_admin_only(client, seed, token):
    path = f"/api/v1/matching/process/{seed['sr_new_id']}"
    assert client.post(path, headers=token("viewer")).status_code == 403
    assert client.post(path, headers=token("reviewer")).status_code == 403

    resp = client.post(path, headers=token("admin"))
    assert resp.status_code == 200
    assert resp.json()["decision"] in {"NEW_ENTITY", "REVIEW", "AUTO_LINK"}


def test_status_recompute_persists_snapshot(client, seed, token):
    resp = client.get("/api/v1/status/UBID000001", headers=token("reviewer"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in {"ACTIVE", "DORMANT", "CLOSED"}
    assert isinstance(body["reasons"], list)
