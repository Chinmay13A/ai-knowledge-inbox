"""PageFetcher tests. Fully offline: httpx.MockTransport serves responses and a fake resolver stands in for DNS."""

import asyncio
from collections.abc import Callable

import httpx
import pytest

from app.errors import (
    EmptyContentError,
    RobotsDisallowedError,
    UnsupportedContentError,
    UrlFetchError,
    UrlFetchTimeoutError,
    UrlNotAllowedError,
)
from app.services.fetcher import FetchedPage, PageFetcher, is_public_address

PUBLIC_IP = "93.184.216.34"

ARTICLE_HTML = """
<html>
  <head><title>Retrieval-augmented generation</title></head>
  <body>
    <nav><a href="/">Home</a> | <a href="/about">About us</a> | <a href="/login">Log in</a></nav>
    <article>
      <h1>Retrieval-augmented generation</h1>
      <p>Retrieval-augmented generation (RAG) is a technique that lets a language model answer
      questions using documents it retrieves at query time instead of relying only on its training data.</p>
      <p>A typical pipeline splits documents into chunks, embeds them as vectors, finds the chunks most
      similar to the question and passes them to the model together with the question.</p>
      <p>Because answers are grounded in retrieved text, the system can cite its sources and stay up to date.</p>
    </article>
    <footer>Copyright 2026 Example Corp. All rights reserved.</footer>
  </body>
</html>
"""

Handler = Callable[[httpx.Request], httpx.Response]


def html(body: str, status: int = 200) -> httpx.Response:
    return httpx.Response(status, text=body, headers={"Content-Type": "text/html; charset=utf-8"})


def robots(rules: str) -> httpx.Response:
    return httpx.Response(200, text=rules, headers={"Content-Type": "text/plain"})


def site(pages: dict[str, httpx.Response | Exception], requested: list[str] | None = None) -> Handler:
    """Mock transport handler: serves `pages` by path; robots.txt is 404 unless given."""

    def handle(request: httpx.Request) -> httpx.Response:
        if requested is not None:
            requested.append(request.url.path)
        result = pages.get(request.url.path) or pages.get(str(request.url))
        if result is None:
            return httpx.Response(404)
        if isinstance(result, Exception):
            raise result
        return result

    return handle


def make_fetcher(handler: Handler, hosts: dict[str, list[str]] | None = None, **kwargs) -> PageFetcher:
    async def resolver(host: str) -> list[str]:
        if host.endswith(".invalid"):
            raise OSError("Name or service not known")
        return (hosts or {}).get(host, [PUBLIC_IP])

    return PageFetcher(transport=httpx.MockTransport(handler), resolver=resolver, **kwargs)


def fetch(fetcher: PageFetcher, url: str = "https://example.com/article") -> FetchedPage:
    return asyncio.run(fetcher.fetch(url))


class TestExtraction:
    def test_html_article_title_and_main_text(self) -> None:
        page = fetch(make_fetcher(site({"/article": html(ARTICLE_HTML)})))

        assert page.title == "Retrieval-augmented generation"
        assert "lets a language model answer" in page.text
        assert "cite its sources" in page.text
        assert "Log in" not in page.text
        assert "All rights reserved" not in page.text
        assert page.url == "https://example.com/article"

    def test_short_page_falls_back_to_full_text(self) -> None:
        page = fetch(make_fetcher(site({"/article": html("<html><body><p>Tiny page.</p></body></html>")})))

        assert page.text == "Tiny page."
        assert page.title is None

    def test_plain_text_is_used_as_is(self) -> None:
        response = httpx.Response(200, text="Just text.\nTwo lines.", headers={"Content-Type": "text/plain"})

        page = fetch(make_fetcher(site({"/article": response})))

        assert page.text == "Just text.\nTwo lines."

    def test_page_without_text_is_rejected(self) -> None:
        with pytest.raises(EmptyContentError):
            fetch(make_fetcher(site({"/article": html("<html><body><script>app()</script></body></html>")})))


