"""Client-IP extraction under various proxy topologies."""

from __future__ import annotations

import pytest
from starlette.datastructures import Headers
from starlette.requests import Request

from app.security import _client_ip


def _make_request(headers: dict[str, str], peer: str | None = "10.0.0.1") -> Request:
    """Minimal ASGI scope shaped enough for `_client_ip` to read it."""
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    scope = {
        "type": "http",
        "headers": raw_headers,
        "client": (peer, 0) if peer else None,
    }
    request = Request(scope)
    request._headers = Headers(raw=raw_headers)
    return request


def test_envoy_external_address_wins_when_present(monkeypatch):
    """Railway/Envoy deploys: X-Envoy-External-Address is authoritative."""
    monkeypatch.delenv("TRUSTED_PROXY_HOPS", raising=False)
    r = _make_request(
        {
            "x-envoy-external-address": "73.0.0.1",
            "x-forwarded-for": "1.1.1.1, 2.2.2.2",
        },
        peer="10.0.0.1",
    )
    assert _client_ip(r) == "73.0.0.1"


def test_envoy_takes_precedence_over_xff_even_with_trusted_hops(monkeypatch):
    """If both are present, Envoy wins — it's set by the edge proxy directly."""
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "2")
    r = _make_request(
        {
            "x-envoy-external-address": "73.0.0.1",
            "x-forwarded-for": "ATTACKER-FAKE, 99.0.0.1, 10.0.0.5",
        }
    )
    assert _client_ip(r) == "73.0.0.1"


def test_empty_envoy_header_falls_through(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "1")
    r = _make_request(
        {"x-envoy-external-address": "  ", "x-forwarded-for": "73.0.0.1"},
        peer="10.0.0.1",
    )
    assert _client_ip(r) == "73.0.0.1"


def test_no_trusted_hops_ignores_xff_uses_peer(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_HOPS", raising=False)
    r = _make_request({"x-forwarded-for": "1.1.1.1, 2.2.2.2"}, peer="10.0.0.1")
    assert _client_ip(r) == "10.0.0.1"


def test_one_trusted_hop_takes_rightmost(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "1")
    # Just nginx in front. XFF added by nginx is the user's IP.
    r = _make_request({"x-forwarded-for": "73.0.0.1"}, peer="10.0.0.1")
    assert _client_ip(r) == "73.0.0.1"


def test_two_trusted_hops_skips_cdn_entry(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "2")
    # CDN appended user (73.x), nginx appended CDN (198.x). Real user is 2nd
    # from right.
    r = _make_request({"x-forwarded-for": "73.0.0.1, 198.51.100.1"})
    assert _client_ip(r) == "73.0.0.1"


def test_two_trusted_hops_rejects_user_injected_leading_entry(monkeypatch):
    """User prepended 'FAKE' to spoof; trusted-hops logic ignores it."""
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "2")
    # FAKE (user-supplied), then 73.x (added by CDN), then 198.x (added by nginx).
    r = _make_request(
        {"x-forwarded-for": "1.1.1.1, 73.0.0.1, 198.51.100.1"}
    )
    assert _client_ip(r) == "73.0.0.1"


def test_trusted_hops_set_but_xff_too_short_falls_back_to_peer(monkeypatch):
    """Safety net: configured 2 hops but only 1 XFF entry — don't trust it."""
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "2")
    r = _make_request({"x-forwarded-for": "73.0.0.1"}, peer="10.0.0.1")
    assert _client_ip(r) == "10.0.0.1"


def test_missing_xff_returns_peer(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "2")
    r = _make_request({}, peer="10.0.0.1")
    assert _client_ip(r) == "10.0.0.1"


def test_no_peer_and_no_xff_returns_unknown(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_HOPS", raising=False)
    r = _make_request({}, peer=None)
    assert _client_ip(r) == "unknown"


@pytest.mark.parametrize("bad", ["", "abc", "-1"])
def test_malformed_env_falls_back_to_zero(monkeypatch, bad):
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", bad)
    r = _make_request({"x-forwarded-for": "1.1.1.1"}, peer="10.0.0.1")
    # bad/zero/negative → ignore XFF entirely
    assert _client_ip(r) == "10.0.0.1"
