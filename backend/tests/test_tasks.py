"""Task CRUD, priority hints, edit/clear semantics, status transitions, timer."""

from datetime import date

from fastapi.testclient import TestClient


def _create(client: TestClient, **kwargs) -> dict:
    body = {"name": "t", "stack_date": "2026-06-01", **kwargs}
    r = client.post("/tasks", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_create_appends_to_end_by_default(auth_client: TestClient):
    a = _create(auth_client, name="a")
    b = _create(auth_client, name="b")
    c = _create(auth_client, name="c")
    assert (a["position"], b["position"], c["position"]) == (0, 1, 2)


def test_priority_hint_top_shifts_others_down(auth_client: TestClient):
    _create(auth_client, name="a")  # pos 0
    _create(auth_client, name="b")  # pos 1
    top = _create(auth_client, name="boss says", priority_hint="top")
    assert top["position"] == 0
    stack = auth_client.get("/stacks/2026-06-01").json()
    titles = [t["name"] for t in stack["tasks"]]
    assert titles == ["boss says", "a", "b"]


def test_priority_hint_high_inserts_at_position_1(auth_client: TestClient):
    _create(auth_client, name="a")
    _create(auth_client, name="b")
    high = _create(auth_client, name="urgent", priority_hint="high")
    assert high["position"] == 1


def test_patch_clears_context_md_when_sent_null(auth_client: TestClient):
    t = _create(auth_client, name="t", context_md="---\nname: t\n---\nbody")
    r = auth_client.patch(f"/tasks/{t['id']}", json={"context_md": None})
    assert r.json()["context_md"] is None


def test_patch_omits_context_md_preserves_existing(auth_client: TestClient):
    t = _create(auth_client, name="t", context_md="keep me")
    # Send title only; context_md must be untouched.
    r = auth_client.patch(f"/tasks/{t['id']}", json={"name": "renamed"})
    body = r.json()
    assert body["name"] == "renamed"
    assert body["context_md"] == "keep me"


def test_direct_link_round_trips(auth_client: TestClient):
    t = _create(auth_client, name="paper", direct_link="https://arxiv.org/abs/1234")
    assert t["direct_link"] == "https://arxiv.org/abs/1234"
    r = auth_client.patch(f"/tasks/{t['id']}", json={"direct_link": None})
    assert r.json()["direct_link"] is None


def test_direct_link_rejects_javascript_url(auth_client: TestClient):
    """XSS guard: javascript:/data:/file: URLs must not survive the API."""
    r = auth_client.post(
        "/tasks",
        json={
            "name": "evil",
            "stack_date": "2026-06-01",
            "direct_link": "javascript:alert(1)",
        },
    )
    assert r.status_code == 422

    # Same guard on PATCH
    t = _create(auth_client, name="paper")
    r = auth_client.patch(
        f"/tasks/{t['id']}",
        json={"direct_link": "javascript:alert(1)"},
    )
    assert r.status_code == 422


def test_direct_link_rejects_other_schemes(auth_client: TestClient):
    for bad in ("data:text/html,<script>1</script>", "file:///etc/passwd", "ftp://x"):
        r = auth_client.post(
            "/tasks",
            json={"name": "t", "stack_date": "2026-06-01", "direct_link": bad},
        )
        assert r.status_code == 422, f"{bad} should be rejected"


def test_direct_link_blank_becomes_null(auth_client: TestClient):
    """An empty/whitespace string clears rather than fails validation."""
    t = _create(auth_client, name="paper", direct_link="   ")
    assert t["direct_link"] is None


def test_patch_due_at_null_clears(auth_client: TestClient):
    t = _create(auth_client, name="t", due_at="2026-12-31T23:59:00")
    r = auth_client.patch(f"/tasks/{t['id']}", json={"due_at": None})
    assert r.json()["due_at"] is None


def test_delete_task_removes_and_compacts_positions(auth_client: TestClient):
    a = _create(auth_client, name="a")
    b = _create(auth_client, name="b")
    c = _create(auth_client, name="c")
    r = auth_client.delete(f"/tasks/{b['id']}")
    assert r.status_code == 204
    assert auth_client.get(f"/tasks/{b['id']}").status_code == 404
    stack = auth_client.get("/stacks/2026-06-01").json()
    titles_positions = [(t["name"], t["position"]) for t in stack["tasks"]]
    assert titles_positions == [("a", 0), ("c", 1)]


def test_status_done_sets_completed_at(auth_client: TestClient):
    t = _create(auth_client, name="t")
    r = auth_client.patch(f"/tasks/{t['id']}", json={"status": "done"})
    body = r.json()
    assert body["status"] == "done"
    assert body["completed_at"] is not None


def test_status_back_to_pending_clears_completed_at(auth_client: TestClient):
    t = _create(auth_client, name="t")
    auth_client.patch(f"/tasks/{t['id']}", json={"status": "done"})
    r = auth_client.patch(f"/tasks/{t['id']}", json={"status": "pending"})
    assert r.json()["completed_at"] is None


def test_start_then_pause_accumulates_seconds(auth_client: TestClient):
    import time

    t = _create(auth_client, name="work")
    assert auth_client.post(f"/tasks/{t['id']}/start").json()["status"] == "in_progress"
    time.sleep(1.1)
    r = auth_client.post(f"/tasks/{t['id']}/pause").json()
    assert r["status"] == "pending"
    assert r["accumulated_seconds"] >= 1
    assert r["in_progress_started_at"] is None


def test_done_while_running_commits_elapsed_time(auth_client: TestClient):
    import time

    t = _create(auth_client, name="work")
    auth_client.post(f"/tasks/{t['id']}/start")
    time.sleep(1.1)
    r = auth_client.patch(f"/tasks/{t['id']}", json={"status": "done"})
    body = r.json()
    assert body["status"] == "done"
    assert body["accumulated_seconds"] >= 1
    assert body["completed_at"] is not None
    assert body["in_progress_started_at"] is None


def test_move_task_to_different_date_changes_stack(auth_client: TestClient):
    t = _create(auth_client, name="t")
    r = auth_client.post(
        f"/tasks/{t['id']}/move", json={"stack_date": "2026-06-02"}
    )
    assert r.status_code == 200
    src = auth_client.get("/stacks/2026-06-01").json()
    dst = auth_client.get("/stacks/2026-06-02").json()
    assert [x["id"] for x in src["tasks"]] == []
    assert [x["id"] for x in dst["tasks"]] == [t["id"]]


def test_move_to_null_stack_does_NOT_delete_the_task(auth_client: TestClient):
    """Regression: cascade='all, delete-orphan' on Stack.tasks used to wipe
    the task when stack_id became None. The current cascade must not."""
    t = _create(auth_client, name="t")
    r = auth_client.post(f"/tasks/{t['id']}/move", json={"stack_date": None})
    assert r.status_code == 200
    assert r.json()["stack_id"] is None
    # Task still exists
    assert auth_client.get(f"/tasks/{t['id']}").status_code == 200


def test_reorder_requires_exact_set_of_stack_tasks(auth_client: TestClient):
    a = _create(auth_client, name="a")
    b = _create(auth_client, name="b")
    # Partial set → 400
    r = auth_client.post(
        "/tasks/reorder",
        json={"stack_date": "2026-06-01", "ordered_ids": [a["id"]]},
    )
    assert r.status_code == 400
    # Foreign id → 400
    r = auth_client.post(
        "/tasks/reorder",
        json={"stack_date": "2026-06-01", "ordered_ids": [a["id"], b["id"], 99999]},
    )
    assert r.status_code == 400
    # Exact set → 200 and applied
    r = auth_client.post(
        "/tasks/reorder",
        json={"stack_date": "2026-06-01", "ordered_ids": [b["id"], a["id"]]},
    )
    assert r.status_code == 200
    stack = auth_client.get("/stacks/2026-06-01").json()
    assert [t["id"] for t in stack["tasks"]] == [b["id"], a["id"]]
