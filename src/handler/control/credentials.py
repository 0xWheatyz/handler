"""Credential resolution + injection (README 3.7).

The database never stores a raw token. ``projects.credential_ref`` is a *pointer* —
``env:VAR_NAME`` / ``file:/path`` / ``cmd:some command`` — mirroring forge's own
``--token-cmd`` pattern one level up. The control layer resolves it to an actual value
only at spawn time and injects it into that one agent's container environment; nothing
is persisted, nothing is baked into an image.

One token, two consumers: ``forge`` reads the resolved token straight from the
environment (``GITHUB_TOKEN`` / ``GITEA_TOKEN`` / ``GITLAB_TOKEN`` per host, plus a
generic ``FORGE_TOKEN``), and git's HTTPS auth reads the same value through a credential
helper we install at spawn (see :func:`credential_env` and
:func:`git_credential_helper_value`).
"""

from __future__ import annotations

import os
import shlex
import subprocess
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from sqlalchemy import Connection

# The env var Handler always injects and that the git credential helper reads back.
CANONICAL_TOKEN_ENV = "FORGE_TOKEN"

# Map a remote-host match -> the token env var that host's forge/CLI conventions expect.
# FORGE_TOKEN is always set too, so an unknown host still works with forge. Matched
# against the parsed hostname (exact, or a dotted suffix) so a repo merely *named*
# "gitea" doesn't misfire.
_HOST_TOKEN_ENV = {
    "github.com": "GITHUB_TOKEN",
    "gitlab.com": "GITLAB_TOKEN",
    "gitea.com": "GITEA_TOKEN",
    "codeberg.org": "GITEA_TOKEN",
    "bitbucket.org": "BITBUCKET_TOKEN",
}
# Substrings that, when present in the hostname itself, imply a self-hosted forge type.
_HOST_HINT_ENV = {"gitea": "GITEA_TOKEN", "forgejo": "GITEA_TOKEN", "gitlab": "GITLAB_TOKEN"}


class CredentialError(Exception):
    """Raised when a ``credential_ref`` cannot be resolved to a value."""


# Schemes an operator may set from the web. ``cmd:`` is deliberately excluded there — it
# executes an arbitrary command in the control container at spawn — so the API rejects it
# while the CLI/DB path still allows it (see api/schemas.py). ``db:`` is reserved for the
# future encrypted secret store (not yet resolvable).
WEB_SETTABLE_SCHEMES = ("env", "file", "db")


def _resolve_env(rest: str) -> str:
    value = os.environ.get(rest)
    if value is None:
        raise CredentialError(f"credential_ref env var '{rest}' is not set")
    return value


def _resolve_file(rest: str) -> str:
    try:
        with open(os.path.expanduser(rest)) as fh:
            return fh.read().strip()
    except OSError as exc:
        raise CredentialError(f"credential_ref file '{rest}' unreadable: {exc}") from exc


