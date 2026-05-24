"""User A must never see user B's data — across every read path."""

from fastapi.testclient import TestClient


def test_users_have_independent_daily_stacks(
    auth_client: TestClient, second_client: TestClient
):
    auth_client.post(
        "/tasks", json={"name": "aryan's task", "stack_date": "2026-06-01"}
    )
    second_client.post(
        "/tasks", json={"name": "other's task", "stack_date": "2026-06-01"}
    )
    a = auth_client.get("/stacks/2026-06-01").json()
    b = second_client.get("/stacks/2026-06-01").json()
    assert [t["name"] for t in a["tasks"]] == ["aryan's task"]
    assert [t["name"] for t in b["tasks"]] == ["other's task"]


def test_users_have_independent_topic_stacks(
    auth_client: TestClient, second_client: TestClient
):
    auth_client.post(
        "/stacks/topics", json={"kind": "reading", "name": "Aryan reads"}
    )
    second_client.post(
        "/stacks/topics", json={"kind": "reading", "name": "Other reads"}
    )
    a_names = {s["name"] for s in auth_client.get("/stacks/topics").json()}
    b_names = {s["name"] for s in second_client.get("/stacks/topics").json()}
    assert "Aryan reads" in a_names and "Other reads" not in a_names
    assert "Other reads" in b_names and "Aryan reads" not in b_names


def test_user_cannot_read_other_users_topic_stack_by_id(
    auth_client: TestClient, second_client: TestClient
):
    sid = auth_client.post(
        "/stacks/topics", json={"kind": "reading", "name": "Sci-Fi"}
    ).json()["id"]
    r = second_client.get(f"/stacks/topics/{sid}")
    assert r.status_code == 404  # not 403 — don't leak existence


def test_user_cannot_modify_other_users_task(
    auth_client: TestClient, second_client: TestClient
):
    t = auth_client.post(
        "/tasks", json={"name": "private", "stack_date": "2026-06-01"}
    ).json()
    # Other user trying to mutate by ID — all should 404
    assert second_client.get(f"/tasks/{t['id']}").status_code == 404
    assert (
        second_client.patch(f"/tasks/{t['id']}", json={"name": "hijack"}).status_code
        == 404
    )
    assert second_client.delete(f"/tasks/{t['id']}").status_code == 404
    assert (
        second_client.post(
            f"/tasks/{t['id']}/move", json={"stack_date": "2026-06-02"}
        ).status_code
        == 404
    )
    # Task is untouched
    again = auth_client.get(f"/tasks/{t['id']}").json()
    assert again["name"] == "private"


def test_user_cannot_inject_foreign_task_into_their_reorder(
    auth_client: TestClient, second_client: TestClient
):
    foreign = auth_client.post(
        "/tasks", json={"name": "aryan", "stack_date": "2026-06-01"}
    ).json()
    mine = second_client.post(
        "/tasks", json={"name": "mine", "stack_date": "2026-06-01"}
    ).json()
    # Other tries to reorder including aryan's task id → 400 (exhaustive check)
    r = second_client.post(
        "/tasks/reorder",
        json={"stack_date": "2026-06-01", "ordered_ids": [mine["id"], foreign["id"]]},
    )
    assert r.status_code == 400  # foreign id appears as "extra"
    # Aryan's task untouched
    assert auth_client.get(f"/tasks/{foreign['id']}").json()["name"] == "aryan"


def test_overdue_only_returns_own_tasks(
    auth_client: TestClient, second_client: TestClient
):
    long_ago = "2026-01-01"
    auth_client.post("/tasks", json={"name": "aryan-old", "stack_date": long_ago})
    second_client.post("/tasks", json={"name": "other-old", "stack_date": long_ago})
    a = auth_client.get("/stacks/overdue?today=2026-12-31").json()
    b = second_client.get("/stacks/overdue?today=2026-12-31").json()
    assert [t["name"] for t in a] == ["aryan-old"]
    assert [t["name"] for t in b] == ["other-old"]
