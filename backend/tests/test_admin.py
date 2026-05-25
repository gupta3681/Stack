"""Tests for the /admin/* router.

Covers:
- Non-admin users get 403 on every admin endpoint.
- Bearer tokens belonging to admins work (admin endpoints accept either auth).
- /admin/stats returns the right shape and numbers move when data changes.
- /admin/users list includes per-user task counts + last_session, never
  exposes password_hash or any other secret.
- Auto-promote via ADMIN_EMAILS env var flips is_admin on next session resolve.
"""

import importlib
import os

import pytest
from fastapi.testclient import TestClient


def _make_admin(client: TestClient, email: str) -> None:
    """Manually promote a user to admin via the test DB session."""
    from app import database as db_module
    from app import models
    from app.main import app

    override = app.dependency_overrides[db_module.get_db]
    session = next(override())
    try:
        user = session.query(models.User).filter_by(email=email).one()
        user.is_admin = True
        session.commit()
    finally:
        session.close()


def test_stats_requires_admin(auth_client: TestClient):
    """Plain logged-in user gets 403, not 401, not 404."""
    r = auth_client.get("/admin/stats")
    assert r.status_code == 403


def test_users_requires_admin(auth_client: TestClient):
    r = auth_client.get("/admin/users")
    assert r.status_code == 403


def test_stats_anonymous_returns_401(client: TestClient):
    """No session, no bearer → 401 before the admin check fires."""
    # The plain `client` fixture has the CSRF header but no auth cookie.
    r = client.get("/admin/stats")
    assert r.status_code == 401


def test_admin_can_read_stats(auth_client: TestClient):
    _make_admin(auth_client, "aryan@example.com")
    r = auth_client.get("/admin/stats")
    assert r.status_code == 200, r.text
    body = r.json()
    # Shape check — top-level sections all present.
    assert set(body.keys()) >= {
        "users",
        "tasks",
        "stacks",
        "api_tokens",
        "recent_signups",
        "timeseries",
        "generated_at",
    }
    # Timeseries: 30 contiguous days each, oldest first.
    ts = body["timeseries"]
    assert len(ts["signups_by_day"]) == 30
    assert len(ts["completions_by_day"]) == 30
    # Verify it's chronological + ISO-shaped.
    dates = [d["date"] for d in ts["signups_by_day"]]
    assert dates == sorted(dates)
    assert all(len(d) == 10 for d in dates)  # YYYY-MM-DD
    # The admin's own signup landed in the window so today's bucket is >=1.
    assert ts["signups_by_day"][-1]["count"] >= 1
    assert body["users"]["total"] == 1  # just the one user signed up in fixture
    assert body["users"]["admin_count"] == 1
    # Recent signups should include the admin themselves and never expose
    # password_hash.
    recent = body["recent_signups"]
    assert len(recent) == 1
    assert recent[0]["email"] == "aryan@example.com"
    assert "password_hash" not in recent[0]


def test_stats_counters_move_with_real_data(auth_client: TestClient):
    """Create tasks + a topic stack, then verify counters reflect reality."""
    _make_admin(auth_client, "aryan@example.com")

    # Add 3 tasks in a daily stack, mark one done, one cancelled
    auth_client.post(
        "/tasks", json={"name": "a", "stack_date": "2026-06-01"}
    )
    t2 = auth_client.post(
        "/tasks", json={"name": "b", "stack_date": "2026-06-01"}
    ).json()
    t3 = auth_client.post(
        "/tasks", json={"name": "c", "stack_date": "2026-06-01"}
    ).json()
    auth_client.patch(f"/tasks/{t2['id']}", json={"status": "done"})
    auth_client.patch(f"/tasks/{t3['id']}", json={"status": "cancelled"})

    # Topic stack with 2 tasks, then make it public
    ts = auth_client.post(
        "/stacks/topics", json={"kind": "reading", "name": "Books"}
    ).json()
    auth_client.post("/tasks", json={"name": "r1", "stack_id": ts["id"]})
    auth_client.post("/tasks", json={"name": "r2", "stack_id": ts["id"]})
    auth_client.post(f"/stacks/topics/{ts['id']}/share")

    r = auth_client.get("/admin/stats")
    body = r.json()
    # 5 tasks total: 3 daily (1 pending, 1 done, 1 cancelled) + 2 topic
    assert body["tasks"]["total"] == 5
    assert body["tasks"]["done"] == 1
    assert body["tasks"]["cancelled"] == 1
    assert body["tasks"]["completed_today"] >= 1
    assert body["stacks"]["topic_total"] == 1
    assert body["stacks"]["by_kind"].get("reading") == 1
    assert body["stacks"]["public_count"] == 1


