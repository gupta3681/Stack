---
name: stack
description: Add tasks, list stacks, complete/move tasks, and manage topic stacks in Stack via its bearer-token REST API. Use when the user mentions adding something to "today", "tomorrow", a topic stack (reading/watching/buy/ideas/etc.), or wants to query / mutate their Stack data.
---

# Stack — REST recipes

Stack is a priority-queue todo app. Daily stacks are the date-bound "what I'm doing today" lists; topic stacks are evergreen backlogs (Reading, Watching, Buy, Ideas, To Do, etc.). Tasks have `name`, optional `context_md` (markdown body), `direct_link` (URL), `priority_hint` (top/high/normal/low), `due_at` (ISO datetime), `estimate_minutes`, `status`.

## Vocabulary: stack kinds

Every `Stack` has a `kind`. There are seven:

| kind        | what it's for                                               | shape                                     |
| ----------- | ----------------------------------------------------------- | ----------------------------------------- |
| `daily`     | "What I'm doing on a specific date." One per user per date. | date-bound, `name=null`, `stack_date` set |
| `todo`      | Generic action items that don't fit anywhere else.          | topic stack, user-named                   |
| `reading`   | Articles, books, papers, anything to read.                  | topic stack                               |
| `watching`  | Videos, films, shows.                                       | topic stack                               |
| `listening` | Podcasts, albums, talks.                                    | topic stack                               |
| `buy`       | Things to purchase.                                         | topic stack                               |
| `ideas`     | Loose thoughts to chew on later.                            | topic stack                               |

The user can have **multiple stacks of the same kind** (e.g. "Books 2026" + "Books reread"), each with its own `name` and `id`. When the user says "add to my reading stack," disambiguate if more than one `reading` stack exists — see the filter recipe below.

Task `status` values: `pending`, `in_progress`, `done`, `cancelled`. The "alive" set the UI shows is `pending` + `in_progress` — `done` and `cancelled` are hidden from the main lists but still queryable.

## Setup (one-time, per user)

API tokens are **created from the browser, not the API**. An agent can't mint its own token — the `POST /auth/tokens` endpoint rejects bearer-authed requests with `403` by design. If `STACK_API_TOKEN` is unset, stop and tell the user to do this:

1. Open https://stack-production-138b.up.railway.app → click their name in the topbar → **Profile** → **API tokens** tab.
2. Name it (e.g. `claude-code`) → **Generate**.
3. Copy the `stk_…` token immediately — it's shown once, never recoverable.
4. Add to `~/.zshrc` (or equivalent):

   ```bash
   export STACK_API_BASE="https://stack-production-138b.up.railway.app/api"
   export STACK_API_TOKEN="stk_…"
   ```

## Calling the API

Every call needs the bearer header. Bearer-authed requests **do not** need the `X-Stack-CSRF` header that the browser uses.

```bash
curl -sS "$STACK_API_BASE/auth/me" \
  -H "Authorization: Bearer $STACK_API_TOKEN"
```

If you see `401`, the token is invalid or revoked — ask the user to generate a new one. If `403 "requires an interactive session"`, you hit a session-only endpoint (change-password, mint/revoke tokens) — those are browser-only by design.

## Common recipes

### Add to today

```bash
TODAY=$(date +%F)
curl -sS "$STACK_API_BASE/tasks" \
  -H "Authorization: Bearer $STACK_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"review PRs\", \"stack_date\": \"$TODAY\", \"priority_hint\": \"top\"}"
```

`priority_hint` is one of `top` / `high` / `normal` / `low`. `top` inserts at position 0 (the most prominent slot). Omit for normal placement at the end.

### Add with a link, estimate, and rich context

```bash
curl -sS "$STACK_API_BASE/tasks" \
  -H "Authorization: Bearer $STACK_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d @- <<'JSON'
{
  "name": "Read: A Philosophy of Software Design",
  "stack_id": 42,
  "direct_link": "https://www.amazon.com/Philosophy-Software-Design-2nd/dp/173210221X",
  "estimate_minutes": 240,
  "context_md": "## Why\nOusterhout's argument about deep modules has been bugging me."
}
JSON
```

Use `stack_id` to add to a topic stack; `stack_date` for daily. Never both.

### List today's stack

```bash
curl -sS "$STACK_API_BASE/stacks/today" \
  -H "Authorization: Bearer $STACK_API_TOKEN"
```

Returns the full stack object with a `tasks: [...]` array. Each task has `id`, `name`, `status`, `position`, etc.

### List a specific date

```bash
curl -sS "$STACK_API_BASE/stacks/2026-05-25" \
  -H "Authorization: Bearer $STACK_API_TOKEN"
```

### Complete a task

```bash
TASK_ID=123
curl -sS -X PATCH "$STACK_API_BASE/tasks/$TASK_ID" \
  -H "Authorization: Bearer $STACK_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "done"}'
```

`status` values: `pending`, `in_progress`, `done`, `cancelled`.

### Move a task to tomorrow

```bash
TASK_ID=123
TMRW=$(date -v+1d +%F 2>/dev/null || date -d 'tomorrow' +%F)
curl -sS -X POST "$STACK_API_BASE/tasks/$TASK_ID/move" \
  -H "Authorization: Bearer $STACK_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"stack_date\": \"$TMRW\"}"
```

To move into a topic stack: `{"stack_id": 42}` instead. To send to the backlog (unstacked): `{"stack_date": null}`.

