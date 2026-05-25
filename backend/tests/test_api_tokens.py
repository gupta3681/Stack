"""Tests for the API-token bearer-auth path.

Covers the contract:
- Token creation returns the raw secret exactly once; list/get never do.
- Bearer auth works on existing endpoints and bypasses the CSRF header.
- A bearer-authed request CANNOT mint / revoke tokens or change password
  (require_session_auth gate).
- One user's token can't see another user's data and can't touch their tokens.
- last_used_at is bumped on use.
- Invalid/revoked tokens 401.
"""

from fastapi.testclient import TestClient


def _bare_client() -> TestClient:
    """A fresh TestClient with no cookie jar and no CSRF header.

    Mirrors what a CLI / curl / agent looks like to the server.
    """
    from app.main import app

    return TestClient(app)


def test_create_token_returns_raw_secret_once(auth_client):
    r = auth_client.post("/auth/tokens", json={"name": "laptop"})
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["name"] == "laptop"
    assert data["token"].startswith("stk_")
    assert len(data["token"]) > 20
    assert data["prefix"] == data["token"][:12]
    assert data["last_used_at"] is None


def test_list_tokens_never_exposes_raw_secret(auth_client):
    auth_client.post("/auth/tokens", json={"name": "laptop"})
    auth_client.post("/auth/tokens", json={"name": "agent"})
    r = auth_client.get("/auth/tokens")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 2
    for item in items:
        assert "token" not in item
        assert item["prefix"].startswith("stk_")
        assert "name" in item


def test_bearer_auth_works_on_protected_endpoint(auth_client):
    raw = auth_client.post("/auth/tokens", json={"name": "cli"}).json()["token"]
    bare = _bare_client()
    r = bare.get("/auth/me", headers={"Authorization": f"Bearer {raw}"})
    assert r.status_code == 200
    assert r.json()["email"] == "aryan@example.com"


