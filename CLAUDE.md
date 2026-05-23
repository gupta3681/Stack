# Stack

> A productivity app organized around the metaphor of a **priority stack** — the thing on top is what you're doing next, and the stack is reorganized as the world changes.

---

## ⚠️ Keep this file current

**This file is the source of truth for project context.** Future Claude sessions (and humans skim-reading the repo) start here. When you change anything in the list below, update the relevant section of this file *in the same change*:

- Data model (new table, new column, changed nullability/constraints)
- Architecture (new service, new framework, swapped dependency)
- Auth, permissions, or multi-tenant rules
- Design system (new color, typography rule, component)
- Build / deploy shape (Docker compose changes, new env var, port change)
- Top-level UX (new page, new nav entry, new modal)
- Conventions or non-obvious patterns (anything that took you >15 min to debug)

Treat drift here the same as a broken test: don't ship without fixing it. If a section gets long enough to be unwieldy, split it into a sibling doc and link from here — don't let CLAUDE.md outgrow its job as a fast onboarding read.

---

## Vision

Most to-do apps are flat lists. They don't capture the truth that **priority is a stack, not a list**: there's one thing on top, the rest are queued, and the order changes as context shifts.

Stack's core moves:
- **Daily stacks** — one per day. What you're committing to today. Forcing function for prioritization.
- **Topic stacks** — evergreen, by theme: Reading, Watching, Buy, Ideas, etc. Long-lived backlogs you pull from.
- **Priority hints** at capture time (top / high / normal / low) so adding things is fast.
- **Drag to reorder, click to edit.** Top of the stack visually dominant; lower items shrink.

### Where this is going

- **Shareable stacks** (planned). A topic stack like "Sci-Fi reading" should be publishable read-only. Social discovery: "what's on Alice's reading stack?"
- **AI stack agent** (planned). Looks at your stacks plus context you drop in ("the deadline moved up", "I have 2 hours free") and proposes a re-stacking with explanations. The shape of `task_events` (priority history) and `context_drops` will support this — neither is implemented yet.

---

## Current state — what's built

- ✅ Multi-user with email+password auth, server-side sessions, HTTP-only cookies
- ✅ Daily stacks (Today, Tomorrow) with drag-reorder, prominence scaling, intention line, overdue surfacing
- ✅ Topic stacks (7 kinds: `daily`, `todo`, `reading`, `watching`, `listening`, `buy`, `ideas`)
- ✅ Per-task: title, description, due date, priority hint, status (pending / in_progress / done / cancelled), live timer for in-progress
- ✅ Move tasks between stacks (e.g. pull from a topic stack into Today)
- ✅ Quick-capture with priority hints
- ✅ Edit modal (title, description, due date, priority hint)
- ✅ Dev: SQLite + native `./dev.sh`, OR Postgres + Docker compose
- ✅ Prod overlay (`docker-compose.prod.yml`): nginx in front, backend/db isolated inside the network

## What's deliberately NOT built (yet)

