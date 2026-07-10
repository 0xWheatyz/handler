"""Phase 3 UI serving: the bundled web UI is served same-origin and, critically, is
*additive* — it must not shadow any existing API route, and both the toggle (UI_ENABLED)
and the optional CORS behave as documented. The frontend JS itself has no test runner
(by design) and is verified via the manual e2e walkthrough in docs/PLAN.md.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _reset_caches() -> None:
    from handler import config
    from handler.db import engine

    config.get_settings.cache_clear()
    engine.get_engine.cache_clear()


def _fresh_client(monkeypatch, **overrides) -> TestClient:
    """Build an app after applying env overrides — the shared `client` fixture bakes in
    defaults, so toggle tests need their own app constructed post-setenv."""
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)
    _reset_caches()
    from handler.api.app import create_app

    return TestClient(create_app())


# --- shell + assets are served, unauthenticated -------------------------------------


def test_index_served_unauthenticated(client):
    res = client.get("/")  # no Authorization header
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/html")
    assert "<title>Handler" in res.text
    # the shell must never inline data or a token
    assert "Bearer" not in res.text


@pytest.mark.parametrize(
    "path, marker",
    [
        ("/static/app.js", "function app("),
        ("/static/styles.css", ".badge"),
        ("/static/alpine.min.js", "Alpine.js"),
    ],
)
def test_static_assets_served_unauthenticated(client, path, marker):
    res = client.get(path)  # no auth
    assert res.status_code == 200
    assert marker in res.text


# --- the static surface must NOT shadow the API ------------------------------------


def test_api_routes_not_shadowed(client, auth):
    # /health still open
    assert client.get("/health").json() == {"status": "ok"}
    # /projects still requires auth (the static mount didn't swallow it)
    assert client.get("/projects").status_code == 401
    res = client.get("/projects", headers=auth)
    assert res.status_code == 200
    assert res.json() == []
    # "/" is an explicit route, not a catch-all: unknown paths still 404
    assert client.get("/does-not-exist").status_code == 404


# --- CORS: off by default, on when configured --------------------------------------


def test_cors_absent_by_default(client):
    res = client.get("/health", headers={"Origin": "https://example.com"})
    assert res.status_code == 200
    assert "access-control-allow-origin" not in {k.lower() for k in res.headers}


def test_cors_present_when_configured(env, monkeypatch):
    origin = "https://handler.example.ts.net"
    client = _fresh_client(monkeypatch, CORS_ORIGINS=origin)
    res = client.get("/health", headers={"Origin": origin})
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == origin


# --- UI_ENABLED=false => headless, API intact --------------------------------------


def test_ui_disabled_serves_no_shell_but_api_works(env, monkeypatch, auth):
    client = _fresh_client(monkeypatch, UI_ENABLED="false")
    assert client.get("/").status_code == 404
    assert client.get("/static/app.js").status_code == 404
    # API is untouched
    assert client.get("/health").status_code == 200
    assert client.get("/projects", headers=auth).status_code == 200
