"""Authentication: password hashing, session management, current-user dependency."""

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session as DbSession

from . import models
from .database import get_db

SESSION_COOKIE_NAME = "stack_session"
SESSION_TTL = timedelta(days=30)


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


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_session(
    db: DbSession, user: models.User, user_agent: str | None = None
) -> models.Session:
    token = secrets.token_urlsafe(32)
    session = models.Session(
        id=token,
        user_id=user.id,
        expires_at=_now() + SESSION_TTL,
        user_agent=user_agent,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def set_session_cookie(response: Response, token: str) -> None:
    secure_cookies = os.getenv("COOKIE_SECURE", "false").lower() == "true"
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


def get_current_user(
    request: Request,
    db: DbSession = Depends(get_db),
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> models.User:
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    session = db.get(models.Session, session_token)
    if session is None or session.expires_at < _now():
        if session is not None:
            db.delete(session)
            db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    user = db.get(models.User, session.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


def revoke_session(db: DbSession, token: str) -> None:
    session = db.get(models.Session, token)
    if session is not None:
        db.delete(session)
        db.commit()
