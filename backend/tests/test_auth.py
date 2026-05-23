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
