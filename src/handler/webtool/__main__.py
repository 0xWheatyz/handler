"""``python -m handler.webtool <web_search|web_fetch>`` — JSON args in, JSON result out."""

from __future__ import annotations

import sys

from . import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
