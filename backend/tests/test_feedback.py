"""Tests for the feedback capture endpoint + admin read path."""

from fastapi.testclient import TestClient


def _make_admin(client: TestClient, email: str) -> None:
    from app import database as db_module
    from app import models
    from app.main import app

    override = app.dependency_overrides[db_module.get_db]
    session = next(override())
    try:
        u = session.query(models.User).filter_by(email=email).one()
        u.is_admin = True
        session.commit()
    finally:
        session.close()


def test_submit_feedback_happy_path(auth_client: TestClient):
    r = auth_client.post(
        "/feedback",
        json={"rating": 4, "comments": "Love the prominence scaling.", "bugs": ""},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["rating"] == 4
    assert body["comments"] == "Love the prominence scaling."
    # Empty-string `bugs` should round-trip as null (stripped on the server).
    assert body["bugs"] is None


def test_rating_required(auth_client: TestClient):
    r = auth_client.post("/feedback", json={"comments": "no rating"})
    assert r.status_code == 422


def test_rating_out_of_range_rejected(auth_client: TestClient):
    for bad in (0, 6, -1, 99):
        r = auth_client.post("/feedback", json={"rating": bad})
        assert r.status_code == 422, f"rating={bad} should be rejected"


def test_feedback_requires_login(client: TestClient):
    r = client.post("/feedback", json={"rating": 3})
    assert r.status_code == 401


def test_admin_can_list_all_feedback(auth_client, second_client):
    _make_admin(auth_client, "aryan@example.com")
    # Two users submit
    auth_client.post("/feedback", json={"rating": 5, "comments": "great"})
    second_client.post("/feedback", json={"rating": 2, "bugs": "x"})

    r = auth_client.get("/admin/feedback")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 2
    by_rating = {row["rating"]: row for row in rows}
    assert by_rating[5]["user_email"] == "aryan@example.com"
    assert by_rating[2]["user_email"] == "other@example.com"
    # No raw password_hash leaking into the admin view.
    assert all("password_hash" not in row for row in rows)


def test_non_admin_cannot_list_feedback(auth_client):
    auth_client.post("/feedback", json={"rating": 3})
    r = auth_client.get("/admin/feedback")
    assert r.status_code == 403


def test_user_cannot_see_others_feedback_via_admin_endpoint(
    auth_client, second_client
):
    """The /admin/feedback endpoint is admin-only, full stop. A regular
    user with a valid session must 403 even though there's feedback to read."""
    second_client.post("/feedback", json={"rating": 1, "bugs": "everything"})
    r = auth_client.get("/admin/feedback")
    assert r.status_code == 403


def test_bearer_can_submit_feedback(auth_client):
    """Bearer-auth (CLI/agent) path also works for capturing feedback."""
    tok = auth_client.post("/auth/tokens", json={"name": "cli"}).json()["token"]
    from app.main import app

    bare = TestClient(app)
    r = bare.post(
        "/feedback",
        json={"rating": 5, "comments": "from a script"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 201
    assert r.json()["rating"] == 5


def test_deleting_user_cascades_feedback(auth_client):
    """CASCADE on user delete — feedback rows go with the user."""
    auth_client.post("/feedback", json={"rating": 4})
    from app import database as db_module
    from app import models
    from app.main import app

    override = app.dependency_overrides[db_module.get_db]
    session = next(override())
    try:
        assert session.query(models.Feedback).count() == 1
        u = session.query(models.User).filter_by(email="aryan@example.com").one()
        session.delete(u)
        session.commit()
        assert session.query(models.Feedback).count() == 0
    finally:
        session.close()
