"""Self-hosted web tools for agents: ``web_search`` and ``web_fetch``.

pi deliberately ships no web tools, and claude's built-in WebSearch/WebFetch are
Anthropic-server-side — they don't exist when the binary is pointed at a local
endpoint. This module is the handler-owned replacement: plain HTTP from the worker
container, no new capability an agent's bash + curl didn't already have, just a
structured tool the model can actually use well.

Search is bring-your-own-provider, resolved in order:

1. ``SEARXNG_URL`` — a SearXNG instance (self-hosted metasearch; set the base URL,
   ``format=json`` must be enabled in its settings).
2. ``BRAVE_SEARCH_API_KEY`` — the Brave Search API.
3. Neither set — DuckDuckGo's HTML endpoint, parsed. Zero-config but rate-limited and
   markup-brittle; fine for occasional agent lookups, configure a real provider for
   heavy use.

Fetch needs no provider: GET the URL, strip the HTML to readable text, cap the size.
Both are exposed to pi via the bridge extension (``python -m handler.webtool <tool>``,
JSON args on stdin — the same seam shape as ``handler.mcpserver --call``).
"""

from __future__ import annotations

import html as html_lib
import json
import re
import urllib.parse

import httpx

_TIMEOUT = 20.0
_UA = "Mozilla/5.0 (X11; Linux x86_64) handler-agent/1.0"
_MAX_FETCH_BYTES = 2 * 1024 * 1024
_DEFAULT_FETCH_CHARS = 20_000
_MAX_RESULTS = 10

TOOLS = ("web_search", "web_fetch")


class WebToolError(Exception):
    """A tool-level failure the caller renders back to the model in-band."""


# ---- html -> text ----------------------------------------------------------------------

_DROP_BLOCKS = re.compile(
    r"<(script|style|noscript|svg|head)\b.*?</\1\s*>", re.IGNORECASE | re.DOTALL
)
_BLOCK_TAGS = re.compile(
    r"</?(p|div|br|li|ul|ol|tr|table|h[1-6]|section|article|blockquote|pre)\b[^>]*>",
    re.IGNORECASE,
)
_TAGS = re.compile(r"<[^>]+>")
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def html_to_text(markup: str) -> tuple[str | None, str]:
    """(title, readable text) from an HTML document — regex-grade readability, which is
    the right weight here: agents want the words, not a perfect DOM."""
    title_match = _TITLE.search(markup)
    title = html_lib.unescape(title_match.group(1)).strip() if title_match else None
    body = _DROP_BLOCKS.sub(" ", markup)
    body = _BLOCK_TAGS.sub("\n", body)
    body = _TAGS.sub(" ", body)
    body = html_lib.unescape(body)
    lines = [" ".join(line.split()) for line in body.splitlines()]
    text = "\n".join(line for line in lines if line)
    return title, text


# ---- search providers --------------------------------------------------------------------


def _searxng_search(base_url: str, query: str, limit: int) -> list[dict]:
    resp = httpx.get(
        f"{base_url.rstrip('/')}/search",
        params={"q": query, "format": "json"},
        headers={"User-Agent": _UA},
        timeout=_TIMEOUT,
        follow_redirects=True,
    )
    resp.raise_for_status()
    results = resp.json().get("results") or []
    return [
        {
            "title": r.get("title") or "",
            "url": r.get("url") or "",
            "snippet": r.get("content") or "",
        }
        for r in results[:limit]
    ]


