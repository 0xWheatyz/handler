"""The web-login API surface: enqueue login_start / login_submit, admin-gated."""

from __future__ import annotations


def _admin(env):
    # ADMIN_TOKEN is unset in the test env, so the admin gate falls back to AUTH_TOKEN.
    return {"Authorization": f"Bearer {env['token']}"}


def test_login_start_enqueues_command(client, env):
    r = client.post("/login/start", headers=_admin(env))
    assert r.status_code == 202
    body = r.json()
    assert body["type"] == "login_start"
    assert body["status"] == "queued"
    assert body["requested_by"] == "operator:web"


def test_login_submit_enqueues_command_with_code(client, env):
    r = client.post("/login/submit", headers=_admin(env), json={"code": "auth-xyz"})
    assert r.status_code == 202
    body = r.json()
    assert body["type"] == "login_submit"
    assert body["payload"] == {"code": "auth-xyz"}


def test_login_submit_rejects_blank_code(client, env):
    r = client.post("/login/submit", headers=_admin(env), json={"code": ""})
    assert r.status_code == 422


def test_login_start_requires_auth(client):
    assert client.post("/login/start").status_code in (401, 403)


def test_login_endpoints_require_admin_token(client, env, monkeypatch):
    # With a distinct admin token set, the plain auth token must be refused.
    monkeypatch.setenv("ADMIN_TOKEN", "admin-secret")
    from handler import config

    config.get_settings.cache_clear()
    try:
        r = client.post("/login/start", headers={"Authorization": f"Bearer {env['token']}"})
        assert r.status_code == 403
        ok = client.post("/login/start", headers={"Authorization": "Bearer admin-secret"})
        assert ok.status_code == 202
    finally:
        config.get_settings.cache_clear()
