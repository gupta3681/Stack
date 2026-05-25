# Stack

> A productivity app organized around the metaphor of a **priority stack** — the thing on top is what you're doing next, and the stack is reorganized as the world changes.

**Live:** https://stack-production-138b.up.railway.app

---

## What it is

Most to-do apps are flat lists. Stack treats priority as what it actually is — a queue. The top of every stack is rendered *physically larger* than the rest, so you feel the weight of the one thing that's next instead of scanning to find it.

- **Daily stacks** — Today, Tomorrow. Date-bound. What you're committing to.
- **Topic stacks** — Reading, Watching, Buy, Ideas, Interview Prep, To-Do. Evergreen backlogs you pull from.
- **Pull / push** between them — promote an item from "Reading" into today; if you don't finish, push it back.
- **Live timer** per task, drag-to-reorder, priority hints, due dates, time estimates.
- **Shareable** — flip any topic stack public via a stable slug, no login required for visitors.
- **Agent-friendly** — bearer-token REST API so CLIs and Claude Code can read and write your stacks.

---

## Stack

| Layer | Tech |
|---|---|
| Frontend | React 18 + Vite + TypeScript + TanStack Query + @dnd-kit |
| Backend | FastAPI + SQLAlchemy 2 + Pydantic v2 (Python 3.12) |
| Database | Postgres 16 (prod) · SQLite (local dev) |
| Auth | bcrypt + HTTP-only session cookies + per-user bearer tokens for programmatic access |
| Styling | Plain CSS — Mono design system (3 colors, zero radius, no shadows) |
| Hosting | Railway (single-image Docker, managed Postgres) |

---

## Run it locally

Three options. Pick whichever fits.

### Docker (recommended once you have Docker Desktop running)

```bash
cp .env.example .env
docker compose up --build      # first time: ~3–6 min
docker compose up              # subsequent: ~5s
```

Open http://localhost:5173 and sign up.

### Native (`./dev.sh`)

```bash
./dev.sh
```

Runs FastAPI on `:8000` against `backend/stack.db` (SQLite), Vite on `:5173`. No Docker needed. Fastest hot reload.

### Production-shape (single port, nginx in front)

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build
```

App on http://localhost:8080.

---

## Tests

```bash
cd backend && uv run pytest
```

120 tests, ~25s, in-memory SQLite per test. See [`backend/tests/conftest.py`](backend/tests/conftest.py) for fixtures.

---

## Programmatic / agent access

Each user can mint personal API tokens for CLIs, scripts, or Claude Code:

1. Sign up → click your name in the topbar → **Profile** → **API Tokens**
2. Name it, hit Generate, copy the `stk_…` token (shown once)
3. Set env vars:
   ```bash
   export STACK_API_BASE="https://stack-production-138b.up.railway.app/api"
   export STACK_API_TOKEN="stk_…"
   ```
4. Call the API:
   ```bash
   curl -sS "$STACK_API_BASE/stacks/today" \
     -H "Authorization: Bearer $STACK_API_TOKEN"
   ```

A **Claude Code skill** ships in the repo at [`.claude/skills/stack/SKILL.md`](.claude/skills/stack/SKILL.md). It teaches Claude Code the recipes for adding tasks, pulling from a topic stack, completing things, sharing, and reading rich context. To install globally:

```bash
ln -s "$(pwd)/.claude/skills/stack" ~/.claude/skills/stack
```

Bearer tokens **cannot** mint sibling tokens or change your password — those stay browser-only by design, so a leaked token caps out at "data access" rather than permanent account takeover.

---

## Architecture, conventions, gotchas

See [**CLAUDE.md**](CLAUDE.md) — it's the source-of-truth project doc covering the data model, auth design, non-obvious patterns, open issues, and the v0.x roadmap. Keep it in sync with material changes; that's how future-you (or a teammate, or an agent) finds the rationale behind a decision without re-deriving it.

---

## Status

Personal project. Built in the open, used daily. Real users welcome but no SLA. The vision section on the landing page calls out what's deliberately not built yet (autonomous priority agent, discovery, mobile app); the rest is real and shipped.
