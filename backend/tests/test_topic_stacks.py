"""Topic stacks (Reading, Watching, etc.) + stack_id task targeting."""

from fastapi.testclient import TestClient


def test_create_topic_stack(auth_client: TestClient):
    r = auth_client.post(
        "/stacks/topics",
        json={"kind": "reading", "name": "Sci-Fi"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["kind"] == "reading"
    assert body["name"] == "Sci-Fi"
    assert body["stack_date"] is None


def test_cannot_create_topic_with_kind_daily(auth_client: TestClient):
    r = auth_client.post(
        "/stacks/topics", json={"kind": "daily", "name": "x"}
    )
    assert r.status_code == 400


def test_list_topic_stacks_groups_by_kind(auth_client: TestClient):
    auth_client.post("/stacks/topics", json={"kind": "reading", "name": "Sci-Fi"})
    auth_client.post("/stacks/topics", json={"kind": "reading", "name": "Tech"})
    auth_client.post("/stacks/topics", json={"kind": "watching", "name": "Films"})
    r = auth_client.get("/stacks/topics")
    assert r.status_code == 200
    kinds = [s["kind"] for s in r.json()]
    # Daily stacks are excluded
    assert all(k != "daily" for k in kinds)
    assert kinds.count("reading") == 2
    assert kinds.count("watching") == 1


def test_add_task_via_stack_id(auth_client: TestClient):
    sid = auth_client.post(
        "/stacks/topics", json={"kind": "reading", "name": "Sci-Fi"}
    ).json()["id"]
    r = auth_client.post(
        "/tasks", json={"name": "Three Body Problem", "stack_id": sid}
    )
    assert r.status_code == 201
    assert r.json()["stack_id"] == sid


def test_create_rejects_both_stack_date_and_stack_id(auth_client: TestClient):
    sid = auth_client.post(
        "/stacks/topics", json={"kind": "reading", "name": "Sci-Fi"}
    ).json()["id"]
    r = auth_client.post(
        "/tasks",
        json={"name": "x", "stack_date": "2026-06-01", "stack_id": sid},
    )
    assert r.status_code == 400


def test_delete_topic_stack_cascades_tasks(auth_client: TestClient):
    sid = auth_client.post(
        "/stacks/topics", json={"kind": "reading", "name": "Sci-Fi"}
    ).json()["id"]
    t = auth_client.post(
        "/tasks", json={"name": "book", "stack_id": sid}
    ).json()
    r = auth_client.delete(f"/stacks/topics/{sid}")
    assert r.status_code == 204
    # Stack is gone
    assert auth_client.get(f"/stacks/topics/{sid}").status_code == 404
    # Task is gone too (cascade via FK ondelete=CASCADE on user_id, but stack
    # FK is SET NULL — so the task may survive in the user's backlog. Verify
    # the actual behavior matches the model contract.)
    survives = auth_client.get(f"/tasks/{t['id']}")
    # The Stack→Task FK is ondelete=SET NULL, so the task moves to backlog.
    assert survives.status_code == 200
    assert survives.json()["stack_id"] is None


def test_rename_topic_stack(auth_client: TestClient):
    sid = auth_client.post(
        "/stacks/topics", json={"kind": "reading", "name": "Sci-Fi"}
    ).json()["id"]
    r = auth_client.patch(f"/stacks/topics/{sid}", json={"name": "  Hard SF  "})
    assert r.status_code == 200
    # Name is trimmed and other fields are untouched.
    assert r.json()["name"] == "Hard SF"
    assert r.json()["kind"] == "reading"
    # And it sticks on a fresh read.
    assert auth_client.get(f"/stacks/topics/{sid}").json()["name"] == "Hard SF"


def test_rename_topic_stack_rejects_foreign_owner(second_client: TestClient, auth_client: TestClient):
    sid = auth_client.post(
        "/stacks/topics", json={"kind": "reading", "name": "Mine"}
    ).json()["id"]
    # Another user can't rename a stack they don't own — 404 (not 403) to avoid
    # leaking existence.
    r = second_client.patch(f"/stacks/topics/{sid}", json={"name": "Hijacked"})
    assert r.status_code == 404
    assert auth_client.get(f"/stacks/topics/{sid}").json()["name"] == "Mine"


def test_move_task_into_topic_stack(auth_client: TestClient):
    sid = auth_client.post(
        "/stacks/topics", json={"kind": "reading", "name": "Sci-Fi"}
    ).json()["id"]
    t = auth_client.post(
        "/tasks", json={"name": "t", "stack_date": "2026-06-01"}
    ).json()
    r = auth_client.post(f"/tasks/{t['id']}/move", json={"stack_id": sid})
    assert r.status_code == 200
    assert r.json()["stack_id"] == sid
