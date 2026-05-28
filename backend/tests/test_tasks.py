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


def test_estimate_minutes_round_trips(auth_client: TestClient):
    t = _create(auth_client, name="work", estimate_minutes=90)
    assert t["estimate_minutes"] == 90
    r = auth_client.patch(f"/tasks/{t['id']}", json={"estimate_minutes": 30})
    assert r.json()["estimate_minutes"] == 30
    r = auth_client.patch(f"/tasks/{t['id']}", json={"estimate_minutes": None})
    assert r.json()["estimate_minutes"] is None


def test_estimate_minutes_rejects_out_of_range(auth_client: TestClient):
    """Allowed range is 0–1440 (= one day) to catch obvious mistakes."""
    r = auth_client.post(
        "/tasks",
        json={"name": "x", "stack_date": "2026-06-01", "estimate_minutes": -1},
    )
    assert r.status_code == 422
    r = auth_client.post(
        "/tasks",
        json={"name": "x", "stack_date": "2026-06-01", "estimate_minutes": 2000},
    )
    assert r.status_code == 422


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


# ── done/cancelled → move-to-end behavior ──────────────────────────────────


def test_marking_top_task_done_moves_it_to_bottom(auth_client: TestClient):
    """The whole 'top = next thing to do' metaphor breaks if a done task
    keeps its prominent slot. Marking the #1 task done should slide it to
    the bottom and bubble the others up."""
    a = _create(auth_client, name="a")  # pos 0
    b = _create(auth_client, name="b")  # pos 1
    c = _create(auth_client, name="c")  # pos 2

    r = auth_client.patch(f"/tasks/{a['id']}", json={"status": "done"})
    assert r.status_code == 200

    stack = auth_client.get("/stacks/2026-06-01").json()
    order = [(t["name"], t["position"], t["status"]) for t in stack["tasks"]]
    assert order == [
        ("b", 0, "pending"),
        ("c", 1, "pending"),
        ("a", 2, "done"),
    ]


def test_marking_middle_task_done_compacts_positions(auth_client: TestClient):
    """Done from the middle should also slide to the bottom; the gap closes
    so positions stay dense from 0."""
    a = _create(auth_client, name="a")  # pos 0
    b = _create(auth_client, name="b")  # pos 1
    c = _create(auth_client, name="c")  # pos 2
    d = _create(auth_client, name="d")  # pos 3

    auth_client.patch(f"/tasks/{b['id']}", json={"status": "done"})

    stack = auth_client.get("/stacks/2026-06-01").json()
    order = [(t["name"], t["position"]) for t in stack["tasks"]]
    assert order == [("a", 0), ("c", 1), ("d", 2), ("b", 3)]


def test_marking_bottom_task_done_is_a_noop_for_position(auth_client: TestClient):
    """No shuffle needed if it's already at the bottom."""
    a = _create(auth_client, name="a")  # pos 0
    b = _create(auth_client, name="b")  # pos 1
    auth_client.patch(f"/tasks/{b['id']}", json={"status": "done"})
    stack = auth_client.get("/stacks/2026-06-01").json()
    assert [(t["name"], t["position"]) for t in stack["tasks"]] == [
        ("a", 0), ("b", 1),
    ]


def test_marking_done_again_is_idempotent_for_position(auth_client: TestClient):
    """A second PATCH status=done on an already-done task must NOT shuffle
    the stack — otherwise an agent that retries gets surprising reorders."""
    a = _create(auth_client, name="a")  # pos 0
    b = _create(auth_client, name="b")  # pos 1
    c = _create(auth_client, name="c")  # pos 2

    auth_client.patch(f"/tasks/{a['id']}", json={"status": "done"})
    # After first done: order is [b=0, c=1, a=2]
    auth_client.patch(f"/tasks/{a['id']}", json={"status": "done"})
    # Second call should be a no-op for ordering
    stack = auth_client.get("/stacks/2026-06-01").json()
    assert [(t["name"], t["position"]) for t in stack["tasks"]] == [
        ("b", 0), ("c", 1), ("a", 2),
    ]


def test_cancelling_also_moves_to_bottom(auth_client: TestClient):
    """Cancel is the same UX category as done — out of the active queue.
    Same move-to-bottom behavior."""
    a = _create(auth_client, name="a")
    b = _create(auth_client, name="b")
    c = _create(auth_client, name="c")

    auth_client.patch(f"/tasks/{a['id']}", json={"status": "cancelled"})

    stack = auth_client.get("/stacks/2026-06-01").json()
    assert [(t["name"], t["position"], t["status"]) for t in stack["tasks"]] == [
        ("b", 0, "pending"),
        ("c", 1, "pending"),
        ("a", 2, "cancelled"),
    ]


