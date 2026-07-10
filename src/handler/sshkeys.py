"""Per-git-server SSH deploy keys.

Each registered git server can carry its own ed25519 keypair: the public key is shown
in the dashboard so the operator can paste it into the forge (GitHub deploy key /
account key, Gitea, ...), and the private key is stored encrypted (see ``secretstore``)
and materialized to a 0600 file in the control container only when git actually needs
it. Generation is pure Python (``cryptography``) so the API container needs no
``ssh-keygen`` binary.
"""

from __future__ import annotations

import os
import re

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from .config import get_settings


def generate_keypair(comment: str) -> tuple[str, str]:
    """A fresh ed25519 keypair as (private_key_openssh, public_key_openssh)."""
    key = ed25519.Ed25519PrivateKey.generate()
    private = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.OpenSSH,
        serialization.NoEncryption(),
    ).decode()
    public = key.public_key().public_bytes(
        serialization.Encoding.OpenSSH,
        serialization.PublicFormat.OpenSSH,
    ).decode()
    comment = comment.strip()
    return private, f"{public} {comment}" if comment else public


def _key_path(hostname: str) -> str:
    # One key file per host under <projects_root>/.ssh; the hostname is sanitized so a
    # crafted value can't traverse out of the directory.
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", hostname.strip()) or "_"
    return os.path.join(get_settings().projects_root, ".ssh", safe)


def materialize_private_key(hostname: str, private_key: str) -> str:
    """Write the host's private key to a 0600 file and return its path.

    Idempotent: rewrites the file each call so a rotated key takes effect immediately.
    """
    path = _key_path(hostname)
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    if not private_key.endswith("\n"):
        private_key += "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(private_key)
    return path


def git_ssh_command(key_path: str) -> str:
    """A ``GIT_SSH_COMMAND`` / ``core.sshCommand`` value pinned to the host's key.

    ``IdentitiesOnly`` stops ssh from offering unrelated agent keys;
    ``accept-new`` trusts a host on first contact without ever accepting a *changed*
    host key silently.
    """
    return f"ssh -i {key_path} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
