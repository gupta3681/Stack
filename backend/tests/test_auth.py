"""Auth round-trips: signup, login, logout, session cookie behavior."""

from fastapi.testclient import TestClient


def test_unauthenticated_endpoints_return_401(client: TestClient):
    assert client.get("/stacks/today").status_code == 401
    assert client.get("/tasks/backlog").status_code == 401
    assert client.get("/auth/me").status_code == 401


def test_signup_creates_user_and_sets_session_cookie(client: TestClient):
    r = client.post(
        "/auth/signup",
        json={"email": "a@b.com", "password": "passworddd", "display_name": "Test"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "a@b.com"
    assert body["display_name"] == "Test"
    assert "stack_session" in r.cookies
    # Subsequent authed requests work
    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "a@b.com"


def test_session_token_is_hashed_at_rest(client: TestClient):
    from app import database as db_module
    from app import models

    r = client.post(
        "/auth/signup",
        json={"email": "hashcheck@example.com", "password": "passworddd"},
    )
    assert r.status_code == 201
    raw_token = r.cookies["stack_session"]

    override = client.app.dependency_overrides[db_module.get_db]
    session_iter = override()
    db = next(session_iter)
    try:
        stored = db.query(models.Session).one()
    finally:
        session_iter.close()

    assert stored.id != raw_token
    assert len(stored.id) == 64


def test_signup_normalizes_email_to_lowercase(client: TestClient):
    r = client.post(
        "/auth/signup", json={"email": "MixedCase@Example.com", "password": "passworddd"}
    )
    assert r.status_code == 201
    assert r.json()["email"] == "mixedcase@example.com"


def test_signup_duplicate_email_returns_409(client: TestClient):
    client.post("/auth/signup", json={"email": "a@b.com", "password": "passworddd"})
    r = client.post("/auth/signup", json={"email": "a@b.com", "password": "passworddd"})
    assert r.status_code == 409


def test_signup_rejects_short_password(client: TestClient):
    r = client.post("/auth/signup", json={"email": "a@b.com", "password": "short"})
    assert r.status_code == 422  # pydantic min_length


def test_login_with_correct_credentials(client: TestClient):
    client.post("/auth/signup", json={"email": "a@b.com", "password": "passworddd"})
    # Clear cookies and log in fresh
    client.cookies.clear()
    r = client.post("/auth/login", json={"email": "a@b.com", "password": "passworddd"})
    assert r.status_code == 200
    assert "stack_session" in r.cookies


def test_login_with_wrong_password_returns_401(client: TestClient):
    client.post("/auth/signup", json={"email": "a@b.com", "password": "passworddd"})
    client.cookies.clear()
    r = client.post("/auth/login", json={"email": "a@b.com", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_email_returns_401(client: TestClient):
    r = client.post("/auth/login", json={"email": "nobody@nowhere.com", "password": "passworddd"})
    assert r.status_code == 401


def test_logout_revokes_session(client: TestClient):
    client.post("/auth/signup", json={"email": "a@b.com", "password": "passworddd"})
    assert client.get("/auth/me").status_code == 200
    r = client.post("/auth/logout")
    assert r.status_code == 204
    # Cookie cleared on the client; even if it weren't, the session row is gone
    assert client.get("/auth/me").status_code == 401


def test_logout_without_cookie_is_idempotent_204(client: TestClient):
    r = client.post("/auth/logout")
    assert r.status_code == 204


def test_unsafe_requests_require_csrf_header(client: TestClient):
    client.headers.pop("X-Stack-CSRF", None)
    r = client.post(
        "/auth/signup",
        json={"email": "csrf@example.com", "password": "passworddd"},
    )
    assert r.status_code == 403


def test_update_profile_display_name(auth_client: TestClient):
    r = auth_client.patch("/auth/me", json={"display_name": "Renamed"})
    assert r.status_code == 200
    assert r.json()["display_name"] == "Renamed"
    # Persists across reads
    assert auth_client.get("/auth/me").json()["display_name"] == "Renamed"


def test_update_profile_clears_display_name_with_null(auth_client: TestClient):
    auth_client.patch("/auth/me", json={"display_name": "Set"})
    r = auth_client.patch("/auth/me", json={"display_name": None})
    assert r.json()["display_name"] is None


def test_update_profile_omit_field_preserves(auth_client: TestClient):
    auth_client.patch("/auth/me", json={"display_name": "Keep"})
    r = auth_client.patch("/auth/me", json={})
    assert r.json()["display_name"] == "Keep"


def test_change_password_wrong_current_rejected(auth_client: TestClient):
    r = auth_client.post(
        "/auth/change-password",
        json={"current_password": "wrong-pw", "new_password": "newpassword123"},
    )
    assert r.status_code == 401


def test_change_password_same_password_rejected(auth_client: TestClient):
    r = auth_client.post(
        "/auth/change-password",
        json={"current_password": "correcthorse", "new_password": "correcthorse"},
    )
    assert r.status_code == 400


def test_change_password_success_then_login_with_new_pw(auth_client: TestClient):
    r = auth_client.post(
        "/auth/change-password",
        json={"current_password": "correcthorse", "new_password": "freshpassword99"},
    )
    assert r.status_code == 204
    # Old password no longer works
    auth_client.cookies.clear()
    r = auth_client.post(
        "/auth/login",
        json={"email": "aryan@example.com", "password": "correcthorse"},
    )
    assert r.status_code == 401
    # New one does
    r = auth_client.post(
        "/auth/login",
        json={"email": "aryan@example.com", "password": "freshpassword99"},
    )
    assert r.status_code == 200


def test_new_user_is_not_onboarded(auth_client: TestClient):
    me = auth_client.get("/auth/me").json()
    assert me["onboarded"] is False


def test_complete_onboarding_flips_flag(auth_client: TestClient):
    r = auth_client.post("/auth/me/onboarded")
    assert r.status_code == 200
    assert r.json()["onboarded"] is True
    # Persists across reads
    assert auth_client.get("/auth/me").json()["onboarded"] is True


def test_complete_onboarding_is_idempotent(auth_client: TestClient):
    first = auth_client.post("/auth/me/onboarded").json()
    second = auth_client.post("/auth/me/onboarded").json()
    assert first["onboarded_at"] == second["onboarded_at"]


def test_login_rate_limit_returns_429(client: TestClient, monkeypatch):
    from app.security import reset_rate_limits

    monkeypatch.setenv("AUTH_RATE_LIMIT_LOGIN_EMAIL_ATTEMPTS", "2")
    monkeypatch.setenv("AUTH_RATE_LIMIT_LOGIN_IP_ATTEMPTS", "100")
    reset_rate_limits()

    client.post("/auth/signup", json={"email": "rate@example.com", "password": "passworddd"})
    client.cookies.clear()

    for _ in range(2):
        r = client.post("/auth/login", json={"email": "rate@example.com", "password": "wrong"})
        assert r.status_code == 401
    r = client.post("/auth/login", json={"email": "rate@example.com", "password": "wrong"})
    assert r.status_code == 429