def test_reviving_done_task_keeps_bottom_position(auth_client: TestClient):
    """When you flip done back to pending, we don't try to restore the
    original position — we never stored it. It stays at the bottom; the
    user can drag it back up if they want."""
    a = _create(auth_client, name="a")  # pos 0
    b = _create(auth_client, name="b")  # pos 1
    c = _create(auth_client, name="c")  # pos 2

    auth_client.patch(f"/tasks/{a['id']}", json={"status": "done"})
    # a is now at the bottom (pos 2)
    auth_client.patch(f"/tasks/{a['id']}", json={"status": "pending"})

    stack = auth_client.get("/stacks/2026-06-01").json()
    order = [(t["name"], t["position"], t["status"]) for t in stack["tasks"]]
    assert order == [
        ("b", 0, "pending"),
        ("c", 1, "pending"),
        ("a", 2, "pending"),  # back to pending but stayed at bottom
    ]


# ── GET /tasks/completed — the cross-stack archive ──


def _mark_done(client: TestClient, task_id: int) -> dict:
    r = client.patch(f"/tasks/{task_id}", json={"status": "done"})
    assert r.status_code == 200, r.text
    return r.json()


def test_completed_lists_done_across_stacks(auth_client: TestClient):
    # A done task in a daily stack, a topic stack, and the backlog.
    _mark_done(auth_client, _create(auth_client, name="ship it")["id"])
    sid = auth_client.post(
        "/stacks/topics", json={"kind": "reading", "name": "Sci-Fi"}
    ).json()["id"]
    _mark_done(
        auth_client,
        auth_client.post("/tasks", json={"name": "Dune", "stack_id": sid}).json()["id"],
    )
    _mark_done(
        auth_client, auth_client.post("/tasks", json={"name": "someday"}).json()["id"]
    )

    r = auth_client.get("/tasks/completed")
    assert r.status_code == 200
    assert {t["name"] for t in r.json()} == {"ship it", "Dune", "someday"}


def test_completed_includes_stack_context(auth_client: TestClient):
    _mark_done(auth_client, _create(auth_client, name="ship it")["id"])  # daily 06-01
    sid = auth_client.post(
        "/stacks/topics", json={"kind": "reading", "name": "Sci-Fi"}
    ).json()["id"]
    _mark_done(
        auth_client,
        auth_client.post("/tasks", json={"name": "Dune", "stack_id": sid}).json()["id"],
    )
    _mark_done(
        auth_client, auth_client.post("/tasks", json={"name": "someday"}).json()["id"]
    )

    by_name = {t["name"]: t for t in auth_client.get("/tasks/completed").json()}

    # Daily stack: kind=daily, date set, no name.
    assert by_name["ship it"]["stack_kind"] == "daily"
    assert by_name["ship it"]["stack_date"] == "2026-06-01"
    assert by_name["ship it"]["stack_name"] is None

    # Topic stack: kind + name set, no date.
    assert by_name["Dune"]["stack_kind"] == "reading"
    assert by_name["Dune"]["stack_name"] == "Sci-Fi"
    assert by_name["Dune"]["stack_date"] is None

    # Backlog: no stack at all.
    assert by_name["someday"]["stack_id"] is None
    assert by_name["someday"]["stack_kind"] is None
    assert by_name["someday"]["stack_name"] is None
    assert by_name["someday"]["stack_date"] is None


def test_completed_excludes_non_done(auth_client: TestClient):
    _create(auth_client, name="pending one")
    ip = _create(auth_client, name="in progress")
    auth_client.post(f"/tasks/{ip['id']}/start")
    nope = _create(auth_client, name="nope")
    auth_client.patch(f"/tasks/{nope['id']}", json={"status": "cancelled"})
    _mark_done(auth_client, _create(auth_client, name="yes")["id"])

    assert [t["name"] for t in auth_client.get("/tasks/completed").json()] == ["yes"]


def test_completed_ordered_newest_first(auth_client: TestClient):
    _mark_done(auth_client, _create(auth_client, name="first")["id"])
    _mark_done(auth_client, _create(auth_client, name="second")["id"])
    # Most recently completed comes first.
    assert [t["name"] for t in auth_client.get("/tasks/completed").json()] == [
        "second",
        "first",
    ]


def test_completed_is_per_user(second_client: TestClient, auth_client: TestClient):
    _mark_done(auth_client, _create(auth_client, name="mine")["id"])
    # The other user's archive is empty — no leakage across tenants.
    assert second_client.get("/tasks/completed").json() == []
    theirs = second_client.post(
        "/tasks", json={"name": "theirs", "stack_date": "2026-06-02"}
    ).json()
    second_client.patch(f"/tasks/{theirs['id']}", json={"status": "done"})
    assert [t["name"] for t in second_client.get("/tasks/completed").json()] == [
        "theirs"
    ]

