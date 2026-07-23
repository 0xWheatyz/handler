"""Distribute claude's OAuth credentials to every worker through the database.

The interactive ``/login`` flow (see :mod:`~handler.control.login`) completes on exactly
one worker container and writes credentials under that container's ``$HOME``. With
multiple headless workers, the others need those files too — and the deployment rule is
"no shared filesystems, the DB is the single source of truth". So:

- ``upload()`` bundles the credential files, encrypts the bundle with the existing
  Fernet secret store (``HANDLER_SECRET_KEY``), and upserts it into ``runtime_secrets``.
  Called after a confirmed login, and after a run if claude refreshed the token on disk.
- ``refresh()`` (workers, at startup and periodically) materializes the bundle locally
  when the DB copy is newer than what this worker last saw. ``~/.claude.json`` is merged
  (only credential-ish top-level keys are taken) so a worker's own onboarding/trust
  state written by ``claude_config.ensure_onboarded`` survives; the pure credential file
  is written verbatim.

Everything is best-effort and silently off when no ``HANDLER_SECRET_KEY`` is configured
(single-worker deployments work exactly as before).
"""

from __future__ import annotations

import json
import os

from .. import secretstore
from ..db import repository as repo
from ..db.engine import connection

SECRET_KEY = "claude_credentials"

# ~/.claude.json keys that belong to the *account*, not this machine's UI/trust state.
_ACCOUNT_KEYS = ("oauthAccount", "userID", "organization", "account")


def _credential_files() -> dict[str, str]:
    """Relative path -> absolute path of every claude credential file we bundle."""
    home = os.path.expanduser("~")
    return {
        ".claude.json": os.path.join(home, ".claude.json"),
        ".claude/.credentials.json": os.path.join(home, ".claude", ".credentials.json"),
    }


def fingerprint() -> tuple:
    """(path, mtime_ns, size) of the OAuth token file — cheap change detection.

    Deliberately only ``.claude/.credentials.json``: claude touches ``~/.claude.json``
    on every run (project entries, UI state), and treating those as "new credentials"
    would ping-pong uploads between workers forever. A login that only rewrites
    ``.claude.json`` is still published — the login flow calls :func:`upload` directly.
    """
    path = _credential_files()[".claude/.credentials.json"]
    try:
        st = os.stat(path)
    except OSError:
        return ()
    return ((path, st.st_mtime_ns, st.st_size),)


def upload() -> bool:
    """Encrypt the local credential files into ``runtime_secrets``. Returns whether a
    bundle was stored (False when disabled or there is nothing to store)."""
    if not secretstore.enabled():
        return False
    bundle: dict[str, str] = {}
    for rel, path in _credential_files().items():
        try:
            with open(path) as fh:
                bundle[rel] = fh.read()
        except OSError:
            continue
    if not bundle:
        return False
    value_enc = secretstore.encrypt(json.dumps(bundle))
    with connection() as conn:
        repo.upsert_runtime_secret(conn, SECRET_KEY, value_enc)
    return True


def _merge_claude_json(path: str, incoming: str) -> None:
    """Take the account keys from ``incoming`` into ``path``, preserving local state.

    A worker's ``~/.claude.json`` also carries per-directory trust + onboarding flags for
    *its* clones; clobbering those would re-wedge spawns on the trust dialog.
    """
    try:
        new_data = json.loads(incoming)
    except (ValueError, TypeError):
        return
    if not isinstance(new_data, dict):
        return
    current: dict = {}
    if os.path.exists(path):
        try:
            with open(path) as fh:
                current = json.load(fh)
        except (OSError, ValueError):
            current = {}
        if not isinstance(current, dict):
            current = {}
    if not current:
        merged = new_data
    else:
        merged = current
        for key in _ACCOUNT_KEYS:
            if key in new_data:
                merged[key] = new_data[key]
    _write_private(path, json.dumps(merged, indent=2))


def _write_private(path: str, content: str) -> None:
    """Atomic write with 0600 from the first byte — these files carry OAuth tokens."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.credsync.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(content)
    os.replace(tmp, path)


class _State:
    """Per-process sync cursor: the DB updated_at we last materialized, and the local
    file fingerprint after the last upload/materialize (to detect claude refreshing
    the token mid-run so the next refresh() re-uploads)."""

    def __init__(self) -> None:
        self.seen_updated_at = None
        self.last_fingerprint: tuple | None = None


_state = _State()


def refresh() -> str | None:
    """One sync pass; returns "materialized", "uploaded", or None (no-op).

    - A DB bundle newer than what we've seen wins: materialize it locally.
    - Otherwise, local credential files that changed since our last pass (a login on
      this worker, or claude refreshing a token during a run) get uploaded.
    """
    if not secretstore.enabled():
        return None
    with connection() as conn:
        row = repo.get_runtime_secret(conn, SECRET_KEY)

    if row is not None and row["updated_at"] != _state.seen_updated_at:
        try:
            bundle = json.loads(secretstore.decrypt(row["value_enc"]))
        except (secretstore.SecretStoreError, ValueError):
            return None
        files = _credential_files()
        for rel, content in bundle.items():
            path = files.get(rel)
            if path is None:
                continue  # never write outside the known credential set
            if rel == ".claude.json":
                _merge_claude_json(path, content)
            else:
                _write_private(path, content)
        _state.seen_updated_at = row["updated_at"]
        _state.last_fingerprint = fingerprint()
        return "materialized"

    current = fingerprint()
    if current and current != _state.last_fingerprint:
        if upload():
            _state.last_fingerprint = current
            with connection() as conn:
                stored = repo.get_runtime_secret(conn, SECRET_KEY)
            _state.seen_updated_at = stored["updated_at"] if stored else None
            return "uploaded"
    return None
