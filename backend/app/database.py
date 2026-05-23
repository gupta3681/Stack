import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


def _resolve_database_url() -> str:
    """Prefer DATABASE_URL env var (set by docker-compose); fall back to local SQLite."""
    url = os.getenv("DATABASE_URL")
    if url:
        return url
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