def test_bearer_auth_skips_csrf_on_unsafe_request(auth_client):
    """Without bearer, a POST without the CSRF header is 403. With bearer
    auth it must succeed — CLI/agent clients don't and can't carry that header.
    """
    raw = auth_client.post("/auth/tokens", json={"name": "cli"}).json()["token"]
    bare = _bare_client()
    # Sanity: no bearer, no CSRF → blocked
    r = bare.post("/stacks/topics", json={"kind": "todo", "name": "x"})
    assert r.status_code == 403
    # With bearer, no CSRF → allowed
    r = bare.post(
        "/stacks/topics",
        json={"kind": "todo", "name": "from cli"},
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "from cli"


def test_invalid_bearer_token_returns_401(client):
    bare = _bare_client()
    r = bare.get("/auth/me", headers={"Authorization": "Bearer stk_doesnotexist"})
    assert r.status_code == 401


def test_empty_bearer_token_returns_401(client):
    bare = _bare_client()
    r = bare.get("/auth/me", headers={"Authorization": "Bearer "})
    assert r.status_code == 401


def test_revoked_token_returns_401(auth_client):
    created = auth_client.post("/auth/tokens", json={"name": "laptop"}).json()
    raw, tid = created["token"], created["id"]
    r = auth_client.delete(f"/auth/tokens/{tid}")
    assert r.status_code == 204
    bare = _bare_client()
    r = bare.get("/auth/me", headers={"Authorization": f"Bearer {raw}"})
    assert r.status_code == 401


def test_bearer_cannot_mint_token(auth_client):
    """A bearer-authed client must not be able to create more tokens —
    that would let a leaked token spawn fresh siblings the user can't see
    on their device list.
    """
    raw = auth_client.post("/auth/tokens", json={"name": "first"}).json()["token"]
    bare = _bare_client()
    r = bare.post(
        "/auth/tokens",
        json={"name": "second"},
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert r.status_code == 403


def test_bearer_cannot_revoke_token(auth_client):
    a = auth_client.post("/auth/tokens", json={"name": "a"}).json()
    b = auth_client.post("/auth/tokens", json={"name": "b"}).json()
    bare = _bare_client()
    r = bare.delete(
        f"/auth/tokens/{b['id']}",
        headers={"Authorization": f"Bearer {a['token']}"},
    )
    assert r.status_code == 403


def test_bearer_cannot_change_password(auth_client):
    """Critical: a leaked token must not escalate to permanent account takeover."""
    raw = auth_client.post("/auth/tokens", json={"name": "cli"}).json()["token"]
    bare = _bare_client()
    r = bare.post(
        "/auth/change-password",
        json={"current_password": "correcthorse", "new_password": "newpassword12345"},
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert r.status_code == 403


def test_other_user_cannot_revoke_token(auth_client, second_client):
    tid = auth_client.post("/auth/tokens", json={"name": "mine"}).json()["id"]
    # second_client is a logged-in different user; uses cookie auth, not bearer.
    r = second_client.delete(f"/auth/tokens/{tid}")
    # 404 (not 403) — don't leak that the ID exists for another user.
    assert r.status_code == 404


def test_other_user_cannot_see_my_tokens(auth_client, second_client):
    auth_client.post("/auth/tokens", json={"name": "mine"})
    r = second_client.get("/auth/tokens")
    assert r.status_code == 200
    assert r.json() == []


def test_bearer_token_only_sees_own_data(auth_client, second_client):
    """A token issued for aryan must not access another user's stacks."""
    # second creates a topic stack
    s = second_client.post(
        "/stacks/topics", json={"kind": "todo", "name": "Others"}
    ).json()
    # aryan mints a token and tries to read it
    raw = auth_client.post("/auth/tokens", json={"name": "cli"}).json()["token"]
    bare = _bare_client()
    r = bare.get(
        f"/stacks/topics/{s['id']}",
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert r.status_code == 404


def test_last_used_at_updates_on_use(auth_client):
    created = auth_client.post("/auth/tokens", json={"name": "cli"}).json()
    raw, tid = created["token"], created["id"]
    # Initially null
    initial = next(t for t in auth_client.get("/auth/tokens").json() if t["id"] == tid)
    assert initial["last_used_at"] is None
    # Use it
    bare = _bare_client()
    assert bare.get(
        "/auth/me", headers={"Authorization": f"Bearer {raw}"}
    ).status_code == 200
    # Recheck
    after = next(t for t in auth_client.get("/auth/tokens").json() if t["id"] == tid)
    assert after["last_used_at"] is not None


def test_delete_user_cascade_drops_tokens(auth_client, client):
    """User → ApiToken FK is ondelete=CASCADE so a deleted user's tokens
    disappear too. We don't have a delete-user endpoint, but the cascade is
    a property of the schema we should still pin down in tests."""
    from app import models
    from app.database import Base
    from sqlalchemy.orm import sessionmaker

    raw = auth_client.post("/auth/tokens", json={"name": "cli"}).json()["token"]
    bare = _bare_client()
    assert bare.get(
        "/auth/me", headers={"Authorization": f"Bearer {raw}"}
    ).status_code == 200

    # Reach into the same engine the TestClient uses to delete the user row.
    from app import database as db_module

    db_gen = db_module.get_db()
    # The test client overrides get_db, so call the override.
    from app.main import app

    override = app.dependency_overrides[db_module.get_db]
    db_session = next(override())
    try:
        user = db_session.query(models.User).filter_by(email="aryan@example.com").one()
        db_session.delete(user)
        db_session.commit()
        # No tokens left
        remaining = db_session.query(models.ApiToken).count()
        assert remaining == 0
    finally:
        db_session.close()

    # Token now returns 401 (token row gone)
    r = bare.get("/auth/me", headers={"Authorization": f"Bearer {raw}"})
    assert r.status_code == 401


def test_token_name_required(auth_client):
    r = auth_client.post("/auth/tokens", json={"name": ""})
    assert r.status_code == 422


def test_token_name_whitespace_only_rejected(auth_client):
    """Pydantic min_length=1 alone would accept '   ' (len=3). The post-strip
    validator must reject it before it lands in the DB as an empty name."""
    r = auth_client.post("/auth/tokens", json={"name": "     "})
    assert r.status_code == 422


def test_token_name_stripped_on_create(auth_client):
    r = auth_client.post("/auth/tokens", json={"name": "  laptop  "})
    assert r.status_code == 201
    assert r.json()["name"] == "laptop"


def test_logout_with_bearer_revokes_the_bearer(auth_client):
    """A CLI calling POST /auth/logout with its bearer should actually
    invalidate the token, not just return 204 with the token still working."""
    raw = auth_client.post("/auth/tokens", json={"name": "cli"}).json()["token"]
    bare = _bare_client()
    # Sanity: token works
    assert bare.get(
        "/auth/me", headers={"Authorization": f"Bearer {raw}"}
    ).status_code == 200
    # Logout via bearer
    r = bare.post("/auth/logout", headers={"Authorization": f"Bearer {raw}"})
    assert r.status_code == 204
    # Token is now invalid
    assert bare.get(
        "/auth/me", headers={"Authorization": f"Bearer {raw}"}
    ).status_code == 401


def test_logout_with_only_cookie_does_not_touch_bearers(auth_client):
    """A browser logout (cookie only, no bearer) should not affect any of
    the user's API tokens."""
    raw = auth_client.post("/auth/tokens", json={"name": "cli"}).json()["token"]
    r = auth_client.post("/auth/logout")
    assert r.status_code == 204
    # Bearer is unaffected
    bare = _bare_client()
    assert bare.get(
        "/auth/me", headers={"Authorization": f"Bearer {raw}"}
    ).status_code == 200


def test_bearer_denied_on_session_only_does_not_bump_last_used_at(auth_client):
    """The require_session_auth dependency runs BEFORE get_current_user, so
    a bearer-authed attempt on /auth/change-password must be 403'd without
    updating the token's last_used_at — otherwise the audit signal is
    polluted (every probe looks like 'recent use')."""
    created = auth_client.post("/auth/tokens", json={"name": "cli"}).json()
    raw, tid = created["token"], created["id"]
    bare = _bare_client()
    # Attempt a denied action with the bearer
    r = bare.post(
        "/auth/change-password",
        json={"current_password": "correcthorse", "new_password": "newpassword12345"},
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert r.status_code == 403
    # last_used_at must still be null — get_current_user never resolved
    items = auth_client.get("/auth/tokens").json()
    row = next(t for t in items if t["id"] == tid)
    assert row["last_used_at"] is None


def test_invalid_bearer_returns_uniform_message(client):
    """Unified 401 detail — never distinguish 'no such token' from 'orphan
    token whose user was deleted'. (CASCADE makes the orphan case unreachable
    in practice; uniformity is a defense-in-depth invariant.)"""
    bare = _bare_client()
    r1 = bare.get("/auth/me", headers={"Authorization": "Bearer stk_nope"})
    r2 = bare.get("/auth/me", headers={"Authorization": "Bearer "})
    assert r1.status_code == r2.status_code == 401
    assert r1.json()["detail"] == r2.json()["detail"] == "Invalid API token"
