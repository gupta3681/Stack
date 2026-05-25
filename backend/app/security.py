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
BEARER_PREFIX = "bearer "  # case-insensitive prefix; exactly one literal space

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
_rate_buckets: dict[str, deque[float]] = defaultdict(deque)


def extract_bearer_token(request: Request) -> str | None:
    """Parse `Authorization: Bearer <token>` from the request.

    Returns the raw token (whitespace stripped) if present, None if the
    header is absent or doesn't carry a bearer scheme. Used by BOTH
    `enforce_csrf_header` (to decide CSRF exemption) and the auth path
    (to authenticate) — single source of truth so the two layers can't drift.
    """
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith(BEARER_PREFIX):
        return None
    return auth_header[len(BEARER_PREFIX) :].strip()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _client_ip(request: Request) -> str:
    """Identify the client IP for rate-limit bucketing.

    Strategy chain — first match wins:

    1. `X-Envoy-External-Address` — set by Envoy edge proxies (Railway, Fly,
       anything fronted by Envoy). A single non-chain header containing the
       real external client IP. Envoy overwrites it, so the user can't
       spoof. This is Railway's officially recommended source.

    2. `X-Forwarded-For` — generic proxy chain. Each proxy appends the IP
       it saw; the N-th entry from the right is what the *first* trusted
       proxy observed (the real user). `TRUSTED_PROXY_HOPS` tells us N.
       Without that env var we ignore XFF entirely — anything in it could
       be client-injected.

    3. TCP peer — local dev and any setup with no proxy at all.
    """
    envoy_addr = request.headers.get("x-envoy-external-address")
    if envoy_addr and envoy_addr.strip():
        return envoy_addr.strip()

    trusted_hops = _env_int("TRUSTED_PROXY_HOPS", 0)
    if trusted_hops > 0:
        xff = request.headers.get("x-forwarded-for", "")
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if len(parts) >= trusted_hops:
            return parts[-trusted_hops]

    if request.client is not None:
        return request.client.host
    return "unknown"


async def enforce_csrf_header(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Require a same-origin-only custom header on unsafe requests.

    CSRF defends against cross-site form posts that ride the user's cookie.
    Bearer-token requests are exempt: a malicious site can't set the
    `Authorization` header on a form post (it's not on the CORS safelist), so
    no cookie-style forgery is possible against bearer-authed endpoints.
    Requiring CSRF on bearer requests would just break every CLI/agent client.
    """
    if request.method.upper() not in _SAFE_METHODS:
        if extract_bearer_token(request) is not None:
            return await call_next(request)
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


def check_public_read_rate_limit(request: Request) -> None:
    """Throttle anonymous reads of /public/* endpoints.

    Public unauth endpoints are the canonical scrape/DoS target. Generous
    enough for normal browsing (real visitors load a page once), tight
    enough to slow down enumeration/scraping.
    """
    check_rate_limit(
        request,
        "public-read-ip",
        max_attempts=_env_int("PUBLIC_READ_RATE_LIMIT_IP_ATTEMPTS", 60),
        window_seconds=_env_int("PUBLIC_READ_RATE_LIMIT_WINDOW_SECONDS", 60),
    )


def reset_rate_limits() -> None:
    """Test helper."""
    _rate_buckets.clear()
