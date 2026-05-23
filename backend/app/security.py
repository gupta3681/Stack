"""Security helpers shared by routers and middleware."""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request, status
from starlette.responses import JSONResponse, Response

CSRF_HEADER_NAME = "x-stack-csrf"
CSRF_HEADER_VALUE = "1"

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
_rate_buckets: dict[str, deque[float]] = defaultdict(deque)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"


async def enforce_csrf_header(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Require a same-origin-only custom header on unsafe requests."""
    if request.method.upper() not in _SAFE_METHODS:
        if request.headers.get(CSRF_HEADER_NAME) != CSRF_HEADER_VALUE:
            return JSONResponse(
                {"detail": "Missing CSRF header"},
                status_code=status.HTTP_403_FORBIDDEN,
            )
    return await call_next(request)


def check_rate_limit(
    request: Request,
    bucket: str,
    *,
    identifier: str | None = None,
    max_attempts: int,
    window_seconds: int,
) -> None:
    """Small dependency-free sliding-window limiter."""
    if os.getenv("AUTH_RATE_LIMIT_DISABLED", "").lower() == "true":
        return
    if max_attempts <= 0 or window_seconds <= 0:
        return

    now = time.monotonic()
    key = f"{bucket}:{_client_ip(request)}:{identifier or '-'}"
    attempts = _rate_buckets[key]
    while attempts and now - attempts[0] > window_seconds:
        attempts.popleft()
    if len(attempts) >= max_attempts:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts. Try again later.",
        )
    attempts.append(now)


def check_login_rate_limit(request: Request, email: str) -> None:
    window = _env_int("AUTH_RATE_LIMIT_WINDOW_SECONDS", 15 * 60)
    check_rate_limit(
        request,
        "login-ip",
        max_attempts=_env_int("AUTH_RATE_LIMIT_LOGIN_IP_ATTEMPTS", 20),
        window_seconds=window,
    )
    check_rate_limit(
        request,
        "login-email",
        identifier=email.lower(),
        max_attempts=_env_int("AUTH_RATE_LIMIT_LOGIN_EMAIL_ATTEMPTS", 8),
        window_seconds=window,
    )


def check_signup_rate_limit(request: Request) -> None:
    check_rate_limit(
        request,
        "signup-ip",
        max_attempts=_env_int("AUTH_RATE_LIMIT_SIGNUP_IP_ATTEMPTS", 10),
        window_seconds=_env_int("AUTH_RATE_LIMIT_SIGNUP_WINDOW_SECONDS", 60 * 60),
    )


def reset_rate_limits() -> None:
    """Test helper."""
    _rate_buckets.clear()