def _brave_search(api_key: str, query: str, limit: int) -> list[dict]:
    resp = httpx.get(
        "https://api.search.brave.com/res/v1/web/search",
        params={"q": query, "count": limit},
        headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    results = ((resp.json().get("web") or {}).get("results")) or []
    return [
        {
            "title": r.get("title") or "",
            "url": r.get("url") or "",
            "snippet": r.get("description") or "",
        }
        for r in results[:limit]
    ]


_DDG_RESULT = re.compile(
    r'<a[^>]+class="result__a"[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_DDG_SNIPPET = re.compile(
    r'<a[^>]+class="result__snippet"[^>]*>(?P<snippet>.*?)</a>', re.IGNORECASE | re.DOTALL
)


def _ddg_url(href: str) -> str:
    """DDG's result hrefs are redirect links carrying the real URL in ``uddg``."""
    parsed = urllib.parse.urlparse(href, scheme="https")
    if "duckduckgo.com" in (parsed.netloc or "") and parsed.path.startswith("/l/"):
        target = urllib.parse.parse_qs(parsed.query).get("uddg")
        if target:
            return target[0]
    return urllib.parse.urlunparse(parsed)


def _ddg_search(query: str, limit: int) -> list[dict]:
    resp = httpx.get(
        "https://html.duckduckgo.com/html/",
        params={"q": query},
        headers={"User-Agent": _UA},
        timeout=_TIMEOUT,
        follow_redirects=True,
    )
    resp.raise_for_status()
    markup = resp.text
    snippets = [
        " ".join(html_lib.unescape(_TAGS.sub(" ", m.group("snippet"))).split())
        for m in _DDG_SNIPPET.finditer(markup)
    ]
    results = []
    for i, m in enumerate(_DDG_RESULT.finditer(markup)):
        if len(results) >= limit:
            break
        title = " ".join(html_lib.unescape(_TAGS.sub(" ", m.group("title"))).split())
        results.append(
            {
                "title": title,
                "url": _ddg_url(html_lib.unescape(m.group("href"))),
                "snippet": snippets[i] if i < len(snippets) else "",
            }
        )
    return results


# ---- tools ---------------------------------------------------------------------------------


def web_search(args: dict) -> dict:
    from ..config import get_settings

    query = (args.get("query") or "").strip()
    if not query:
        raise WebToolError("query is required")
    limit = min(int(args.get("limit") or 5), _MAX_RESULTS)
    s = get_settings()
    try:
        if s.searxng_url:
            provider = "searxng"
            results = _searxng_search(s.searxng_url, query, limit)
        elif s.brave_search_api_key:
            provider = "brave"
            results = _brave_search(s.brave_search_api_key, query, limit)
        else:
            provider = "duckduckgo"
            results = _ddg_search(query, limit)
    except httpx.HTTPError as exc:
        raise WebToolError(f"search failed ({exc.__class__.__name__}): {exc}") from exc
    return {"provider": provider, "query": query, "results": results}


def web_fetch(args: dict) -> dict:
    url = (args.get("url") or "").strip()
    if not url.startswith(("http://", "https://")):
        raise WebToolError("url must be an http(s) URL")
    max_chars = min(int(args.get("max_chars") or _DEFAULT_FETCH_CHARS), 100_000)
    try:
        with httpx.stream(
            "GET",
            url,
            headers={"User-Agent": _UA},
            timeout=_TIMEOUT,
            follow_redirects=True,
        ) as resp:
            status = resp.status_code
            final_url = str(resp.url)
            content_type = resp.headers.get("content-type", "")
            raw = b""
            for chunk in resp.iter_bytes():
                raw += chunk
                if len(raw) >= _MAX_FETCH_BYTES:
                    break
    except httpx.HTTPError as exc:
        raise WebToolError(f"fetch failed ({exc.__class__.__name__}): {exc}") from exc
    body = raw.decode("utf-8", "replace")
    if "html" in content_type.lower() or "<html" in body[:2000].lower():
        title, text = html_to_text(body)
    else:
        title, text = None, body
    truncated = len(text) > max_chars
    return {
        "url": final_url,
        "status": status,
        "content_type": content_type,
        "title": title,
        "truncated": truncated,
        "text": text[:max_chars],
    }


def call_tool(name: str, args: dict) -> dict:
    handlers = {"web_search": web_search, "web_fetch": web_fetch}
    if name not in handlers:
        raise WebToolError(f"unknown tool '{name}'")
    return handlers[name](args)


def main(argv: list[str]) -> int:
    """CLI seam: ``python -m handler.webtool <tool>`` with JSON args on stdin."""
    import sys

    if len(argv) != 1 or argv[0] not in TOOLS:
        print(f"usage: python -m handler.webtool {{{'|'.join(TOOLS)}}}", file=sys.stderr)
        return 2
    raw = sys.stdin.read()
    try:
        args = json.loads(raw) if raw.strip() else {}
    except ValueError:
        print("invalid JSON arguments on stdin", file=sys.stderr)
        return 2
    try:
        payload = call_tool(argv[0], args if isinstance(args, dict) else {})
    except WebToolError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, ensure_ascii=False))
    return 0
