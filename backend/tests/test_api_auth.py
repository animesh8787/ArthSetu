def test_protected_route_requires_token(client, seed):
    assert client.get("/api/v1/dashboard").status_code == 401


def test_health_is_public(client, seed):
    assert client.get("/api/v1/health").status_code == 200


def test_verified_token_with_no_local_profile_is_403(client, seed, token):
    # A Firebase-verified identity with no matching user_account row (e.g.
    # never provisioned by an admin) must be rejected, not auto-provisioned.
    resp = client.get("/api/v1/dashboard", headers=token("ghost"))
    assert resp.status_code == 403


def test_unrecognised_token_is_401(client, seed):
    resp = client.get("/api/v1/dashboard", headers={"Authorization": "Bearer fake:stranger"})
    assert resp.status_code == 401


def test_me_returns_current_user(client, seed, token):
    resp = client.get("/api/v1/auth/me", headers=token("reviewer"))
    assert resp.status_code == 200
    assert resp.json()["email"] == "reviewer@test.local"


def test_viewer_cannot_approve_reviews(client, seed, token):
    resp = client.post(
        f"/api/v1/reviews/{seed['review_id']}/approve",
        headers=token("viewer"),
    )
    assert resp.status_code == 403


def test_reviewer_cannot_run_batch_status(client, seed, token):
    assert (
        client.post("/api/v1/status/run-all", headers=token("reviewer")).status_code
        == 403
    )


def test_reviewer_cannot_list_users(client, seed, token):
    assert (
        client.get("/api/v1/auth/users", headers=token("reviewer")).status_code == 403
    )


def test_admin_can_manage_users(client, seed, token):
    headers = token("admin")

    created = client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={
            "email": "newbie@test.local",
            "full_name": "New Bie",
            "role": "viewer",
            "password": "newbiepass",
        },
    )
    assert created.status_code == 201
    assert created.json()["email"] == "newbie@test.local"
    user_id = created.json()["id"]

    promoted = client.patch(
        f"/api/v1/auth/users/{user_id}",
        headers=headers,
        json={"role": "reviewer"},
    )
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "reviewer"


def test_create_user_with_duplicate_email_is_409(client, seed, token):
    resp = client.post(
        "/api/v1/auth/users",
        headers=token("admin"),
        json={
            "email": "reviewer@test.local",  # already seeded
            "full_name": "Duplicate",
            "role": "viewer",
            "password": "whatever123",
        },
    )
    assert resp.status_code == 409


def test_bootstrap_admin_cannot_be_demoted(client, seed, token):
    headers = token("admin")
    users = client.get("/api/v1/auth/users", headers=headers).json()
    admin_id = next(u["id"] for u in users if u["is_bootstrap"])

    resp = client.patch(
        f"/api/v1/auth/users/{admin_id}",
        headers=headers,
        json={"role": "viewer"},
    )
    assert resp.status_code == 400


def test_disabled_user_token_is_rejected(client, seed, token):
    admin_headers = token("admin")
    users = client.get("/api/v1/auth/users", headers=admin_headers).json()
    viewer_id = next(u["id"] for u in users if u["email"] == "viewer@test.local")

    viewer_headers = token("viewer")
    assert client.get("/api/v1/dashboard", headers=viewer_headers).status_code == 200

    client.patch(
        f"/api/v1/auth/users/{viewer_id}",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert client.get("/api/v1/dashboard", headers=viewer_headers).status_code == 403
