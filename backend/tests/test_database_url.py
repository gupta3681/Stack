"""Postgres URL normalization — managed providers hand out URLs with no
driver suffix, but we ship psycopg v3 only, so they need rewriting."""

from app.database import _normalize_pg_driver


def test_plain_postgres_scheme_gets_psycopg_driver():
    url = "postgres://u:p@host:5432/db"
    assert _normalize_pg_driver(url) == "postgresql+psycopg://u:p@host:5432/db"


def test_postgresql_scheme_gets_psycopg_driver():
    url = "postgresql://u:p@host:5432/db"
    assert _normalize_pg_driver(url) == "postgresql+psycopg://u:p@host:5432/db"


def test_already_specified_psycopg_left_alone():
    url = "postgresql+psycopg://u:p@host:5432/db"
    assert _normalize_pg_driver(url) == url


def test_sqlite_url_left_alone():
    url = "sqlite:///./stack.db"
    assert _normalize_pg_driver(url) == url


def test_query_params_preserved():
    url = "postgres://u:p@host:5432/db?sslmode=require"
    assert (
        _normalize_pg_driver(url)
        == "postgresql+psycopg://u:p@host:5432/db?sslmode=require"
    )
