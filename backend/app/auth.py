"""Authentication: password hashing, session management, current-user dependency."""

import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as DbSession

from . import models
from .database import get_db
from .security import extract_bearer_token

logger = logging.getLogger(__name__)

SESSION_COOKIE_NAME = "stack_session"
SESSION_TTL = timedelta(days=30)
API_TOKEN_PREFIX = "stk_"
# urlsafe(32) → 43 chars; full token = "stk_" + 43 chars = 47 chars.
# Showing the first 12 chars (4 prefix + 8 random) is enough to disambiguate
# in the UI without leaking enough entropy to brute-force.
API_TOKEN_DISPLAY_PREFIX_LEN = 12

# Admin bootstrap. Comma-separated list of emails read at import time.
# Matching emails get is_admin=True the first time they resolve a session
# (browser login) or a bearer token. Promote-only — removing an email here
# does NOT demote (that requires a DB flip), so a stale env can't accidentally
# strip admin from someone still using the system.
_ADMIN_EMAILS: set[str] = {
    e.strip().lower()
    for e in os.getenv("ADMIN_EMAILS", "").split(",")
    if e.strip()
}


def _prehash(password: str) -> bytes:
    """SHA-256 the password so bcrypt's 72-byte input limit never bites.

    Pattern used by Dropbox et al. Bcrypt sees 32 fixed bytes regardless of
    the user's password length; we still get bcrypt's slow KDF on top.
    """
    return hashlib.sha256(password.encode("utf-8")).digest()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_prehash(password), password_hash.encode("utf-8"))
    except ValueError:
        return False


def _session_token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_session(
    db: DbSession, user: models.User, user_agent: str | None = None
) -> tuple[models.Session, str]:
    token = secrets.token_urlsafe(32)
    session = models.Session(
        id=_session_token_digest(token),
        user_id=user.id,
        expires_at=_now() + SESSION_TTL,
        user_agent=user_agent,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session, token


def set_session_cookie(response: Response, token: str) -> None:
    default_secure = (
        "true" if os.getenv("APP_ENV", "").lower() == "production" else "false"
    )
    secure_cookies = os.getenv("COOKIE_SECURE", default_secure).lower() == "true"
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=secure_cookies,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


def _api_token_digest(raw: str) -> str:
    """SHA-256 a raw API token for storage / lookup. Same shape as session digest."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def issue_api_token(db: DbSession, user: models.User, name: str) -> tuple[models.ApiToken, str]:
    """Mint a new API token. Returns (row, raw_token). Raw is shown to the
    user exactly once; the DB only ever holds the digest.
    """
    raw = API_TOKEN_PREFIX + secrets.token_urlsafe(32)
    row = models.ApiToken(
        user_id=user.id,
        name=name,
        token_hash=_api_token_digest(raw),
        prefix=raw[:API_TOKEN_DISPLAY_PREFIX_LEN],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, raw


def _resolve_bearer_user(
    request: Request, db: DbSession
) -> models.User | None:
    """If the request carries `Authorization: Bearer <token>`, look up the user.

    Returns None if no bearer header is present (caller falls back to cookie).
    Raises 401 if a bearer is present but invalid — never silently fall through,
    because that would let a stale-token client hit a stale-cookie session and
    get unexpected behavior.

    Note: error detail is uniformly "Invalid API token" for *every* failure
    (missing row, deleted user, empty token) so an attacker can't distinguish
    "this token belonged to a since-deleted user" from "this token never
    existed" by reading response bodies.
    """
    raw = extract_bearer_token(request)
    if raw is None:
        return None
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API token"
        )
    digest = _api_token_digest(raw)
    row = db.execute(
        select(models.ApiToken).where(models.ApiToken.token_hash == digest)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API token"
        )
    user = db.get(models.User, row.user_id)
    if user is None:
        # Unified message — see docstring.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API token"
        )
    # Best-effort last_used_at update. Narrow except so a real programming
    # bug is loud, not swallowed. SQLAlchemyError covers DB transport /
    # constraint failures — the only thing we're willing to ignore here.
    try:
        row.last_used_at = _now()
        db.commit()
    except SQLAlchemyError:
        logger.exception("Failed to bump last_used_at for token id=%s", row.id)
        db.rollback()
    return user


def revoke_bearer_token(db: DbSession, raw: str) -> None:
    """Delete the api_token row that matches `raw`, if any. Idempotent — no
    error on a missing/already-revoked token. Used by /auth/logout so a CLI
    that calls logout actually invalidates the bearer it was using."""
    digest = _api_token_digest(raw)
    row = db.execute(
        select(models.ApiToken).where(models.ApiToken.token_hash == digest)
    ).scalar_one_or_none()
    if row is not None:
        db.delete(row)
        db.commit()


def _auto_promote_admin(db: DbSession, user: models.User) -> None:
    """If `user.email` is in ADMIN_EMAILS and they aren't admin yet, flip the
    flag. Idempotent — once `is_admin=True`, the email check is skipped on
    subsequent requests. Promote-only (never demote)."""
    if user.is_admin or not _ADMIN_EMAILS:
        return
    if user.email.lower() in _ADMIN_EMAILS:
        user.is_admin = True
        try:
            db.commit()
        except SQLAlchemyError:
            logger.exception("Failed to auto-promote admin for user id=%s", user.id)
            db.rollback()


def get_current_user(
    request: Request,
    db: DbSession = Depends(get_db),
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> models.User:
    # Bearer first — programmatic clients (CLI, agents, MCP) bypass the cookie
    # path. If a bearer header is present and invalid, we raise immediately
    # rather than silently fall through to the cookie.
    bearer_user = _resolve_bearer_user(request, db)
    if bearer_user is not None:
        _auto_promote_admin(db, bearer_user)
        return bearer_user

    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    session = db.get(models.Session, _session_token_digest(session_token))
    if session is None or session.expires_at < _now():
        if session is not None:
            db.delete(session)
            db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    user = db.get(models.User, session.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    _auto_promote_admin(db, user)
    return user


def require_admin(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    """Dependency: gate an endpoint to admins only. 403 for non-admins.

    Note: admin endpoints intentionally accept BOTH bearer and cookie auth.
    Rationale: an admin running curl scripts to extract usage analytics from
    a CI job is a reasonable use case, and the bearer token is already gated
    to the user's own data + non-mutating /admin endpoints. If you add
    destructive admin endpoints later (ban-user, force-delete-stack), consider
    layering `require_session_auth` on top so the browser-only guarantee
    still applies."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return current_user


def require_session_auth(request: Request) -> None:
    """Reject the request if it carries a bearer header.

    Use as a path-operation dependency: `dependencies=[Depends(require_session_auth)]`
    so it runs BEFORE `get_current_user` and bearer requests are 403'd before
    `_resolve_bearer_user` would bump `last_used_at` on a token that was
    never actually allowed to use the endpoint.

    A compromised API token must NOT be able to escalate to permanent account
    takeover (change password, mint sibling tokens, revoke other tokens).
    """
    if extract_bearer_token(request) is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires an interactive session, not an API token.",
        )


def revoke_session(db: DbSession, token: str) -> None:
    session = db.get(models.Session, _session_token_digest(token))
    if session is not None:
        db.delete(session)
        db.commit()
