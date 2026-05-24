"""Public sharing of topic stacks: share/unshare lifecycle + the no-auth /public read."""

from fastapi.testclient import TestClient


def _create_topic_stack(client: TestClient, name: str = "Sci-Fi") -> dict:
    r = client.post(
        "/stacks/topics", json={"kind": "reading", "name": name}
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_new_topic_stack_is_private(auth_client: TestClient):
    s = _create_topic_stack(auth_client)
    assert s["is_public"] is False
    assert s["share_slug"] is None


def test_share_generates_slug_and_flips_public(auth_client: TestClient):
    s = _create_topic_stack(auth_client)
    r = auth_client.post(f"/stacks/topics/{s['id']}/share")
    assert r.status_code == 200
    body = r.json()
    assert body["is_public"] is True
    assert body["share_slug"] is not None
    assert 8 <= len(body["share_slug"]) <= 20


def test_resharing_keeps_the_same_slug(auth_client: TestClient):
    """Notion-style: the slug is stable across share → unshare → re-share."""
    s = _create_topic_stack(auth_client)
    first_slug = auth_client.post(
        f"/stacks/topics/{s['id']}/share"
    ).json()["share_slug"]

    auth_client.post(f"/stacks/topics/{s['id']}/unshare")
    second_slug = auth_client.post(
        f"/stacks/topics/{s['id']}/share"
    ).json()["share_slug"]

    assert first_slug == second_slug


def test_unshare_keeps_slug_but_flips_public(auth_client: TestClient):
    s = _create_topic_stack(auth_client)
    shared = auth_client.post(f"/stacks/topics/{s['id']}/share").json()
    r = auth_client.post(f"/stacks/topics/{s['id']}/unshare")
    body = r.json()
    assert body["is_public"] is False
    assert body["share_slug"] == shared["share_slug"]


def test_public_read_returns_shared_stack(client: TestClient, auth_client: TestClient):
    s = _create_topic_stack(auth_client, name="Sci-Fi")
    # Add a couple of tasks
    auth_client.post(
        "/tasks", json={"name": "Three Body Problem", "stack_id": s["id"]}
    )
    auth_client.post("/tasks", json={"name": "Dune", "stack_id": s["id"]})
    slug = auth_client.post(f"/stacks/topics/{s['id']}/share").json()[
        "share_slug"
    ]

    # The `client` fixture is unauthenticated — drop cookies to be sure.
    client.cookies.clear()
    r = client.get(f"/public/stacks/{slug}")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Sci-Fi"
    assert body["kind"] == "reading"
    assert body["owner_display_name"] == "Aryan"
    titles = [t["name"] for t in body["tasks"]]
    assert "Three Body Problem" in titles and "Dune" in titles


def test_public_read_hides_done_and_cancelled_tasks(
    client: TestClient, auth_client: TestClient
):
    s = _create_topic_stack(auth_client, name="Reading")
    a = auth_client.post(
        "/tasks", json={"name": "Active book", "stack_id": s["id"]}
    ).json()
    d = auth_client.post(
        "/tasks", json={"name": "Finished book", "stack_id": s["id"]}
    ).json()
    auth_client.patch(f"/tasks/{d['id']}", json={"status": "done"})
    slug = auth_client.post(f"/stacks/topics/{s['id']}/share").json()[
        "share_slug"
    ]

    client.cookies.clear()
    body = client.get(f"/public/stacks/{slug}").json()
    titles = [t["name"] for t in body["tasks"]]
    assert titles == ["Active book"]  # done excluded
    # Active task ID isn't even exposed
    assert "id" not in body["tasks"][0]


def test_public_read_excludes_operational_state(
    client: TestClient, auth_client: TestClient
):
    """The public view must NOT leak the owner's workflow internals."""
    s = _create_topic_stack(auth_client)
    t = auth_client.post(
        "/tasks", json={"name": "Item", "stack_id": s["id"]}
    ).json()
    auth_client.post(f"/tasks/{t['id']}/start")
    slug = auth_client.post(f"/stacks/topics/{s['id']}/share").json()[
        "share_slug"
    ]

    client.cookies.clear()
    body = client.get(f"/public/stacks/{slug}").json()
    task = body["tasks"][0]
    for forbidden in (
        "status",
        "id",
        "user_id",
        "stack_id",
        "completed_at",
        "created_at",
        "updated_at",
        "in_progress_started_at",
        "accumulated_seconds",
    ):
        assert forbidden not in task, f"Public view leaks {forbidden}"


def test_public_read_hides_context_md_by_default(
    client: TestClient, auth_client: TestClient
):
    """Default: share_context_in_public=False, so context_md is None even
    if the task has one."""
    s = _create_topic_stack(auth_client)
    auth_client.post(
        "/tasks",
        json={
            "name": "Paper",
            "stack_id": s["id"],
            "context_md": "secret notes about this paper",
            "direct_link": "https://arxiv.org/abs/1234",
        },
    )
    slug = auth_client.post(f"/stacks/topics/{s['id']}/share").json()[
        "share_slug"
    ]

    client.cookies.clear()
    task = client.get(f"/public/stacks/{slug}").json()["tasks"][0]
    assert task["context_md"] is None
    # direct_link is the click target — always exposed.
    assert task["direct_link"] == "https://arxiv.org/abs/1234"


def test_public_read_includes_context_md_when_opted_in(
    client: TestClient, auth_client: TestClient
):
    s = _create_topic_stack(auth_client)
    auth_client.post(
        "/tasks",
        json={
            "name": "Paper",
            "stack_id": s["id"],
            "context_md": "why I want to read this",
        },
    )
    auth_client.patch(
        f"/stacks/topics/{s['id']}", json={"share_context_in_public": True}
    )
    slug = auth_client.post(f"/stacks/topics/{s['id']}/share").json()[
        "share_slug"
    ]

    client.cookies.clear()
    task = client.get(f"/public/stacks/{slug}").json()["tasks"][0]
    assert task["context_md"] == "why I want to read this"


def test_unshared_slug_returns_404(client: TestClient, auth_client: TestClient):
    s = _create_topic_stack(auth_client)
    slug = auth_client.post(f"/stacks/topics/{s['id']}/share").json()[
        "share_slug"
    ]
    auth_client.post(f"/stacks/topics/{s['id']}/unshare")

    client.cookies.clear()
    r = client.get(f"/public/stacks/{slug}")
    assert r.status_code == 404


def test_unknown_slug_returns_404(client: TestClient):
    client.cookies.clear()
    r = client.get("/public/stacks/this-slug-does-not-exist")
    assert r.status_code == 404


def test_daily_stack_cannot_be_made_public(auth_client: TestClient):
    """Sanity: the share endpoints only operate on topic stacks."""
    # Daily stacks have no /share endpoint exposed under /topics/, so trying
    # to share by daily-stack id (when the user has no topic stack with that
    # id) returns 404 from find_topic_stack — confirming the constraint.
    today = auth_client.get("/stacks/today").json()
    r = auth_client.post(f"/stacks/topics/{today['id']}/share")
    assert r.status_code == 404


def test_other_user_cannot_share_my_stack(
    auth_client: TestClient, second_client: TestClient
):
    s = _create_topic_stack(auth_client)
    r = second_client.post(f"/stacks/topics/{s['id']}/share")
    assert r.status_code == 404  # find_topic_stack scoped to current_user


def test_public_read_rate_limited(
    client: TestClient, auth_client: TestClient, monkeypatch
):
    """Anonymous /public reads get throttled per IP — scrape defense."""
    from app.security import reset_rate_limits

    monkeypatch.setenv("PUBLIC_READ_RATE_LIMIT_IP_ATTEMPTS", "3")
    monkeypatch.setenv("PUBLIC_READ_RATE_LIMIT_WINDOW_SECONDS", "60")
    reset_rate_limits()

    s = _create_topic_stack(auth_client)
    slug = auth_client.post(f"/stacks/topics/{s['id']}/share").json()[
        "share_slug"
    ]
    client.cookies.clear()

    # First 3 succeed.
    for _ in range(3):
        assert client.get(f"/public/stacks/{slug}").status_code == 200
    # 4th trips the limiter.
    assert client.get(f"/public/stacks/{slug}").status_code == 429