### Start / pause the timer

```bash
curl -sS -X POST "$STACK_API_BASE/tasks/$TASK_ID/start" \
  -H "Authorization: Bearer $STACK_API_TOKEN"

curl -sS -X POST "$STACK_API_BASE/tasks/$TASK_ID/pause" \
  -H "Authorization: Bearer $STACK_API_TOKEN"
```

### List topic stacks

```bash
curl -sS "$STACK_API_BASE/stacks/topics" \
  -H "Authorization: Bearer $STACK_API_TOKEN"
```

Each row has `id`, `name`, `kind`, `tasks: [...]`. The tasks come back inline — you don't need a second call to get them. Use `id` for any `stack_id` you pass elsewhere.

### Find stacks of a specific kind (e.g. "my reading stack")

There's no `?kind=` filter on the endpoint — list everything, then filter:

```bash
# Pretty-print all reading stacks
curl -sS "$STACK_API_BASE/stacks/topics" \
  -H "Authorization: Bearer $STACK_API_TOKEN" \
  | jq '.[] | select(.kind == "reading")'

# Just their names and ids
curl -sS "$STACK_API_BASE/stacks/topics" \
  -H "Authorization: Bearer $STACK_API_TOKEN" \
  | jq '.[] | select(.kind == "reading") | {id, name, task_count: (.tasks | length)}'

# Grab the ID of the first reading stack (for further calls)
READING_ID=$(curl -sS "$STACK_API_BASE/stacks/topics" \
  -H "Authorization: Bearer $STACK_API_TOKEN" \
  | jq -r '[.[] | select(.kind == "reading")][0].id')
```

If the user has multiple stacks of the same kind, **disambiguate by name** before acting — don't silently pick the first one.

### Get one topic stack by id (freshest copy)

```bash
curl -sS "$STACK_API_BASE/stacks/topics/$STACK_ID" \
  -H "Authorization: Bearer $STACK_API_TOKEN"
```

Same shape as a row from the list endpoint, including inline tasks.

### Read a single task's full context (markdown body)

The `tasks` array on a stack already includes each task's `context_md`. But if you have only a task ID (e.g. from a previous list), fetch it directly:

```bash
TASK_ID=123
curl -sS "$STACK_API_BASE/tasks/$TASK_ID" \
  -H "Authorization: Bearer $STACK_API_TOKEN"
```

Returns the full `TaskOut`: `id`, `name`, `context_md` (the long-form markdown body, including any YAML frontmatter the user added), `direct_link`, `priority_hint`, `due_at`, `estimate_minutes`, `status`, `accumulated_seconds`, `in_progress_started_at`, timestamps. To pull just the markdown:

```bash
curl -sS "$STACK_API_BASE/tasks/$TASK_ID" \
  -H "Authorization: Bearer $STACK_API_TOKEN" \
  | jq -r '.context_md // "(no context)"'
```

Foreign task IDs return `404` (not `403`) — the API never confirms whether another user's task exists.

### Get backlog tasks (no stack assigned)

Tasks that exist but aren't on any stack — typically dropped there by moving without a destination:

```bash
curl -sS "$STACK_API_BASE/tasks/backlog" \
  -H "Authorization: Bearer $STACK_API_TOKEN"
```

Returns a flat array of `TaskOut` rows.

### Create a topic stack

```bash
curl -sS "$STACK_API_BASE/stacks/topics" \
  -H "Authorization: Bearer $STACK_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"kind": "reading", "name": "Books 2026"}'
```

`kind` is one of `todo` / `reading` / `watching` / `listening` / `buy` / `ideas`.

### Share a topic stack publicly

```bash
STACK_ID=42
curl -sS -X POST "$STACK_API_BASE/stacks/topics/$STACK_ID/share" \
  -H "Authorization: Bearer $STACK_API_TOKEN"
```

Returns the stack with `share_slug` populated. The public URL is `https://stack-production-138b.up.railway.app/s/<slug>` (at the site root, not under `/api`). No auth needed for the visitor.

### Get overdue items

```bash
TODAY=$(date +%F)
curl -sS "$STACK_API_BASE/stacks/overdue?today=$TODAY" \
  -H "Authorization: Bearer $STACK_API_TOKEN"
```

### Set the day's intention

```bash
TODAY=$(date +%F)
curl -sS -X PATCH "$STACK_API_BASE/stacks/$TODAY" \
  -H "Authorization: Bearer $STACK_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"intention": "Ship the bearer-auth feature."}'
```

## Patterns to follow

- **PATCH semantics:** sending `{"due_at": null}` clears the field. Omitting the key from the body leaves it alone. Don't include keys you don't want to touch.
- **Position is per-stack, dense from 0.** Reorders need the full ID list — use the UI for those, the API expects all of them in one call.
- **Direct link click target:** if `direct_link` is set, the card opens that URL when clicked. URLs must be `http://` or `https://` — anything else is rejected.
- **Stack/date are mutually exclusive** on task create/move: pick one of `stack_id` or `stack_date`, never both, never neither (when adding to a real stack).

## What this token can't do

By design:

- Change the user's password (interactive session only).
- Mint or revoke other API tokens (interactive session only).
- See or touch any other user's data — even with a guessed token ID, the response is `404`.

If the user asks you to do any of those, point them to the Profile modal in the browser.