- Sharing / public stacks / social
- AI stack agent
- Push notifications / reminders
- Mobile app (the responsive web isn't great yet)
- Real migrations (we use idempotent ALTER TABLE on startup; should adopt Alembic before the next big schema change)
- Search across stacks
- Tags / arbitrary cross-cutting categories

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  Browser                                             │
│   • React (Vite + TypeScript)                        │
│   • TanStack Query for server state                  │
│   • @dnd-kit for drag-and-drop                       │
└────────────────────┬─────────────────────────────────┘
                     │ HTTP (cookies for session)
                     ▼
┌──────────────────────────────────────────────────────┐
│  FastAPI (Python 3.12)                               │
│   • SQLAlchemy 2 ORM                                 │
│   • bcrypt password hashing (with SHA-256 prehash)   │
│   • Per-request user filtering on every endpoint     │
└────────────────────┬─────────────────────────────────┘
                     │ SQL
                     ▼
┌──────────────────────────────────────────────────────┐
│  Postgres 16 (or local SQLite for `./dev.sh`)        │
└──────────────────────────────────────────────────────┘
```

We don't have a separate service layer or message bus. FastAPI routers call SQLAlchemy directly. Business logic that doesn't fit cleanly in a router lives in [auth.py](backend/app/auth.py) — add a `services/` folder when complexity warrants, not before.

---

## Data model

```
┌────────────────────────────┐
│ users                      │
├────────────────────────────┤
│ id            PK           │
│ email         UNIQUE       │
│ password_hash              │
│ display_name  NULL         │
│ created_at                 │
└──────┬─────────────────────┘
       │ 1
       │
       ├──── N ────► sessions  (id PK = random token, user_id, expires_at)
       │
       ├──── N ────► stacks    (id, user_id, kind, stack_date NULL, name NULL,
       │                        intention NULL)
       │                       UNIQUE (user_id, stack_date)
       │
       └──── N ────► tasks     (id, user_id, stack_id NULL, title, description,
                                position, status, priority_hint, due_at,
                                in_progress_started_at, accumulated_seconds,
                                completed_at, created_at, updated_at)
```

Key shape rules:
- **`Stack.kind`** discriminator: `daily` (date-bound, name=null) vs topic kinds (date=null, name set).
- **`Stack.stack_date`** is nullable. Daily stacks have a date; topic stacks don't.
- **`Task.user_id`** is denormalized (also reachable via `task.stack.user_id`) — backlog tasks have `stack_id=NULL` so they need it directly, and it's a safety belt.
- **`Task.position`** is per-stack, 0 = top.
- **`Task.in_progress_started_at` + `accumulated_seconds`** = live timer. The frontend ticks every second; the backend commits elapsed time on pause/done. Never stores live time.
- **Cascade**: deleting a user cascades to sessions/stacks/tasks. SQLite needs `PRAGMA foreign_keys = ON` (enabled in [database.py](backend/app/database.py)) for this to actually fire.

### NOT in the model (yet)

- `task_events` — audit log for reorderings. Designed but not built; needed before the AI agent can explain why it moves things.
- `context_drops`, `reprioritization_proposals` — AI flow. Designed in early planning, deferred.
- `is_public`, `share_slug` on stacks — for sharing. Not yet.

---

## Auth

- **Email + password.** bcrypt with SHA-256 prehash so passwords of any length work without bcrypt's 72-byte limit biting ([auth.py](backend/app/auth.py)).
- **Server-side sessions.** Random 32-byte URL-safe token stored as the cookie value and as a row in `sessions`. 30-day TTL. Revocable.
- **`HttpOnly` cookie, `SameSite=Lax`, `path=/`.** `Secure` flag controlled by `COOKIE_SECURE` env var — flip to `true` when serving over HTTPS.
- **Every endpoint** that touches user data uses `Depends(get_current_user)`. Stack/task queries filter by `current_user.id`. Direct task lookups go through `_get_owned_task` which returns 404 (not 403) for foreign tasks to avoid leaking existence.

No CSRF tokens yet — `SameSite=Lax` blocks cross-site form POSTs which is enough for local dev. Add CSRF if/when this goes public.

No rate limiting yet. When deploying, drop in [`slowapi`](https://github.com/laurentS/slowapi) or rely on Cloudflare's free WAF at the edge.

---

## Project structure

```
Stack/
├── CLAUDE.md                ← you are here
├── design.md                ← Mono design system reference
├── docker-compose.yml       ← dev: db + backend (Postgres) + frontend (Vite)
├── docker-compose.prod.yml  ← prod overlay: nginx in front, internal-only services
├── dev.sh                   ← native dev (SQLite + uvicorn + Vite, no Docker)
├── .env                     ← local secrets, gitignored
├── .env.example             ← template
│
├── backend/
│   ├── Dockerfile           ← prod-style image (no --reload)
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py          ← FastAPI app, CORS, migrations
│   │   ├── database.py      ← engine + session factory (DATABASE_URL aware)
│   │   ├── models.py        ← SQLAlchemy: User, Session, Stack, Task
│   │   ├── schemas.py       ← Pydantic request/response models
│   │   ├── auth.py          ← password hashing, session mgmt, get_current_user
│   │   └── routers/
│   │       ├── auth.py      ← /auth/{signup,login,logout,me}
│   │       ├── stacks.py    ← /stacks/{today,tomorrow,overdue,{date},topics,...}
│   │       └── tasks.py     ← /tasks/{...} CRUD + move/reorder/start/pause
│   └── tests/               ← pytest suite (45 tests)
│       ├── conftest.py      ← in-memory SQLite fixtures
│       ├── test_auth.py
│       ├── test_stacks.py
│       ├── test_tasks.py
│       ├── test_topic_stacks.py
│       └── test_multitenant.py
│
└── frontend/
    ├── Dockerfile           ← dev: runs Vite with hot reload
    ├── Dockerfile.prod      ← prod: multi-stage build → nginx serves dist/
    ├── nginx.conf           ← prod only — /api proxy + SPA fallback
    ├── vite.config.ts       ← env-aware proxy target + file-watching polling
    └── src/
        ├── main.tsx
        ├── App.tsx          ← auth gate + view router (today/tomorrow/stacks)
        ├── index.css        ← all styles, Mono design tokens at top
        ├── types.ts
        ├── api/client.ts    ← `request<T>()` wrapper + the `api` object
        ├── auth/
        │   ├── AuthContext.tsx
        │   └── LoginPage.tsx
        └── components/
            ├── StackHeader.tsx
            ├── QuickCapture.tsx
            ├── StackView.tsx       ← drag-drop, optimistic state, polymorphic stackRef
            ├── TaskCard.tsx        ← prominence-scaled, timer, action buttons
            ├── TaskEditModal.tsx   ← edit title/desc/due/priority
            ├── OverdueSection.tsx
            ├── TopicStackList.tsx  ← "All Stacks" page + create modal
            └── TopicStackView.tsx  ← single topic stack detail
```

---

## Running locally

### Option 1 — Docker (recommended once you have Docker Desktop running)

```bash
docker compose up --build      # first time: ~3–6 min
docker compose up              # subsequent: ~5s
```

This starts **db** (Postgres 16, port 5432), **backend** (FastAPI, port 8000, `--reload` enabled, source bind-mounted), **frontend** (Vite, port 5173, source bind-mounted). Open http://localhost:5173.

First time, the SQLite path from native-dev won't carry over — sign up fresh.

### Option 2 — Native (`./dev.sh`)

```bash
./dev.sh
```

Runs backend on `:8000` against `backend/stack.db` (SQLite), frontend on `:5173` natively. No Docker dependency. Fastest hot reload. Single-user-ish (SQLite has writer locking).

### Prod (single port, nginx in front, backend/db isolated)

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build
```

App on http://localhost:8080 (configurable via `HOST_PORT` in [.env](.env)). Browser sees same origin for app + `/api`. Backend and db have no published ports.

### Running tests

```bash
cd backend && uv run pytest
```

Each test gets a fresh in-memory SQLite database via [conftest.py](backend/tests/conftest.py). The `client` fixture is a TestClient with the `get_db` dependency overridden. The `auth_client` fixture is the same but already signed up as `aryan@example.com`. The `second_client` is a separate TestClient (own cookie jar) signed up as `other@example.com` — used for multi-tenant isolation tests.

When adding new endpoints or behaviors, add a test in the matching `test_*.py` file. The suite runs in ~12s and is the cheapest possible regression net.

---

## Design system

See [design.md](design.md) for the full spec. The crash course:

- **Three colors only.** Canvas White (`#ffffff`), Ink Black (`#292929`), Deep Black (`#000000`). No grays, no accents.
- **Zero border-radius globally.** Every box is a sharp rectangle. CSS reset enforces this (`border-radius: 0 !important` on `*`).
- **No shadows.** State changes happen via thin (1px) borders, not elevation.
- **Typography over color** for hierarchy:
  - **NH** (Helvetica Neue) — body, headings. Negative letter-spacing (-0.02em).
  - **S-Condensed** (Impact) — nav, labels, chips. Positive letter-spacing (0.2em), UPPERCASE.
  - **EV** (Roboto Thin) — etched headlines. Weight 100.
  - **S-Works** (Bebas Neue) — wordmark.
- **Buttons are always outlined.** Transparent background, 1px Ink border. Filled = active state only.

If you're tempted to add a color or rounded corner, stop. The whole product's visual identity is the discipline of the constraints.

---

## Non-obvious conventions (gotchas to know)

1. **PATCH null clears, omit preserves.** Backend uses `payload.model_dump(exclude_unset=True)` and checks `if "field" in fields`. Sending `{description: null}` clears the description; omitting `description` from the body leaves it alone. Don't revert to `is not None` checks — you'll break field clearing. ([tasks.py:148](backend/app/routers/tasks.py:148))

2. **Cache clear on logout** ([AuthContext.tsx:64](frontend/src/auth/AuthContext.tsx:64)). React Query keys are not user-scoped, so we **must** call `qc.clear()` on logout to prevent the next user's data view from briefly showing the previous user's cached data. If you add new queries, this is the safety net.

3. **`Stack.tasks` relationship does NOT have `delete-orphan` cascade.** If you add `cascade="all, delete-orphan"` back, then setting `task.stack_id = None` (move to backlog) will silently DELETE the task. The current "all" without delete-orphan is intentional. ([models.py:84](backend/app/models.py:84))

4. **Pre-auth migration is SQLite-only.** [main.py `_drop_pre_auth_tables_if_needed`](backend/app/main.py) only runs on SQLite. Don't loosen this — a misconfigured Postgres deploy would lose all production data.

5. **`stack_id` and `stack_date` are mutually exclusive** on task create/move/reorder payloads. The backend's `_resolve_target_stack_id` enforces this. Frontend's `StackRef` type uses a discriminated union to make accidental dual-set impossible at the type level.

6. **Timer state is committed only on pause/done.** While running, only the frontend ticks (`useLiveElapsed`). The backend stores `in_progress_started_at` + `accumulated_seconds`; effective elapsed = `accumulated + (now - started_at)`. Don't write live time on every tick.

7. **Position is per-stack, dense from 0.** Reorder endpoint requires the full set of task IDs in the stack (no partial reorders). Insert with priority hints shifts neighbors. There's one known latent gap: same-stack `move_task` with no position can leave a hole (see CLAUDE.md history for context — covered in the code review).

8. **Backend reload + bind mount in dev compose, NOT in prod.** [docker-compose.yml](docker-compose.yml) overrides the backend's `command` to add `--reload` and mounts `./backend/app` → `/app/app`. The prod overlay resets both (`!reset null`, `!reset []`) so production runs the immutable image.

9. **Vite proxy target is env-driven.** `VITE_PROXY_TARGET` defaults to `http://localhost:8000` for native dev, set to `http://backend:8000` inside Docker. `CHOKIDAR_USEPOLLING=true` in container because macOS Docker file events are unreliable.

10. **CORS_ORIGINS env var is read by the backend at boot.** Comma-separated. Defaults to `http://localhost:5173,http://127.0.0.1:5173`. Update if you change the dev port or deploy somewhere new.

11. **Use `useInvalidateStacks()` after any task or stack mutation** ([useInvalidateStacks.ts](frontend/src/hooks/useInvalidateStacks.ts)). The hook invalidates `["stack"]`, `["topic-stack"]`, `["topic-stacks"]`, and `["overdue"]` together. If you only invalidate one, mutations on a topic-stack view won't refresh the UI (the bug that motivated this hook). Don't inline `qc.invalidateQueries({queryKey: ["stack"]})` in new mutations — use the hook so it stays consistent.

---

## Open issues we know about

Not bugs we're blocked on — just real things flagged by code review that haven't been fixed yet:

- **Safari microsecond timestamp parsing** — `new Date("...440918Z")` is brittle in older WebKit; the live timer could show NaN. ([TaskCard.tsx:43](frontend/src/components/TaskCard.tsx:43))
- **`OverdueSection` shows "from earlier"** generically because `TaskOut` doesn't expose `stack_date`. Add the field to the schema to surface real dates.
- **Cancelling a done task destroys `completed_at`.** No `cancelled_at` column; the only completion timestamp is lost.
- **Mutations other than `stackQuery` don't auto-logout on 401.** Only the stack-query 401 hook in App.tsx kicks the user to login.
- **`api/client.ts` headers merge** — caller-supplied `headers` shallow-replaces the default Content-Type. Latent (no current caller triggers it).
- **No real migrations.** `Base.metadata.create_all` + idempotent ALTERs is fine for the current scale but will bite the first time we need a column rename, type change, or backfill.

---

## When you (Claude / a teammate) ship something

A friendly checklist:

1. Did you change the data model? → update **Data model** above.
2. Did you add a new route, new top-level page, or change UX flow? → update **Project structure** and/or **Current state**.
3. Did you add a new env var or change Docker shape? → update **Running locally** and [.env.example](.env.example).
4. Did you discover a footgun? → add it to **Non-obvious conventions**.
5. Did you fix one of the **Open issues** above? → strike it off the list.
6. Did the vision shift? → update the top section.

Drift in this file undermines its value. Better a 5-minute doc update than a future hour debugging from stale context.
