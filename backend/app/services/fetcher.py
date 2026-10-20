"""Server-side page fetching: safety checks, robots.txt, download limits and text extraction."""

import asyncio
import ipaddress
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
import trafilatura

from app.errors import (
    EmptyContentError,
    RobotsDisallowedError,
    UnsupportedContentError,
    UrlFetchError,
    UrlFetchTimeoutError,
    UrlNotAllowedError,
)

USER_AGENT = "AIKnowledgeInbox/0.1"
HTML_CONTENT_TYPES = {"text/html", "application/xhtml+xml"}
TEXT_CONTENT_TYPES = {"text/plain"}
MAX_TEXT_CHARS = 100_000
ROBOTS_MAX_BYTES = 500_000

HostResolver = Callable[[str], Awaitable[list[str]]]
ResponseCheck = Callable[[httpx.Response], None]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FetchedPage:
    url: str  # final URL after redirects
    title: str | None
    text: str


async def resolve_host(host: str) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, None)
    return [info[4][0] for info in infos]


def is_public_address(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%", 1)[0])  # drop IPv6 zone index
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


class PageFetcher:
    def __init__(
        self,
        *,
        timeout_s: float = 10.0,
        max_bytes: int = 5_000_000,
        max_redirects: int = 5,
        respect_robots_txt: bool = True,
        transport: httpx.AsyncBaseTransport | None = None,
        resolver: HostResolver = resolve_host,
    ) -> None:
        self._timeout_s = timeout_s
        self._max_bytes = max_bytes
        self._max_redirects = max_redirects
        self._respect_robots_txt = respect_robots_txt
        self._transport = transport
        self._resolver = resolver

    async def fetch(self, url: str) -> FetchedPage:
        start = time.perf_counter()
        async with self._client() as client:
            if self._respect_robots_txt:
                await self._check_robots(client, url)
            response, body = await self._download(client, url, self._max_bytes, self._check_page_response)

        text, title = _extract(body, response)
        if len(text) > MAX_TEXT_CHARS:
            logger.info("fetch.truncated", extra={"url": url, "text_chars": len(text)})
            text = text[:MAX_TEXT_CHARS]

        logger.info(
            "fetch.completed",
            extra={
                "url": url,
                "final_url": str(response.url),
                "status_code": response.status_code,
                "bytes": len(body),
                "text_chars": len(text),
                "duration_ms": round((time.perf_counter() - start) * 1000, 2),
            },
        )
        return FetchedPage(url=str(response.url), title=title, text=text)

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=self._transport,
            timeout=self._timeout_s,
            follow_redirects=True,
            max_redirects=self._max_redirects,
            headers={"User-Agent": USER_AGENT},
            # Runs before every request, including each redirect hop.
            event_hooks={"request": [self._ensure_public_target]},
        )

    async def _ensure_public_target(self, request: httpx.Request) -> None:
        """SSRF guard: never let user-supplied URLs reach internal or private hosts."""
        if request.url.scheme not in ("http", "https"):
            raise UrlNotAllowedError("Only http and https URLs are supported")
        host = request.url.host
        try:
            addresses = await self._resolver(host)
        except OSError:
            raise UrlNotAllowedError(f"Could not resolve host '{host}'") from None
        if not addresses or not all(is_public_address(address) for address in addresses):
            raise UrlNotAllowedError("URLs pointing to private or internal addresses are not allowed")

    async def _check_robots(self, client: httpx.AsyncClient, url: str) -> None:
        parts = urlsplit(url)
        robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
        try:
            response, body = await self._download(client, robots_url, ROBOTS_MAX_BYTES)
        except (UrlFetchError, UrlFetchTimeoutError, UnsupportedContentError) as exc:
            # Deliberately lenient: an unreadable robots.txt does not block the user's request.
            logger.warning("fetch.robots_unavailable", extra={"robots_url": robots_url, "reason": exc.message})
            return

        if 400 <= response.status_code < 500:
            return  # no robots.txt (or not accessible) means no restrictions (RFC 9309)
        if response.status_code >= 500:
            logger.warning(
                "fetch.robots_unavailable",
                extra={"robots_url": robots_url, "reason": f"status {response.status_code}"},
            )
            return

        parser = RobotFileParser()
        parser.parse(body.decode("utf-8", errors="replace").splitlines())
        if not parser.can_fetch(USER_AGENT, url):
            logger.info("fetch.robots_blocked", extra={"url": url})
            raise RobotsDisallowedError("This site does not allow automated access to this page (robots.txt)")

    async def _download(
        self,
        client: httpx.AsyncClient,
        url: str,
        max_bytes: int,
        check_response: ResponseCheck | None = None,
    ) -> tuple[httpx.Response, bytes]:
        """GET `url`, validating headers before reading and stopping at `max_bytes`."""
        try:
            async with client.stream("GET", url) as response:
                if check_response:
                    check_response(response)
                declared = int(response.headers.get("Content-Length") or 0)
                if declared > max_bytes:
                    raise UnsupportedContentError(_too_large_message(max_bytes))
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise UnsupportedContentError(_too_large_message(max_bytes))
                    chunks.append(chunk)
                return response, b"".join(chunks)
        except httpx.TimeoutException:
            raise UrlFetchTimeoutError(f"The site did not respond within {self._timeout_s:g} seconds") from None
        except httpx.TooManyRedirects:
            raise UrlFetchError("The site redirected too many times") from None
        except httpx.HTTPError:
            raise UrlFetchError("Could not connect to the site") from None

    @staticmethod
    def _check_page_response(response: httpx.Response) -> None:
        if response.status_code >= 400:
            raise UrlFetchError(f"Site responded with {response.status_code}")
        content_type = _content_type(response)
        if content_type and content_type not in HTML_CONTENT_TYPES | TEXT_CONTENT_TYPES:
            raise UnsupportedContentError(
                f"Unsupported content type '{content_type}'; only HTML and plain-text pages are supported"
            )


def _extract(body: bytes, response: httpx.Response) -> tuple[str, str | None]:
    """Returns (text, title). Raises EmptyContentError if nothing readable is found."""
    if _content_type(response) in TEXT_CONTENT_TYPES:
        text, title = body.decode(response.encoding or "utf-8", errors="replace"), None
    else:
        # trafilatura keeps the main content and drops navigation, ads and footers;
        # html2txt is a fallback for short pages the main-content heuristics skip.
        text = trafilatura.extract(body, include_comments=False, include_tables=True) or trafilatura.html2txt(body)
        metadata = trafilatura.extract_metadata(body)
        title = metadata.title if metadata and metadata.title else None

    text = (text or "").strip()
    if not text:
        raise EmptyContentError("No readable text found on the page (it may require JavaScript)")
    return text, title


def _content_type(response: httpx.Response) -> str:
    return response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()


def _too_large_message(max_bytes: int) -> str:
    return f"Page is larger than {max_bytes / 1_000_000:g} MB"
