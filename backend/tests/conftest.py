"""Pytest fixtures: every test gets a fresh in-memory SQLite database.

The app's `get_db` dependency is overridden to use the test session factory,
so endpoint code runs unchanged but talks to an isolated, throwaway DB per
test. The pre-auth migration in main.py is a no-op against an empty schema,
so importing the app is safe.
"""

import os
import sys
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Tell the app to use a throwaway SQLite DB before importing it. The app
# resolves DATABASE_URL at import time, so this must be set first.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

# Make the `app` package importable when running `uv run pytest` from anywhere.
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Fresh app + fresh in-memory DB per test."""
    # Build a dedicated in-memory engine with StaticPool so all sessions share
    # the same connection (otherwise each session gets its own private DB).
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_fks(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Import here so the env var above takes effect.
    from app import database as db_module
    from app.database import Base
    from app.main import app

    Base.metadata.create_all(bind=engine)

    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[db_module.get_db] = override_get_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def auth_client(client: TestClient) -> TestClient:
    """A TestClient already logged in as `aryan@example.com`."""
    r = client.post(
        "/auth/signup",
        json={"email": "aryan@example.com", "password": "correcthorse", "display_name": "Aryan"},
    )
    assert r.status_code == 201, r.text
    return client


@pytest.fixture
def second_client(client: TestClient) -> TestClient:
    """A second client logged in as `other@example.com` — for isolation tests.

    Note: this shares the same underlying app/DB as `client`, but is a
    distinct TestClient so cookies don't collide.
    """
    # We need a SEPARATE TestClient instance pointing at the same app so the
    # second user has their own cookie jar. Reusing `client` would clobber
    # the first user's session.
    from app.main import app

    other = TestClient(app)
    r = other.post(
        "/auth/signup",
        json={"email": "other@example.com", "password": "anotherpw1234", "display_name": "Other"},
    )
    assert r.status_code == 201, r.text
    return other
