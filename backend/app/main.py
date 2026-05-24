import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError, ProgrammingError

from .database import Base, engine
from .routers import auth, public, stacks, tasks
from .security import enforce_csrf_header


def _drop_pre_auth_tables_if_needed() -> None:
    """One-shot upgrade path for the local dev SQLite database only.

    Pre-auth schema had no `user_id` column. SQLite can't add NOT NULL columns
    to populated tables, so we drop and let create_all rebuild. This is ONLY
    safe on the throwaway local dev DB — never on Postgres, which must use
    real migrations (Alembic) for any schema change.
    """
    if engine.dialect.name != "sqlite":
        return
    inspector = inspect(engine)
    if "tasks" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("tasks")}
    if "user_id" in columns:
        return
    print(
        "[stack] WARNING: pre-auth SQLite schema detected — dropping local "
        "tasks/stacks tables to rebuild with user_id. (This only runs on SQLite.)",
        flush=True,
    )
    Base.metadata.drop_all(
        bind=engine,
        tables=[
            Base.metadata.tables["tasks"],
            Base.metadata.tables["stacks"],
        ],
    )


def _migrate_add_stack_kind_columns() -> None:
    """Additive migration for the kind+name columns on `stacks`.

    Also drops the NOT NULL on `stack_date` because topic stacks (kind != daily)
    don't have a date. Safe to run repeatedly on both SQLite and Postgres.
    """
    inspector = inspect(engine)
    if "stacks" not in inspector.get_table_names():
        return
    columns = {c["name"]: c for c in inspector.get_columns("stacks")}

    statements: list[str] = []
    if "kind" not in columns:
        statements.append(
            "ALTER TABLE stacks ADD COLUMN kind VARCHAR(20) NOT NULL DEFAULT 'daily'"
        )
    if "name" not in columns:
        statements.append("ALTER TABLE stacks ADD COLUMN name VARCHAR(200)")

    # Drop NOT NULL on stack_date if it's still required. SQLite can't ALTER
    # column nullability without a table rebuild — skip; SQLite users on the
    # old schema will need to delete stack.db once.
    if (
        engine.dialect.name == "postgresql"
        and "stack_date" in columns
        and columns["stack_date"].get("nullable") is False
    ):
        statements.append("ALTER TABLE stacks ALTER COLUMN stack_date DROP NOT NULL")

    if not statements:
        return
    with engine.begin() as conn:
        for sql in statements:
            try:
                conn.execute(text(sql))
            except (OperationalError, ProgrammingError):
                # Column likely already exists from a concurrent worker; safe to ignore.
                pass


def _migrate_add_stack_sharing_columns() -> None:
    """Additive migration: stacks.is_public + stacks.share_slug.

    Existing rows default to is_public=false, share_slug=NULL — so nothing
    becomes public by accident. Safe to run repeatedly.
    """
    inspector = inspect(engine)
    if "stacks" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("stacks")}
    statements: list[str] = []
    if "is_public" not in columns:
        statements.append(
            "ALTER TABLE stacks ADD COLUMN is_public BOOLEAN NOT NULL DEFAULT FALSE"
        )
    if "share_slug" not in columns:
        statements.append("ALTER TABLE stacks ADD COLUMN share_slug VARCHAR(20)")
        # Both Postgres and SQLite treat NULL as distinct in unique indexes,
        # so a plain CREATE UNIQUE INDEX lets multiple unshared stacks coexist
        # with share_slug=NULL. Fresh DBs get this index from the model's
        # unique=True; IF NOT EXISTS handles the upgrade case here.
        statements.append(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_stacks_share_slug "
            "ON stacks (share_slug)"
        )
    if not statements:
        return
    with engine.begin() as conn:
        for sql in statements:
            try:
                conn.execute(text(sql))
            except (OperationalError, ProgrammingError):
                pass


