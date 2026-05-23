import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError, ProgrammingError

from .database import Base, engine
from .routers import auth, stacks, tasks
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
Base.metadata.create_all(bind=engine)
_migrate_add_stack_kind_columns()
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


@app.get("/health")
def health():
    return {"status": "ok"}
