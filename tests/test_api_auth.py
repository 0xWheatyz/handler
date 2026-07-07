"""Bearer auth on every route."""

from __future__ import annotations


def test_missing_token_is_401(client):
    assert client.get("/projects").status_code == 401


def test_wrong_token_is_401(client):
    r = client.get("/projects", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_valid_token_is_200(client, auth):
    assert client.get("/projects", headers=auth).status_code == 200


def test_health_needs_no_auth(client):
    assert client.get("/health").status_code == 200
