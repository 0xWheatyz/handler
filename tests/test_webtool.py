"""The agents' web tools (``handler.webtool``): provider selection, result shaping,
HTML-to-text, the fetch cap, and the stdin/stdout CLI seam the pi bridge shells to.
All HTTP is mocked with respx — no live network."""

from __future__ import annotations

import io
import json

import httpx
import pytest
import respx

from handler import webtool

DDG_HTML = """
<html><body>
<a rel="nofollow" class="result__a"
   href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fdocs&amp;rut=abc">Example
   <b>Docs</b></a>
<a class="result__snippet" href="#">The official <b>docs</b> for Example.</a>
<a rel="nofollow" class="result__a" href="https://other.example.org/page">Other page</a>
<a class="result__snippet" href="#">Another snippet.</a>
</body></html>
"""


@pytest.fixture
def clean_settings(env):
    """The env fixture already resets the settings cache; just be explicit that the
    provider env vars are unset unless a test sets them."""
    return env


@respx.mock
def test_search_falls_back_to_duckduckgo(clean_settings):
    respx.get("https://html.duckduckgo.com/html/").mock(
        return_value=httpx.Response(200, text=DDG_HTML)
    )
    out = webtool.web_search({"query": "example docs"})
    assert out["provider"] == "duckduckgo"
    assert out["results"][0]["title"] == "Example Docs"
    # The redirect wrapper is unwrapped to the real target URL.
    assert out["results"][0]["url"] == "https://example.com/docs"
    assert "official docs" in out["results"][0]["snippet"]
    assert out["results"][1]["url"] == "https://other.example.org/page"


@respx.mock
def test_search_prefers_searxng_when_configured(clean_settings, monkeypatch):
    from handler import config

    monkeypatch.setenv("SEARXNG_URL", "http://searx.lan:8080")
    config.get_settings.cache_clear()
    respx.get("http://searx.lan:8080/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {"title": "T", "url": "https://t.example", "content": "snippet"},
                ]
            },
        )
    )
    out = webtool.web_search({"query": "q", "limit": 3})
    assert out["provider"] == "searxng"
    assert out["results"] == [
        {"title": "T", "url": "https://t.example", "snippet": "snippet"}
    ]


@respx.mock
def test_search_uses_brave_with_key(clean_settings, monkeypatch):
    from handler import config

    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "brave-key")
    config.get_settings.cache_clear()
    route = respx.get("https://api.search.brave.com/res/v1/web/search").mock(
        return_value=httpx.Response(
            200,
            json={"web": {"results": [{"title": "B", "url": "https://b", "description": "d"}]}},
        )
    )
    out = webtool.web_search({"query": "q"})
    assert out["provider"] == "brave"
    assert route.calls[0].request.headers["X-Subscription-Token"] == "brave-key"
    assert out["results"][0]["snippet"] == "d"


def test_search_requires_query(clean_settings):
    with pytest.raises(webtool.WebToolError):
        webtool.web_search({"query": "  "})


@respx.mock
def test_search_provider_error_is_tool_error(clean_settings):
    respx.get("https://html.duckduckgo.com/html/").mock(side_effect=httpx.ConnectError)
    with pytest.raises(webtool.WebToolError, match="search failed"):
        webtool.web_search({"query": "q"})


@respx.mock
def test_fetch_strips_html_and_caps_text(clean_settings):
    page = (
        "<html><head><title>My &amp; Page</title><style>b{}</style></head>"
        "<body><h1>Header</h1><p>Hello <b>world</b>.</p><script>evil()</script></body></html>"
    )
    respx.get("https://example.com/a").mock(
        return_value=httpx.Response(200, text=page, headers={"content-type": "text/html"})
    )
    out = webtool.web_fetch({"url": "https://example.com/a"})
    assert out["title"] == "My & Page"
    assert "Header" in out["text"] and "Hello world" in out["text"]
    assert "evil" not in out["text"]

    out = webtool.web_fetch({"url": "https://example.com/a", "max_chars": 1000})
    assert len(out["text"]) <= 1000


@respx.mock
def test_fetch_passes_plain_text_through(clean_settings):
    respx.get("https://example.com/raw").mock(
        return_value=httpx.Response(200, text="plain body", headers={"content-type": "text/plain"})
    )
    out = webtool.web_fetch({"url": "https://example.com/raw"})
    assert out["text"] == "plain body"
    assert out["title"] is None


def test_fetch_rejects_non_http(clean_settings):
    with pytest.raises(webtool.WebToolError, match="http"):
        webtool.web_fetch({"url": "file:///etc/passwd"})


@respx.mock
def test_cli_seam_round_trip(clean_settings, monkeypatch, capsys):
    respx.get("https://html.duckduckgo.com/html/").mock(
        return_value=httpx.Response(200, text=DDG_HTML)
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"query": "example"})))
    assert webtool.main(["web_search"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["provider"] == "duckduckgo"

    monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
    assert webtool.main(["web_search"]) == 1  # missing query -> tool error, exit 1
    assert webtool.main(["nope"]) == 2