def _migrate_add_task_context_columns() -> None:
    """Additive migration: tasks.context_md + tasks.direct_link.

    Backfills context_md from any existing non-null description so the
    rename doesn't lose data. Old description column stays in the DB
    (SQLite can't DROP COLUMN cleanly) but new code never reads it.
    """
    inspector = inspect(engine)
    if "tasks" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("tasks")}
    statements: list[str] = []
    if "context_md" not in columns:
        statements.append("ALTER TABLE tasks ADD COLUMN context_md TEXT")
        # Backfill: preserve any existing description text as the body of
        # the new markdown field. Users can later add frontmatter on top.
        statements.append(
            "UPDATE tasks SET context_md = description "
            "WHERE description IS NOT NULL AND context_md IS NULL"
        )
    if "direct_link" not in columns:
        statements.append("ALTER TABLE tasks ADD COLUMN direct_link VARCHAR(2048)")
    if not statements:
        return
    with engine.begin() as conn:
        for sql in statements:
            try:
                conn.execute(text(sql))
            except (OperationalError, ProgrammingError):
                pass


def _migrate_add_stack_share_context_column() -> None:
    """Additive migration: stacks.share_context_in_public (default false)."""
    inspector = inspect(engine)
    if "stacks" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("stacks")}
    if "share_context_in_public" in columns:
        return
    with engine.begin() as conn:
        try:
            conn.execute(
                text(
                    "ALTER TABLE stacks ADD COLUMN share_context_in_public "
                    "BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
        except (OperationalError, ProgrammingError):
            pass


def _migrate_add_task_estimate_column() -> None:
    """Additive migration: tasks.estimate_minutes (nullable INT)."""
    inspector = inspect(engine)
    if "tasks" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("tasks")}
    if "estimate_minutes" in columns:
        return
    with engine.begin() as conn:
        try:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN estimate_minutes INTEGER"))
        except (OperationalError, ProgrammingError):
            pass


def _migrate_rename_task_title_to_name() -> None:
    """One-shot rename: tasks.title → tasks.name.

    The frontmatter convention, modal label, and the public API now all use
    `name`. The DB column was the last lingering `title`. Postgres and
    SQLite (3.25+) both support ALTER TABLE ... RENAME COLUMN.

    Idempotent: skips if the rename already happened (name exists) or if
    we're on a brand-new DB (neither column exists yet — create_all will
    make `name` directly).
    """
    inspector = inspect(engine)
    if "tasks" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("tasks")}
    if "name" in columns:
        return
    if "title" not in columns:
        return
    with engine.begin() as conn:
        try:
            conn.execute(text("ALTER TABLE tasks RENAME COLUMN title TO name"))
        except (OperationalError, ProgrammingError):
            # Loud-fail in logs but don't crash boot — the next request will
            # 500 visibly if the rename truly failed.
            import logging

            logging.exception("Failed to rename tasks.title → tasks.name")


def _migrate_add_user_onboarded_at() -> None:
    """Additive migration: users.onboarded_at — null on existing rows.

    Existing users get NULL, so they see the onboarding tips on next login.
    That's intentional — better one-time tip card than missed introduction.
    Safe to run repeatedly.
    """
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns("users")}
    if "onboarded_at" in columns:
        return
    with engine.begin() as conn:
        try:
            conn.execute(
                text("ALTER TABLE users ADD COLUMN onboarded_at TIMESTAMP")
            )
        except (OperationalError, ProgrammingError):
            pass


_drop_pre_auth_tables_if_needed()
# Rename has to run BEFORE create_all on existing DBs — otherwise create_all
# is a no-op (table exists) and the column rename never happens. On fresh
# DBs the rename is a no-op (tasks table doesn't exist yet) and create_all
# makes the table with the new `name` column directly.
_migrate_rename_task_title_to_name()
Base.metadata.create_all(bind=engine)
_migrate_add_stack_kind_columns()
_migrate_add_stack_sharing_columns()
_migrate_add_task_context_columns()
_migrate_add_stack_share_context_column()
_migrate_add_task_estimate_column()
_migrate_add_user_onboarded_at()


app = FastAPI(title="Stack", version="0.2.0")

app.middleware("http")(enforce_csrf_header)

cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in cors_origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(stacks.router)
app.include_router(tasks.router)
app.include_router(public.router)


@app.get("/health")
def health():
    return {"status": "ok"}
