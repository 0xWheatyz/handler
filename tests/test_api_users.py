"""User accounts: first-run setup, sign-in, sessions, resets/invites, admin management.

The email flows run with SMTP unconfigured (the default test env), which is itself a
supported mode: links are returned to the admin instead of mailed. Delivery is covered
by faking ``emailer.send`` where it matters.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def admin_session(client):
    """Complete first-run setup; returns (headers, user) for the created admin."""
    r = client.post(
        "/auth/setup", json={"email": "admin@example.com", "password": "admin-pass-1"}
    )
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["is_admin"] is True
    return {"Authorization": f"Bearer {body['token']}"}, body["user"]


def _invite(client, admin_headers, email, is_admin=False):
    r = client.post(
        "/auth/users", json={"email": email, "is_admin": is_admin}, headers=admin_headers
    )
    assert r.status_code == 201
    return r.json()


def _accept(client, invite, password):
    token = invite["invite_url"].split("token=")[1]
    r = client.post("/auth/reset", json={"token": token, "password": password})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["user"]


# ---- first-run setup -------------------------------------------------------------------


def test_status_flips_after_setup(client):
    assert client.get("/auth/status").json()["initialized"] is False
    client.post("/auth/setup", json={"email": "a@b.co", "password": "password-1"})
    assert client.get("/auth/status").json()["initialized"] is True


def test_first_user_is_admin_and_second_setup_refused(client, admin_session):
    headers, user = admin_session
    assert user["is_admin"] is True
    r = client.post("/auth/setup", json={"email": "x@y.co", "password": "password-1"})
    assert r.status_code == 409


def test_setup_rejects_bad_email_and_short_password(client):
    bad_email = client.post("/auth/setup", json={"email": "nope", "password": "password-1"})
    assert bad_email.status_code == 422
    short = client.post("/auth/setup", json={"email": "a@b.co", "password": "short"})
    assert short.status_code == 422


# ---- sign-in / session lifecycle -------------------------------------------------------


def test_login_logout_me(client, admin_session):
    r = client.post("/auth/login", json={"email": "Admin@Example.COM", "password": "admin-pass-1"})
    assert r.status_code == 200  # email matching is case-insensitive
    headers = {"Authorization": f"Bearer {r.json()['token']}"}
    me = client.get("/auth/me", headers=headers).json()
    assert me == {
        "kind": "user", "user_id": r.json()["user"]["id"],
        "email": "admin@example.com", "is_admin": True,
    }
    assert client.post("/auth/logout", headers=headers).status_code == 200
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_login_rejects_wrong_password_and_unknown_email(client, admin_session):
    assert client.post(
        "/auth/login", json={"email": "admin@example.com", "password": "wrong-pass"}
    ).status_code == 401
    assert client.post(
        "/auth/login", json={"email": "ghost@example.com", "password": "whatever-1"}
    ).status_code == 401


def test_disabled_user_cannot_login_and_live_session_dies(client, admin_session):
    admin_headers, _ = admin_session
    invite = _invite(client, admin_headers, "dev@example.com")
    dev_headers, dev = _accept(client, invite, "dev-password-1")

    r = client.patch(f"/auth/users/{dev['id']}", json={"disabled": True}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["disabled"] is True
    assert client.post(
        "/auth/login", json={"email": "dev@example.com", "password": "dev-password-1"}
    ).status_code == 403
    # The existing session stops resolving too — disable means locked out now.
    assert client.get("/auth/me", headers=dev_headers).status_code == 401


def test_change_password_revokes_other_sessions(client, admin_session):
    headers, user = admin_session
    other = client.post(
        "/auth/login", json={"email": "admin@example.com", "password": "admin-pass-1"}
    )
    other_headers = {"Authorization": f"Bearer {other.json()['token']}"}

    r = client.post(
        "/auth/change-password",
        json={"current_password": "admin-pass-1", "new_password": "admin-pass-2"},
        headers=headers,
    )
    assert r.status_code == 200
    assert client.get("/auth/me", headers=headers).status_code == 200  # this session lives
    assert client.get("/auth/me", headers=other_headers).status_code == 401  # others die
    assert client.post(
        "/auth/login", json={"email": "admin@example.com", "password": "admin-pass-2"}
    ).status_code == 200

    wrong = client.post(
        "/auth/change-password",
        json={"current_password": "nope-nope-1", "new_password": "admin-pass-3"},
        headers=headers,
    )
    assert wrong.status_code == 403


# ---- invites & resets ------------------------------------------------------------------


def test_invite_flow_creates_usable_account(client, admin_session):
    admin_headers, _ = admin_session
    invite = _invite(client, admin_headers, "Dev@Example.com")
    assert invite["emailed"] is False  # SMTP unconfigured -> link only
    assert invite["user"]["has_password"] is False

    dev_headers, dev = _accept(client, invite, "dev-password-1")
    assert dev["email"] == "dev@example.com" and dev["is_admin"] is False
    assert client.get("/auth/me", headers=dev_headers).json()["email"] == "dev@example.com"
    # The invite link is one-shot.
    token = invite["invite_url"].split("token=")[1]
    assert client.post(
        "/auth/reset", json={"token": token, "password": "again-password-1"}
    ).status_code == 400


def test_invite_duplicate_email_conflicts(client, admin_session):
    admin_headers, _ = admin_session
    _invite(client, admin_headers, "dev@example.com")
    r = client.post("/auth/users", json={"email": "DEV@example.com"}, headers=admin_headers)
    assert r.status_code == 409


def test_admin_reset_link_and_forgot(client, admin_session, monkeypatch):
    admin_headers, admin = admin_session
    invite = _invite(client, admin_headers, "dev@example.com")
    dev_headers, dev = _accept(client, invite, "dev-password-1")

    # Admin-minted reset link works and revokes the old session on use.
    r = client.post(f"/auth/users/{dev['id']}/reset-link", headers=admin_headers)
    assert r.status_code == 200
    token = r.json()["reset_url"].split("token=")[1]
    reset = client.post("/auth/reset", json={"token": token, "password": "dev-password-2"})
    assert reset.status_code == 200
    assert client.get("/auth/me", headers=dev_headers).status_code == 401

    # Self-serve forgot: without SMTP it reports emailed=False and mints nothing.
    r = client.post("/auth/forgot", json={"email": "dev@example.com"})
    assert r.json() == {"ok": True, "emailed": False}

    # With (faked) SMTP configured, the link lands in an email — capture and use it.
    sent = []
    from handler import emailer

    monkeypatch.setattr(emailer, "configured", lambda settings=None: True)
    monkeypatch.setattr(
        emailer, "send", lambda to, subject, body, settings=None: sent.append((to, subject, body))
    )
    r = client.post("/auth/forgot", json={"email": "dev@example.com"})
    assert r.json() == {"ok": True, "emailed": True}
    assert sent and sent[0][0] == "dev@example.com"
    emailed_token = sent[0][2].split("token=")[1].split()[0]
    assert client.post(
        "/auth/reset", json={"token": emailed_token, "password": "dev-password-3"}
    ).status_code == 200
    # Unknown addresses get the same answer and no email.
    sent.clear()
    assert client.post("/auth/forgot", json={"email": "ghost@example.com"}).json()["ok"] is True
    assert sent == []


# ---- admin management guards -----------------------------------------------------------


def test_user_management_is_admin_only(client, admin_session):
    admin_headers, _ = admin_session
    invite = _invite(client, admin_headers, "dev@example.com")
    dev_headers, dev = _accept(client, invite, "dev-password-1")

    assert client.get("/auth/users", headers=dev_headers).status_code == 403
    assert client.post(
        "/auth/users", json={"email": "x@y.co"}, headers=dev_headers
    ).status_code == 403
    assert client.patch(
        f"/auth/users/{dev['id']}", json={"is_admin": True}, headers=dev_headers
    ).status_code == 403

    listed = client.get("/auth/users", headers=admin_headers).json()
    assert {u["email"] for u in listed} == {"admin@example.com", "dev@example.com"}


def test_last_admin_cannot_be_demoted_disabled_or_deleted(client, admin_session):
    admin_headers, admin = admin_session
    for body in ({"is_admin": False}, {"disabled": True}):
        r = client.patch(f"/auth/users/{admin['id']}", json=body, headers=admin_headers)
        assert r.status_code == 400, body
    assert client.delete(f"/auth/users/{admin['id']}", headers=admin_headers).status_code == 400

    # With a second active admin the original may step down.
    invite = _invite(client, admin_headers, "admin2@example.com", is_admin=True)
    _accept(client, invite, "admin2-pass-1")
    r = client.patch(f"/auth/users/{admin['id']}", json={"is_admin": False}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["is_admin"] is False


def test_deleting_a_user_shares_their_resources(client, admin_session, conn):
    admin_headers, _ = admin_session
    invite = _invite(client, admin_headers, "dev@example.com")
    dev_headers, dev = _accept(client, invite, "dev-password-1")

    r = client.post(
        "/projects", json={"id": "devproj", "root_dir": "/tmp/devproj"}, headers=dev_headers
    )
    assert r.status_code == 201 and r.json()["owner_user_id"] == dev["id"]

    r = client.delete(f"/auth/users/{dev['id']}", headers=admin_headers)
    assert r.status_code == 200
    project = client.get("/projects/devproj", headers=admin_headers).json()
    assert project["owner_user_id"] is None  # reassigned to shared, not orphaned
    assert client.get("/auth/me", headers=dev_headers).status_code == 401


def test_legacy_env_tokens_keep_working(client, admin_session, env):
    token_headers = {"Authorization": f"Bearer {env['token']}"}
    me = client.get("/auth/me", headers=token_headers).json()
    assert me["kind"] == "token" and me["user_id"] is None
    # ADMIN_TOKEN unset falls back to AUTH_TOKEN, so the env token passes admin gates.
    assert client.get("/auth/users", headers=token_headers).status_code == 200
    assert client.get("/projects", headers=token_headers).status_code == 200
