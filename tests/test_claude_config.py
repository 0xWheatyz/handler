"""Seeding Claude Code onboarding so a detached agent boots straight to the REPL."""

from __future__ import annotations

import json
from pathlib import Path

from handler.control import claude_config


def _read(home: Path) -> dict:
    return json.loads((home / ".claude.json").read_text())


def test_ensure_onboarded_seeds_defaults_on_fresh_home(tmp_path):
    claude_config.ensure_onboarded(home=str(tmp_path))
    data = _read(tmp_path)
    assert data["hasCompletedOnboarding"] is True
    assert data["theme"] == "dark"


def test_ensure_onboarded_merges_without_clobbering(tmp_path):
    # The login flow's oauthAccount (and a chosen theme) must survive the seeding.
    (tmp_path / ".claude.json").write_text(
        json.dumps({"oauthAccount": {"emailAddress": "a@b.c"}, "theme": "light"})
    )
    claude_config.ensure_onboarded(home=str(tmp_path))
    data = _read(tmp_path)
    assert data["oauthAccount"] == {"emailAddress": "a@b.c"}  # preserved
    assert data["theme"] == "light"  # operator's chosen theme untouched
    assert data["hasCompletedOnboarding"] is True


def test_ensure_onboarded_forces_flag_and_trusts_working_dir(tmp_path):
    # A stale false must not leave onboarding armed; the working dir gets trusted.
    (tmp_path / ".claude.json").write_text(json.dumps({"hasCompletedOnboarding": False}))
    wd = "/var/lib/handler/projects/x"
    claude_config.ensure_onboarded(working_dir=wd, home=str(tmp_path))
    data = _read(tmp_path)
    assert data["hasCompletedOnboarding"] is True
    assert data["projects"][wd]["hasTrustDialogAccepted"] is True


def test_ensure_onboarded_survives_corrupt_file(tmp_path):
    (tmp_path / ".claude.json").write_text("{ not valid json")
    claude_config.ensure_onboarded(home=str(tmp_path))
    assert _read(tmp_path)["hasCompletedOnboarding"] is True