def _resolve_cmd(rest: str) -> str:
    try:
        result = subprocess.run(
            shlex.split(rest),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise CredentialError(f"credential_ref cmd '{rest}' failed: {exc}") from exc
    if result.returncode != 0:
        raise CredentialError(
            f"credential_ref cmd '{rest}' exited {result.returncode}: "
            f"{(result.stderr or '').strip()}"
        )
    return result.stdout.strip()


def _resolve_db(rest: str) -> str:
    # Reserved for the encrypted secret store (a later phase); the ``db:`` scheme and this
    # dispatch seam land now so that store is a drop-in without touching every caller.
    raise CredentialError(
        f"credential_ref 'db:{rest}' scheme is reserved for the encrypted secret store, "
        "which is not enabled yet"
    )


# Scheme -> resolver. Adding the encrypted store later means wiring _resolve_db to it,
# nothing else here changes.
_RESOLVERS = {
    "env": _resolve_env,
    "file": _resolve_file,
    "cmd": _resolve_cmd,
    "db": _resolve_db,
}


def resolve(credential_ref: str | None) -> str | None:
    """Resolve a ``credential_ref`` pointer to an actual secret value.

    Returns ``None`` when no ref is configured (a project may not need credentials).
    Raises :class:`CredentialError` when a configured ref cannot be resolved — a
    misconfigured pointer is an error, not a silent "no token".
    """
    if not credential_ref:
        return None
    ref = credential_ref.strip()
    scheme, _, rest = ref.partition(":")
    rest = rest.strip()
    if not rest:
        raise CredentialError(f"credential_ref '{ref}' has no value after '{scheme}:'")

    resolver = _RESOLVERS.get(scheme)
    if resolver is None:
        raise CredentialError(
            f"credential_ref '{ref}' has unknown scheme '{scheme}' "
            "(expected env:, file:, cmd:, or db:)"
        )
    return resolver(rest)


def remote_host(git_remote: str | None) -> str | None:
    """Parse the hostname from an https or scp-style (``git@host:path``) remote."""
    if not git_remote:
        return None
    remote = git_remote.strip()
    if "://" in remote:
        host = urlsplit(remote).hostname
        return host.lower() if host else None
    # scp-style: git@github.com:owner/repo.git
    if "@" in remote and ":" in remote:
        after_at = remote.split("@", 1)[1]
        return after_at.split(":", 1)[0].lower() or None
    return None


def _builtin_host_token_env(host: str) -> str | None:
    for known, env_var in _HOST_TOKEN_ENV.items():
        if host == known or host.endswith("." + known):
            return env_var
    for hint, env_var in _HOST_HINT_ENV.items():
        if hint in host:
            return env_var
    return None


def _host_token_env(git_remote: str | None, conn: Connection | None = None) -> str | None:
    """The per-host token env var for a remote.

    Consults the web-managed ``forge_hosts`` registry first (when a ``conn`` is available),
    so operators can register self-hosted forges without a code change; falls back to the
    built-in map so behaviour is unchanged when no row exists.
    """
    host = remote_host(git_remote)
    if not host:
        return None
    if conn is not None:
        row = _host_row(conn, host)
        if row and row.get("token_env_var"):
            return row["token_env_var"]
    return _builtin_host_token_env(host)


def _host_row(conn: Connection, host: str) -> dict | None:
    # Local import to keep this module import-light and avoid a control<->db import cycle.
    from ..db import repository as repo

    return repo.get_host(conn, host)


def git_credential_config(
    git_remote: str | None, conn: Connection | None = None
) -> tuple[str, str] | None:
    """The scoped git config (key, value) that installs the credential helper.

    Scopes the helper to the forge's HTTPS base URL — ``credential.https://host.helper``
    — so the injected token is only ever offered to that host, never to an arbitrary
    HTTPS URL the agent might touch. A registered host's explicit ``base_url`` wins when
    set. Returns ``None`` for ssh/unknown remotes, where no HTTPS credential helper is
    needed (ssh uses deploy keys).
    """
    if not git_remote or "://" not in git_remote:
        return None
    parts = urlsplit(git_remote.strip())
    if parts.scheme not in ("https", "http") or not parts.hostname:
        return None
    base = f"{parts.scheme}://{parts.hostname}"
    if conn is not None:
        row = _host_row(conn, parts.hostname.lower())
        if row and row.get("base_url"):
            base = row["base_url"].rstrip("/")
    return f"credential.{base}.helper", git_credential_helper_value()


def credential_env(
    token: str | None, git_remote: str | None, conn: Connection | None = None
) -> dict[str, str]:
    """The environment variables to inject so forge + git both authenticate.

    Always sets ``FORGE_TOKEN`` (the generic name forge accepts and our git helper
    reads); additionally sets the host-specific var (``GITHUB_TOKEN`` etc.) when the
    remote host is recognized — via the ``forge_hosts`` registry when a ``conn`` is given,
    otherwise the built-in map — so per-host tooling works with zero extra config.
    """
    if not token:
        return {}
    env = {CANONICAL_TOKEN_ENV: token}
    host_var = _host_token_env(git_remote, conn)
    if host_var:
        env[host_var] = token
    return env


def git_credential_helper_value() -> str:
    """A git ``credential.helper`` value that hands back the injected token.

    Uses an inline shell helper reading ``$FORGE_TOKEN`` from the environment, so the
    raw token lives only in the process environment — never written to disk. The
    username ``x-access-token`` is the conventional throwaway that GitHub and most
    self-hosted forges accept alongside a PAT-as-password.
    """
    return (
        f'!f() {{ echo "username=x-access-token"; echo "password=${CANONICAL_TOKEN_ENV}"; }}; f'
    )
