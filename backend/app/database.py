import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


def _normalize_pg_driver(url: str) -> str:
    """Force the psycopg (v3) driver for any Postgres URL.

    Managed Postgres providers (Railway, Heroku, Render, etc.) hand out plain
    `postgres://` or `postgresql://` URLs. SQLAlchemy interprets those as
    "use psycopg2", which we don't install — we ship psycopg v3 only. This
    rewrite makes any Postgres URL Just Work without the operator having to
    know about driver suffixes.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def _resolve_database_url() -> str:
    """Prefer DATABASE_URL env var (set by docker-compose); fall back to local SQLite."""
    url = os.getenv("DATABASE_URL")
    if url:
        return _normalize_pg_driver(url)
    if os.getenv("APP_ENV", "").lower() == "production":
        raise RuntimeError("DATABASE_URL is required when APP_ENV=production")
    db_path = Path(__file__).resolve().parent.parent / "stack.db"
    return f"sqlite:///{db_path}"


DATABASE_URL = _resolve_database_url()

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, connect_args=connect_args)


if DATABASE_URL.startswith("sqlite"):
    # SQLite ignores ondelete=CASCADE/SET NULL unless foreign keys are explicitly
    # enabled per connection. Postgres enforces them by default.
    @event.listens_for(engine, "connect")
    def _enable_sqlite_fks(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
