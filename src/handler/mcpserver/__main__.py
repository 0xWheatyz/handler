"""``python -m handler.mcpserver`` — run the bundled handler-memory MCP server."""

from __future__ import annotations

import sys

from . import serve

if __name__ == "__main__":
    sys.exit(serve())
