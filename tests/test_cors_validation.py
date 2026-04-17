"""
Tests for CORSOriginValidationMiddleware.

Validates that the server does NOT reflect arbitrary Origin headers back
in Access-Control-Allow-Origin. Only explicitly allowed origins should
receive CORS headers; all others must be rejected with 403.

Addresses the CORS misconfiguration finding from issue #5 AuthProbe scan.
"""

import pytest
from starlette.testclient import TestClient


@pytest.fixture
def http_client():
    """Create test client with HTTP app (includes all security middleware)."""
    from server import app

    asgi_app = app.http_app(path="/mcp/")
    return TestClient(asgi_app, raise_server_exceptions=False)


# ── Untrusted origins must be blocked ────────────────────────────────────


def test_rejects_arbitrary_origin(http_client):
    """Requests with an untrusted Origin must receive 403 Forbidden."""
    response = http_client.post(
        "/mcp/",
        json={"jsonrpc": "2.0", "method": "initialize", "id": "1"},
        headers={
            "Content-Type": "application/json",
            "Origin": "http://invalid.example",
        },
    )
    assert response.status_code == 403
    data = response.json()
    assert data["error"] == "Forbidden"
    assert "Origin not allowed" in data["detail"]


def test_allows_localhost_for_local_development(http_client):
    """localhost / 127.0.0.1 are explicitly allowed by CORSOriginValidation's
    _LOCAL_ORIGIN_PATTERN -- CORS is a browser-only policy and permitting
    localhost doesn't widen the attack surface (an attacker's page runs on
    their own origin, not localhost)."""
    response = http_client.post(
        "/mcp/",
        json={"jsonrpc": "2.0", "method": "initialize", "id": "1"},
        headers={
            "Content-Type": "application/json",
            "Origin": "http://localhost:3000",
        },
    )
    # Must NOT be 403 from CORS. Downstream may 500 because Starlette
    # TestClient doesn't run FastMCP's lifespan (task group unavailable)
    # -- that's unrelated to CORS validation, which is what we're testing.
    assert response.status_code != 403


def test_rejects_preflight_from_untrusted_origin(http_client):
    """OPTIONS preflight from an untrusted origin must be rejected."""
    response = http_client.options(
        "/mcp/",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 403


# ── Trusted origins must be allowed ──────────────────────────────────────


def test_allows_trusted_origin(http_client):
    """Requests from the trusted origin should NOT be rejected by CORS middleware."""
    response = http_client.post(
        "/mcp/",
        json={"jsonrpc": "2.0", "method": "initialize", "id": "1"},
        headers={
            "Content-Type": "application/json",
            "Origin": "https://rivalsearchmcp.fastmcp.app",
        },
    )
    # Should NOT be 403 from our CORS middleware (downstream may return
    # 500 in test environment due to missing FastMCP lifespan, but that's
    # unrelated to CORS validation).
    assert response.status_code != 403


def test_preflight_from_trusted_origin(http_client):
    """OPTIONS preflight from a trusted origin should return 204."""
    response = http_client.options(
        "/mcp/",
        headers={
            "Origin": "https://rivalsearchmcp.fastmcp.app",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 204
    assert response.headers.get("access-control-allow-origin") == (
        "https://rivalsearchmcp.fastmcp.app"
    )
    assert "POST" in response.headers.get("access-control-allow-methods", "")


# ── No Origin header → pass through ─────────────────────────────────────


def test_no_origin_header_passes_through(http_client):
    """Requests without Origin (e.g. stdio, curl) should pass through."""
    response = http_client.post(
        "/mcp/",
        json={"jsonrpc": "2.0", "method": "initialize", "id": "1"},
        headers={"Content-Type": "application/json"},
    )
    # Should not be blocked by CORS middleware
    assert response.status_code != 403


# ── Helper / unit tests ─────────────────────────────────────────────────


def test_get_allowed_origins_defaults():
    """Default origins should include the FastMCP app domain."""
    from src.middleware.cors_validation import _get_allowed_origins

    origins = _get_allowed_origins()
    assert "https://rivalsearchmcp.fastmcp.app" in origins
    assert "https://RivalSearchMCP.fastmcp.app" in origins


def test_get_allowed_origins_from_env(monkeypatch):
    """ALLOWED_ORIGINS env var should extend the default set."""
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://example.com,https://foo.bar")
    from src.middleware.cors_validation import _get_allowed_origins

    origins = _get_allowed_origins()
    assert "https://example.com" in origins
    assert "https://foo.bar" in origins
    # Defaults are still present
    assert "https://rivalsearchmcp.fastmcp.app" in origins