class TestLimitsAndErrors:
    def test_unsupported_content_type(self) -> None:
        pdf = httpx.Response(200, content=b"%PDF-1.7", headers={"Content-Type": "application/pdf"})

        with pytest.raises(UnsupportedContentError, match="application/pdf"):
            fetch(make_fetcher(site({"/article": pdf})))

    def test_body_over_limit(self) -> None:
        with pytest.raises(UnsupportedContentError, match="larger than"):
            fetch(make_fetcher(site({"/article": html("x" * 2_000)}), max_bytes=1_000))

    @pytest.mark.parametrize("status", [404, 500])
    def test_upstream_error_status(self, status: int) -> None:
        with pytest.raises(UrlFetchError, match=f"Site responded with {status}"):
            fetch(make_fetcher(site({"/article": httpx.Response(status)})))

    def test_connection_error(self) -> None:
        with pytest.raises(UrlFetchError, match="Could not connect"):
            fetch(make_fetcher(site({"/article": httpx.ConnectError("refused")})))

    def test_timeout(self) -> None:
        with pytest.raises(UrlFetchTimeoutError):
            fetch(make_fetcher(site({"/article": httpx.ReadTimeout("slow")})))


class TestSsrfGuard:
    @pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.5", "192.168.1.10", "169.254.169.254", "::1"])
    def test_private_addresses_are_blocked(self, address: str) -> None:
        fetcher = make_fetcher(site({"/article": html(ARTICLE_HTML)}), hosts={"example.com": [address]})

        with pytest.raises(UrlNotAllowedError, match="private or internal"):
            fetch(fetcher)

    def test_unresolvable_host_is_blocked(self) -> None:
        with pytest.raises(UrlNotAllowedError, match="Could not resolve"):
            fetch(make_fetcher(site({})), "https://does-not-exist.invalid/")

    def test_redirect_to_private_host_is_blocked(self) -> None:
        handler = site(
            {
                "https://example.com/article": httpx.Response(302, headers={"Location": "http://internal.local/admin"}),
                "/admin": html(ARTICLE_HTML),
            }
        )
        fetcher = make_fetcher(handler, hosts={"internal.local": ["10.0.0.7"]})

        with pytest.raises(UrlNotAllowedError):
            fetch(fetcher)

    def test_redirect_to_public_host_returns_final_url(self) -> None:
        handler = site(
            {
                "https://example.com/article": httpx.Response(301, headers={"Location": "https://www.example.org/post"}),
                "/post": html(ARTICLE_HTML),
            }
        )

        page = fetch(make_fetcher(handler))

        assert page.url == "https://www.example.org/post"

    @pytest.mark.parametrize(
        ("address", "public"),
        [("8.8.8.8", True), ("10.1.2.3", False), ("::ffff:127.0.0.1", False), ("224.0.0.1", False)],
    )
    def test_is_public_address(self, address: str, public: bool) -> None:
        assert is_public_address(address) is public


class TestRobotsTxt:
    def test_disallow_all_blocks_without_fetching_page(self) -> None:
        requested: list[str] = []
        handler = site({"/robots.txt": robots("User-agent: *\nDisallow: /"), "/article": html(ARTICLE_HTML)}, requested)

        with pytest.raises(RobotsDisallowedError):
            fetch(make_fetcher(handler))
        assert requested == ["/robots.txt"]

    def test_rules_for_our_bot_apply(self) -> None:
        rules = "User-agent: AIKnowledgeInbox\nDisallow: /private/\n\nUser-agent: *\nAllow: /"
        handler = site({"/robots.txt": robots(rules), "/article": html(ARTICLE_HTML), "/private/x": html(ARTICLE_HTML)})
        fetcher = make_fetcher(handler)

        assert fetch(fetcher, "https://example.com/article").title
        with pytest.raises(RobotsDisallowedError):
            fetch(fetcher, "https://example.com/private/x")

    def test_rules_for_other_bots_do_not_apply(self) -> None:
        rules = "User-agent: GPTBot\nDisallow: /"
        handler = site({"/robots.txt": robots(rules), "/article": html(ARTICLE_HTML)})

        assert fetch(make_fetcher(handler)).title

    @pytest.mark.parametrize(
        "robots_result",
        [httpx.Response(404), httpx.Response(500), httpx.ReadTimeout("slow"), httpx.ConnectError("refused")],
    )
    def test_missing_or_unavailable_robots_allows_fetch(self, robots_result: httpx.Response | Exception) -> None:
        handler = site({"/robots.txt": robots_result, "/article": html(ARTICLE_HTML)})

        assert fetch(make_fetcher(handler)).title

    def test_check_can_be_disabled(self) -> None:
        requested: list[str] = []
        handler = site({"/robots.txt": robots("User-agent: *\nDisallow: /"), "/article": html(ARTICLE_HTML)}, requested)

        page = fetch(make_fetcher(handler, respect_robots_txt=False))

        assert page.title
        assert requested == ["/article"]
