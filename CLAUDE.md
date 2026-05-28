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

Most to-do apps are flat lists. They don't capture the truth that **priority is a queue, not a list**: there's one thing on top, the rest are queued, and the order changes as context shifts. The data structure is a priority queue; the product is named **Stack** because that's the everyday word for a pile of work.

Stack's core moves:
- **Daily stacks** — one per day. What you're committing to today. Forcing function for prioritization.
- **Topic stacks** — evergreen, by theme: Reading, Watching, Buy, Ideas, etc. Long-lived backlogs you pull from.
- **Priority hints** at capture time (top / high / normal / low) so adding things is fast.
- **Drag to reorder, click to edit.** Top of the stack visually dominant; lower items shrink.

### Where this is going

- **Shareable stacks** (v1 shipped). Topic stacks can be flipped public via `POST /stacks/topics/{id}/share`, get a random ~11-char slug, and render at `/s/<slug>` for anyone — no auth required. The public view hides done/cancelled tasks and operational state (timer, completed_at, etc.). Still TODO: discovery (browse other users' public stacks), user profile pages, comments.
- **AI stack agent** (planned). Looks at your stacks plus context you drop in ("the deadline moved up", "I have 2 hours free") and proposes a re-stacking with explanations. The shape of `task_events` (priority history) and `context_drops` will support this — neither is implemented yet.

---

## Current state — what's built

- ✅ Multi-user with email+password auth, server-side sessions, HTTP-only cookies
- ✅ Daily stacks (Today, Tomorrow) with drag-reorder, prominence scaling, intention line, overdue surfacing
- ✅ Topic stacks (7 kinds: `daily`, `todo`, `reading`, `watching`, `listening`, `buy`, `ideas`) — rename inline by clicking the title on the stack detail view (`PATCH /stacks/topics/{id}` with `name`)
- ✅ Per-task: name, **context_md (long-form markdown with optional YAML frontmatter; backend doesn't parse it yet)**, **direct_link (URL — primary click target on the card)**, due date, priority hint, status (pending / in_progress / done / cancelled), live timer for in-progress
- ✅ Move tasks between stacks (e.g. pull from a topic stack into Today)
- ✅ Quick-capture with priority hints
- ✅ Edit modal (name, direct_link, description, context_md markdown editor with bidirectional frontmatter sync + preview tab, due date, priority hint)
- ✅ Profile modal (display name + change password with current-pw verification + API token management)
- ✅ Confirm-password field on signup
- ✅ Bearer-token API access (per-user PATs, `stk_…`) for CLIs / agents / Claude Code skill file at [.claude/skills/stack/SKILL.md](.claude/skills/stack/SKILL.md)
- ✅ Admin panel — `/admin/stats` (users / tasks / stacks / api token counts + recent signups) + `/admin/users` (full list with task counts + last session). Gated on `is_admin`, bootstrapped via `ADMIN_EMAILS` env var. UI lives at the `Admin` nav tab (shown only to admins).
- ✅ Task counts in topbar nav (`Today (3)`, `Tomorrow (5)`, `Stacks (4)`)
- ✅ First-run onboarding tips card (no library tour — dismissable Mono card)
- ✅ Shareable topic stacks via random slug, read-only public viewer at `/s/<slug>`
- ✅ Dev: SQLite + native `./dev.sh`, OR Postgres + Docker compose
- ✅ Prod overlay (`docker-compose.prod.yml`): nginx in front, backend/db isolated inside the network
- ✅ Deployed on Railway (single-image root `Dockerfile` + managed Postgres)
- ✅ Root `Dockerfile`: single-image production build for platforms that detect a standard Dockerfile

## What's deliberately NOT built (yet)

- Discovery / browse other users' public stacks / user profile pages
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
       ├──── N ────► sessions  (id PK = SHA-256 token digest, user_id, expires_at)
       │
       ├──── N ────► api_tokens (id, user_id, name, token_hash UNIQUE,
       │                         prefix, created_at, last_used_at NULL)
       │
       ├──── N ────► stacks    (id, user_id, kind, stack_date NULL, name NULL,
       │                        intention NULL)
       │                       UNIQUE (user_id, stack_date)
       │
       └──── N ────► tasks     (id, user_id, stack_id NULL, name,
                                context_md, direct_link, description [DEPRECATED],
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
- **`ApiToken.token_hash`** stores only the SHA-256 of the raw token. The raw value is shown to the user exactly once at creation. `prefix` is the first 12 chars of the raw token (e.g. `stk_abc12345`) — surfaced in the list view so users can tell tokens apart without leaking the secret.
- **`User.is_admin`** gates the `/admin/*` router. Bootstrapped via `ADMIN_EMAILS` env var (comma-separated). `_auto_promote_admin` in [auth.py](backend/app/auth.py) flips the flag on next session resolve for any matching email. Promote-only — removing an email from the env doesn't demote.
- **Cascade**: deleting a user cascades to sessions/stacks/tasks/api_tokens. SQLite needs `PRAGMA foreign_keys = ON` (enabled in [database.py](backend/app/database.py)) for this to actually fire.

### NOT in the model (yet)

- `task_events` — audit log for reorderings. Designed but not built; needed before the AI agent can explain why it moves things.
- `context_drops`, `reprioritization_proposals` — AI flow. Designed in early planning, deferred.
- `is_public`, `share_slug` on stacks — for sharing. Not yet.

---

## Auth

- **Email + password.** bcrypt with SHA-256 prehash so passwords of any length work without bcrypt's 72-byte limit biting ([auth.py](backend/app/auth.py)).
- **Server-side sessions.** Random 32-byte URL-safe token stored as the cookie value; a SHA-256 digest is stored in `sessions`. 30-day TTL. Revocable.
- **Session tokens are hashed at rest.** The browser cookie holds the raw random token; `sessions.id` stores only its SHA-256 digest.
- **`HttpOnly` cookie, `SameSite=Lax`, `path=/`.** `Secure` defaults to true when `APP_ENV=production`; it can still be forced with `COOKIE_SECURE`.
- **Every endpoint** that touches user data uses `Depends(get_current_user)`. Stack/task queries filter by `current_user.id`. Direct task lookups go through `_get_owned_task` which returns 404 (not 403) for foreign tasks to avoid leaking existence.
- **Bearer-token auth for programmatic clients** (CLIs, agents, Claude Code skill file). `get_current_user` checks `Authorization: Bearer <stk_…>` *before* the session cookie. Tokens are minted from the Profile modal, stored as SHA-256 digest, never expire, revocable. **Bearer-authed requests bypass the CSRF header** — cross-site forms can't set `Authorization`, so the CSRF threat model doesn't apply.
- **Session-only endpoints.** A bearer token can NOT change password or mint/revoke other tokens (`require_session_auth` guard). This caps the blast radius of a leaked token: data access, never permanent account takeover.
- **Admin endpoints** (`/admin/*`) accept BOTH cookie and bearer auth — the `require_admin` dependency gates on `User.is_admin` regardless of auth path. Rationale: an admin running curl scripts to pull analytics from CI is a real workflow. If we ever add destructive admin endpoints (ban-user, force-delete-stack), layer `require_session_auth` on top so a leaked admin bearer can't take destructive action.
- **CSRF defense:** every unsafe request requires `X-Stack-CSRF: 1`; the frontend API client adds it globally. This blocks cross-site form POSTs from using the session cookie. (Bearer requests are exempt — see above.)
- **Auth rate limiting:** login/signup have a small in-process sliding-window limiter. The production nginx config also rate-limits login/signup at the proxy.
- **Public-read rate limiting:** `/public/stacks/{slug}` is throttled per IP (defaults 60/min). Defends against scrape/enumeration of shared content. Tunable via `PUBLIC_READ_RATE_LIMIT_IP_ATTEMPTS` and `PUBLIC_READ_RATE_LIMIT_WINDOW_SECONDS`.
- **Client-IP resolution (`_client_ip()`):** strategy chain, first match wins:
  1. `X-Envoy-External-Address` — set by Envoy edge proxies (Railway, Fly, etc.). Single trustworthy header that Envoy overwrites; client can't spoof. **On Railway no extra config is needed — this header lights up automatically.**
  2. `X-Forwarded-For` — for non-Envoy deploys. The backend reads the N-th entry from the right of XFF where N = `TRUSTED_PROXY_HOPS` env var. Default 0 = ignore XFF entirely (safe for dev / direct deploys). Set to `1` when only your own nginx is in front; set to `2` behind a non-Envoy CDN → nginx. Wrong N either bucket-merges all users or trusts a client-supplied value.
  3. TCP peer — local dev / no proxy.
- nginx is also configured to *append* (not overwrite) `X-Forwarded-For` via `$proxy_add_x_forwarded_for`, so the chain through any front proxy survives intact.

The limiter is per process/Machine, not a distributed quota. If this gets real traffic, keep the app-level limiter but add an edge WAF or shared store-backed limiter.

---

## Programmatic access (CLIs, agents, Claude Code)

Stack ships a [skill file at `.claude/skills/stack/SKILL.md`](.claude/skills/stack/SKILL.md) so any Claude Code user can call the REST API. Setup is two steps per user:

1. **Mint a token.** Profile modal → API tokens → name it (e.g. `claude-code`) → Generate → copy. The raw token (`stk_…`) is shown exactly once.
2. **Set env vars** (e.g. in `~/.zshrc`):
   ```bash
   export STACK_API_BASE="https://stack.example.com"
   export STACK_API_TOKEN="stk_…"
   ```

Then the skill's curl recipes (add to today, complete, move, list topics, share) "just work." Bearer-authed requests bypass the browser's `X-Stack-CSRF` header by design — see Auth note above.

The skill file lives in the repo so updates ship with the code. A user who wants it Claude-Code-wide can symlink:
```bash
ln -s "$(pwd)/.claude/skills/stack" ~/.claude/skills/stack
```

The same backend would also serve an MCP server later (since MCP is just another transport over the same endpoints + same bearer auth), but we haven't built that. Skill file is sufficient for now.

---

## Project structure

```
Stack/
├── CLAUDE.md                ← you are here
├── .claude/skills/stack/    ← skill file for Claude Code users (REST recipes)
├── Dockerfile               ← single-image production target: React + nginx + FastAPI
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
│   │   ├── auth.py          ← password hashing, session mgmt, bearer-token mgmt, get_current_user
│   │   └── routers/
│   │       ├── auth.py      ← /auth/{signup,login,logout,me,change-password,me/onboarded,tokens}
│   │       ├── stacks.py    ← /stacks/{today,tomorrow,overdue,counts,{date},topics,...}
│   │       ├── tasks.py     ← /tasks/{...} CRUD + move/reorder/start/pause
│   │       ├── public.py    ← /public/stacks/{slug} (read-only, unauthed)
│   │       └── admin.py     ← /admin/{stats,users} (require is_admin)
│   └── tests/               ← pytest suite (152 tests)
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
        │   ├── AuthContext.tsx  ← user + login/signup/logout/refresh
        │   ├── LoginPage.tsx    ← email + password (+ confirm on signup)
        │   └── ProfileModal.tsx ← display name + change password
        └── components/
            ├── StackHeader.tsx
            ├── QuickCapture.tsx
            ├── StackView.tsx       ← drag-drop, optimistic state, polymorphic stackRef
            ├── TaskCard.tsx        ← prominence-scaled, timer, action buttons
            ├── TaskEditModal.tsx   ← edit name/direct_link/desc (via frontmatter sync)/context_md/due/priority
            ├── OverdueSection.tsx
            ├── OnboardingTips.tsx  ← first-run dismissable tips card
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

The frontend's nginx proxies `/api/*` to whatever `BACKEND_URL` env var the container is started with. Default is `http://backend:8000/` so local compose Just Works. On a hosted platform (Railway / Fly / Render / etc.) set `BACKEND_URL` to that platform's internal hostname for the backend service, e.g. `http://backend.railway.internal:8000/`. The substitution happens at container startup via [nginx's built-in envsubst on `/etc/nginx/templates/*.template`](frontend/Dockerfile.prod) — no image rebuild needed per environment.

### Plain Dockerfile production image

```bash
docker build -t stack .
docker run --rm -p 8080:8080 \
  -e APP_ENV=production \
  -e COOKIE_SECURE=true \
  -e CORS_ORIGINS=http://localhost:8080 \
  -e DATABASE_URL='postgresql+psycopg://...' \
  stack
```

The root [Dockerfile](Dockerfile) builds the React app, writes the production nginx/startup config into the image, runs FastAPI on loopback `:8000`, and serves the app plus `/api` through nginx on `:8080`. In a hosted deploy, set `APP_ENV=production`, `COOKIE_SECURE=true`, `CORS_ORIGINS` to the public origin, and `DATABASE_URL` to Postgres.

### Running tests

```bash
cd backend && uv run pytest
```

Each test gets a fresh in-memory SQLite database via [conftest.py](backend/tests/conftest.py). The `client` fixture is a TestClient with the `get_db` dependency overridden. The `auth_client` fixture is the same but already signed up as `aryan@example.com`. The `second_client` is a separate TestClient (own cookie jar) signed up as `other@example.com` — used for multi-tenant isolation tests. Current suite size: 152 tests.

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

1. **PATCH null clears, omit preserves.** Backend uses `payload.model_dump(exclude_unset=True)` and checks `if "field" in fields`. Sending `{context_md: null}` clears the field; omitting it from the body leaves it alone. Don't revert to `is not None` checks — you'll break field clearing. ([tasks.py:148](backend/app/routers/tasks.py:148))

18. **`Task.description` is deprecated but still in the DB.** It was renamed to `context_md`. The migration backfills `context_md` from existing `description` rows once. New code reads/writes `context_md` only. The old column stays because SQLite can't cleanly DROP COLUMN; safe to ignore unless you need to manually back-fill from it.

19. **`context_md` frontmatter is convention only, not parsed by the backend.** Users (and eventually agents) write YAML-style frontmatter (`name:`, `description:`, `direct_link:`) at the top of their markdown. The backend stores it verbatim. The `direct_link` URL the click handler opens lives in its own structured column — not parsed from frontmatter. That separation keeps the click path fast and avoids backend YAML parsing in v1.

20. **Stack-level share gating for context.** `Stack.share_context_in_public` (default `false`) controls whether `PublicTaskOut.context_md` is populated. `direct_link` is always exposed when sharing — it's the click target visitors actually use.

21. **`Task.title` was renamed to `Task.name`.** Both Postgres and SQLite (3.25+) support `ALTER TABLE … RENAME COLUMN`, so this was a real rename (not a deprecation). The migration in [main.py `_migrate_rename_task_title_to_name`](backend/app/main.py) runs **before** `Base.metadata.create_all` so existing DBs rename in place and fresh DBs get `name` directly. The API payload key, Pydantic field, frontend types, and the modal label all use `name` now — there is no `title` left anywhere. If you find one in a future PR, it's a bug.

22. **Bidirectional frontmatter ↔ inputs in TaskEditModal.** The modal's Name/Direct link/Description inputs are derived views over `context_md`'s frontmatter — typing in an input rewrites the YAML block; editing the YAML updates the inputs. The shared parser/serializer lives in [`frontend/src/lib/markdown.ts`](frontend/src/lib/markdown.ts) and uses a leading-one-whitespace strip (not `.trim()`) so spaces typed inside input fields don't get eaten on round-trip. Unknown frontmatter keys (e.g. `tags:`) are preserved.

23. **Bearer auth wins over the session cookie in `get_current_user`.** If both are present we use the bearer. A request with a stale cookie + valid bearer goes through; the reverse also works. Important: **`enforce_csrf_header` ALSO checks for bearer first** — bearer-authed unsafe requests skip the CSRF header requirement. Cross-site forms can't set `Authorization` (not on the CORS safelist), so the CSRF threat model genuinely doesn't apply to them. If you add a new transport (basic auth, OAuth) that also bypasses the cookie, mirror the same exemption pattern.

24. **Session-only endpoints reject bearer with 403.** `change_password`, `create_api_token`, `list_api_tokens`, `revoke_api_token` all call `auth_service.require_session_auth(request)` as their first line. A leaked API token must NOT be able to mint sibling tokens, revoke existing tokens, or change the password — that's the difference between "they have access to my data until I notice" and "they own the account forever." If you add another endpoint where bearer access would be dangerous (account deletion, billing, etc.), add this same guard.

25. **Admin is bootstrapped via env, not the UI.** `ADMIN_EMAILS` is a comma-separated list read once at backend boot. On any session resolve (cookie or bearer), `_auto_promote_admin` flips `is_admin=True` for matching emails. There's NO admin UI to create admins — that'd be a chicken-and-egg problem the first time and a self-grant escalation surface every time after. To add an admin: edit the env, restart the backend, ask them to log out + in. To remove one: manual DB flip (`UPDATE users SET is_admin=false WHERE email=…`) — the env is promote-only by design so a typo in `ADMIN_EMAILS` can't accidentally strip access from someone actively using the system.

2. **Cache clear on logout** ([AuthContext.tsx:64](frontend/src/auth/AuthContext.tsx:64)). React Query keys are not user-scoped, so we **must** call `qc.clear()` on logout to prevent the next user's data view from briefly showing the previous user's cached data. If you add new queries, this is the safety net.

3. **`Stack.tasks` relationship does NOT have `delete-orphan` cascade.** If you add `cascade="all, delete-orphan"` back, then setting `task.stack_id = None` (move to backlog) will silently DELETE the task. The current "all" without delete-orphan is intentional. ([models.py:84](backend/app/models.py:84))

4. **Pre-auth migration is SQLite-only.** [main.py `_drop_pre_auth_tables_if_needed`](backend/app/main.py) only runs on SQLite. Don't loosen this — a misconfigured Postgres deploy would lose all production data.

5. **`stack_id` and `stack_date` are mutually exclusive** on task create/move/reorder payloads. The backend's `_resolve_target_stack_id` enforces this. Frontend's `StackRef` type uses a discriminated union to make accidental dual-set impossible at the type level.

6. **Timer state is committed only on pause/done.** While running, only the frontend ticks (`useLiveElapsed`). The backend stores `in_progress_started_at` + `accumulated_seconds`; effective elapsed = `accumulated + (now - started_at)`. Don't write live time on every tick.

7. **Position is per-stack, dense from 0.** Reorder endpoint requires the full set of task IDs in the stack (no partial reorders). Insert with priority hints shifts neighbors. There's one known latent gap: same-stack `move_task` with no position can leave a hole (see CLAUDE.md history for context — covered in the code review). **Status transitions to `done` or `cancelled` slide the task to the LAST position** ([`_move_task_to_end_of_stack` in tasks.py](backend/app/routers/tasks.py)) so the "top of the stack = next thing to do" metaphor stays honest — a done item at position 0 was still visually dominating the largest prominence tier. Only fires on real transitions (idempotent re-sets are a no-op for ordering). Reviving a done task to pending does NOT restore its original position — it stays at the bottom and the user can drag back up. **The frontend also collapses every done task to the least-prominent tier (`task--prest`) regardless of its slot** ([prominence in TaskCard.tsx](frontend/src/components/TaskCard.tsx)) — the backend slide-to-end is the primary mechanism, but with only a few tasks a done item can still land in a high slot, so the class override guarantees all completed items render identically (smallest, faded) and never visually dominate.

8. **Backend reload + bind mount in dev compose, NOT in prod.** [docker-compose.yml](docker-compose.yml) overrides the backend's `command` to add `--reload` and mounts `./backend/app` → `/app/app`. The prod overlay resets both (`!reset null`, `!reset []`) so production runs the immutable image.

9. **Vite proxy target is env-driven.** `VITE_PROXY_TARGET` defaults to `http://localhost:8000` for native dev, set to `http://backend:8000` inside Docker. `CHOKIDAR_USEPOLLING=true` in container because macOS Docker file events are unreliable.

10. **CORS_ORIGINS env var is read by the backend at boot.** Comma-separated. Defaults to `http://localhost:5173,http://127.0.0.1:5173`. Update if you change the dev port or deploy somewhere new.

11. **CSRF header is mandatory on unsafe requests.** [api/client.ts](frontend/src/api/client.ts) adds `X-Stack-CSRF: 1` globally. Any new non-frontend client or test fixture must send that header for POST/PATCH/DELETE.

12. **Use `useInvalidateStacks()` after any task or stack mutation** ([useInvalidateStacks.ts](frontend/src/hooks/useInvalidateStacks.ts)). The hook invalidates `["stack"]`, `["topic-stack"]`, `["topic-stacks"]`, and `["overdue"]` together. If you only invalidate one, mutations on a topic-stack view won't refresh the UI (the bug that motivated this hook). Don't inline `qc.invalidateQueries({queryKey: ["stack"]})` in new mutations — use the hook so it stays consistent.

13. **Mobile responsive at ≤700px and ≤420px** (all in one `@media` block at the bottom of [index.css](frontend/src/index.css)). When adding new components, keep them desktop-correct at the component level and add mobile overrides in that block — don't mix breakpoints throughout the file. Inputs that accept text must be ≥16px font-size on mobile or iOS Safari zooms on focus. Drag-and-drop uses `MouseSensor` + `TouchSensor` with a 200ms touch delay so finger scroll isn't hijacked into a reorder.

14. **`AuthContext.refresh()` after any mutation that changes the user row** (display name change, onboarding completion, future fields). It re-fetches `/auth/me` and replaces the user state — so the topbar / onboarding visibility / etc. react. Don't push `setUser` access into other components.

15. **`/auth/me/onboarded` is idempotent.** Re-calling on an already-onboarded user keeps the original `onboarded_at`. `OnboardingTips` only renders when `user.onboarded === false`, so dismissing once is permanent.

16. **`POST /auth/change-password` requires the current password.** Never let a session change the password without re-verifying — a hijacked session could otherwise lock the real owner out. Also rejects "new == current" with 400.

17. **`/stacks/counts` is the source for topbar badges.** Don't compute counts client-side from cached stack queries — different views fetch different keys, so counts would drift. Always invalidate `["counts"]` on mutations (`useInvalidateStacks` already does).

---

## Open issues we know about

Not bugs we're blocked on — just real things flagged by code review that haven't been fixed yet:

- **Safari microsecond timestamp parsing** — `new Date("...440918Z")` is brittle in older WebKit; the live timer could show NaN. ([TaskCard.tsx:43](frontend/src/components/TaskCard.tsx:43))
- **`OverdueSection` shows "from earlier"** generically because `TaskOut` doesn't expose `stack_date`. Add the field to the schema to surface real dates.
- **Cancelling a done task destroys `completed_at`.** No `cancelled_at` column; the only completion timestamp is lost.
- **Mutations other than `stackQuery` don't auto-logout on 401.** Only the stack-query 401 hook in App.tsx kicks the user to login.
- **No real migrations.** `Base.metadata.create_all` + idempotent ALTERs is fine for the current scale but will bite the first time we need a column rename, type change, or backfill.
- **No way to browse past stacks in the UI.** Yesterday's stack and everything before it still exist in the DB (tasks marked done that day have their `completed_at` timestamp, etc.), and the API can return them via `GET /stacks/{date}`. The frontend just doesn't surface them anywhere — Overdue only shows unfinished items. A `← Yesterday` button or a date picker in the topbar would close this gap without any schema work.
- **`index.css` is a single ~1100-line file.** Functional but unwieldy. Two reasonable next steps when it starts hurting: (a) split into per-feature CSS files glued by `@import`, or (b) move to CSS Modules with colocated `.module.css` per component (tokens + responsive stay global). B is the real fix; A is the cheap intermediate step.

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
