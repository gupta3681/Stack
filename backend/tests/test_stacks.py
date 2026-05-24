"""Daily stacks: get/create-on-write semantics, intention, overdue."""

from datetime import date, timedelta  # noqa: F401

from fastapi.testclient import TestClient


def test_get_unknown_date_returns_synthetic_empty(auth_client: TestClient):
    r = auth_client.get("/stacks/2099-12-31")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] is None  # not persisted
    assert body["stack_date"] == "2099-12-31"
    assert body["tasks"] == []


def test_get_stack_does_not_write_a_row(auth_client: TestClient):
    """Regression: GETs used to silently INSERT, allowing table flood."""
    for d in ("2099-01-01", "2099-01-02", "2099-01-03"):
        auth_client.get(f"/stacks/{d}")
    # If GETs created rows, /stacks/topics or any list query would see them.
    # We can't list daily stacks directly; instead confirm no row exists by
    # checking the synthetic id stays None on the most-recently-fetched date.
    body = auth_client.get("/stacks/2099-01-01").json()
    assert body["id"] is None


def test_creating_a_task_for_a_date_persists_the_stack(auth_client: TestClient):
    auth_client.post(
        "/tasks", json={"title": "first", "stack_date": "2026-06-01"}
    )
    body = auth_client.get("/stacks/2026-06-01").json()
    assert body["id"] is not None
    assert len(body["tasks"]) == 1
    assert body["tasks"][0]["title"] == "first"


def test_patch_intention_creates_the_stack(auth_client: TestClient):
    r = auth_client.patch(
        "/stacks/2026-06-01", json={"intention": "ship the thing"}
    )
    assert r.status_code == 200
    assert r.json()["intention"] == "ship the thing"


def test_patch_intention_with_null_clears_it(auth_client: TestClient):
    auth_client.patch("/stacks/2026-06-01", json={"intention": "ship"})
    r = auth_client.patch("/stacks/2026-06-01", json={"intention": None})
    assert r.json()["intention"] is None


def test_today_endpoint_auto_creates(auth_client: TestClient):
    r = auth_client.get("/stacks/today")
    assert r.status_code == 200
    assert r.json()["id"] is not None  # /today always persists
    assert r.json()["stack_date"] == date.today().isoformat()


def test_overdue_respects_client_today_param(auth_client: TestClient):
    """Overdue cutoff must respect the client's local 'today', not the server's."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    long_ago = "2026-01-01"
    auth_client.post("/tasks", json={"title": "old task", "stack_date": long_ago})
    # Cutoff before the task's stack_date: not yet overdue
    r = auth_client.get(f"/stacks/overdue?today={long_ago}")
    assert r.status_code == 200
    assert len(r.json()) == 0
    # Cutoff after: now overdue
    r = auth_client.get(f"/stacks/overdue?today={yesterday}")
    if long_ago < yesterday:
        assert len(r.json()) == 1
        assert r.json()[0]["title"] == "old task"


def test_counts_today_tomorrow_topic_stacks(auth_client: TestClient):
    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    # 2 today (1 pending, 1 done — done should be excluded)
    auth_client.post("/tasks", json={"title": "a", "stack_date": today})
    t = auth_client.post(
        "/tasks", json={"title": "b", "stack_date": today}
    ).json()
    auth_client.patch(f"/tasks/{t['id']}", json={"status": "done"})
    # 3 tomorrow
    for title in ("x", "y", "z"):
        auth_client.post("/tasks", json={"title": title, "stack_date": tomorrow})
    # 2 topic stacks
    auth_client.post(
        "/stacks/topics", json={"kind": "reading", "name": "Sci-Fi"}
    )
    auth_client.post(
        "/stacks/topics", json={"kind": "watching", "name": "Films"}
    )

    r = auth_client.get(f"/stacks/counts?today={today}")
    assert r.status_code == 200
    body = r.json()
    assert body == {"today": 1, "tomorrow": 3, "topic_stacks": 2}


def test_counts_respects_user_scope(
    auth_client: TestClient, second_client: TestClient
):
    today = date.today().isoformat()
    auth_client.post("/tasks", json={"title": "mine", "stack_date": today})
    second_client.post("/tasks", json={"title": "theirs", "stack_date": today})
    second_client.post("/tasks", json={"title": "theirs2", "stack_date": today})
    assert (
        auth_client.get(f"/stacks/counts?today={today}").json()["today"] == 1
    )
    assert (
        second_client.get(f"/stacks/counts?today={today}").json()["today"] == 2
    )


def test_overdue_excludes_done_tasks(auth_client: TestClient):
    long_ago = "2026-01-01"
    t = auth_client.post(
        "/tasks", json={"title": "done already", "stack_date": long_ago}
    ).json()
    auth_client.patch(f"/tasks/{t['id']}", json={"status": "done"})
    today = date.today().isoformat()
    r = auth_client.get(f"/stacks/overdue?today={today}")
    assert len(r.json()) == 0


def test_overdue_excludes_cancelled_tasks(auth_client: TestClient):
    """Dismissing an overdue item from the UI sets status=cancelled.
    Cancelled tasks must drop out of the overdue feed."""
    long_ago = "2026-01-01"
    t = auth_client.post(
        "/tasks", json={"title": "not gonna happen", "stack_date": long_ago}
    ).json()
    auth_client.patch(f"/tasks/{t['id']}", json={"status": "cancelled"})
    today = date.today().isoformat()
    r = auth_client.get(f"/stacks/overdue?today={today}")
    assert len(r.json()) == 0