def test_users_list_includes_aggregates_no_secrets(auth_client: TestClient):
    _make_admin(auth_client, "aryan@example.com")

    # Add 2 tasks to give a non-zero task_count
    auth_client.post("/tasks", json={"name": "a", "stack_date": "2026-06-01"})
    auth_client.post("/tasks", json={"name": "b", "stack_date": "2026-06-01"})

    r = auth_client.get("/admin/users")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["email"] == "aryan@example.com"
    assert row["task_count"] == 2
    assert row["is_admin"] is True
    assert row["last_session_at"] is not None  # signup created a session
    # Critical: no password_hash field or any other secret.
    assert "password_hash" not in row


def test_users_list_includes_multiple_users(auth_client: TestClient, second_client: TestClient):
    _make_admin(auth_client, "aryan@example.com")
    r = auth_client.get("/admin/users")
    rows = r.json()
    emails = {row["email"] for row in rows}
    assert emails == {"aryan@example.com", "other@example.com"}
    # Only one is admin
    admins = [r for r in rows if r["is_admin"]]
    assert len(admins) == 1
    assert admins[0]["email"] == "aryan@example.com"


def test_other_user_cannot_see_admin_endpoints(
    auth_client: TestClient, second_client: TestClient
):
    """auth_client (Aryan) is admin; second_client (Other) is not → 403."""
    _make_admin(auth_client, "aryan@example.com")
    assert second_client.get("/admin/stats").status_code == 403
    assert second_client.get("/admin/users").status_code == 403


def test_admin_bearer_token_works_for_stats(auth_client: TestClient):
    """An admin's bearer token can hit /admin/stats (read-only endpoint).
    This matters: an admin running a usage-extraction script from CI is a
    real workflow."""
    _make_admin(auth_client, "aryan@example.com")
    # Mint a bearer token from the admin's session
    tok = auth_client.post("/auth/tokens", json={"name": "cli"}).json()["token"]

    from app.main import app

    bare = TestClient(app)
    r = bare.get(
        "/admin/stats", headers={"Authorization": f"Bearer {tok}"}
    )
    assert r.status_code == 200


def test_non_admin_bearer_token_gets_403(auth_client: TestClient):
    """A regular user's bearer token must NOT bypass the admin check."""
    # Don't promote — auth_client stays a regular user
    tok = auth_client.post("/auth/tokens", json={"name": "cli"}).json()["token"]

    from app.main import app

    bare = TestClient(app)
    r = bare.get(
        "/admin/stats", headers={"Authorization": f"Bearer {tok}"}
    )
    assert r.status_code == 403


def test_admin_emails_env_auto_promotes_on_session_resolve(monkeypatch):
    """Setting ADMIN_EMAILS before app import auto-promotes matching users
    on their next request. Must reload auth module so its module-level
    env-read picks up the new value."""
    monkeypatch.setenv("ADMIN_EMAILS", "boss@example.com")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    # Reload auth so it re-reads ADMIN_EMAILS at import time.
    from app import auth as auth_module

    importlib.reload(auth_module)
    assert "boss@example.com" in auth_module._ADMIN_EMAILS

    # Build a fresh test client + sign up boss; the auto-promote should
    # fire on the next request (it runs inside get_current_user, which
    # signup's session-resolution path doesn't touch — but the next /auth/me
    # does).
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fks(conn, _):
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.close()

    from app import database as db_module
    from app.database import Base
    from app.main import app
    from app.security import reset_rate_limits

    reset_rate_limits()
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[db_module.get_db] = override_get_db
    try:
        client = TestClient(app)
        client.headers.update({"X-Stack-CSRF": "1"})
        r = client.post(
            "/auth/signup",
            json={"email": "boss@example.com", "password": "correcthorse"},
        )
        assert r.status_code == 201
        # First /auth/me after signup runs get_current_user → auto-promote
        me = client.get("/auth/me").json()
        assert me["is_admin"] is True
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
