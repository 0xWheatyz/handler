"""Handler — remote control wrapper for Claude Code agents.

See README.md for the full design. Phase 1 (this package) is the control layer +
API: a centralized database, a stateless HTTP read API, a tmux + ``claude`` control
layer as the sole writer, and hook-enforced test/push gates.
"""

__version__ = "0.1.0"
