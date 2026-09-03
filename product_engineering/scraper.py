"""Conservative public-page fetching and semantic HTML extraction."""

from __future__ import annotations

import gzip
import ipaddress
import re
import socket
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Any


MAX_PAGE_BYTES = 2_000_000


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lang: str | None = None
        self.description: str | None = None
        self.title_parts: list[str] = []
        self.headings: dict[str, list[str]] = {"h1": [], "h2": [], "h3": [], "h4": []}
        self._capture: str | None = None
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attributes = {name.lower(): value for name, value in attrs}
        if tag == "html" and attributes.get("lang"):
            self.lang = attributes["lang"]
        elif tag == "meta":
            name = (attributes.get("name") or "").lower()
            prop = (attributes.get("property") or "").lower()
            if name == "description" or prop == "og:description":
                content = attributes.get("content")
                if content and not self.description:
                    self.description = _clean(content)
        elif tag == "title" or tag in self.headings:
            self._capture = tag
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag != self._capture:
            return
        value = _clean(" ".join(self._buffer))
        if value:
            if tag == "title":
                self.title_parts.append(value)
            else:
                self.headings[tag].append(value)
        self._capture = None
        self._buffer = []


def parse_html(html: str, *, url: str) -> dict[str, Any]:
    parser = PageParser()
    parser.feed(html)
    parser.close()

    headings = {
        key: list(dict.fromkeys(values))[:30]
        for key, values in parser.headings.items()
    }
    return {
        "url": url,
        "title": _clean(" ".join(parser.title_parts)) or None,
        "description": parser.description,
        "lang": parser.lang,
        **headings,
    }


def _validate_public_url(url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"Only absolute HTTP(S) URLs are allowed: {url}")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing credentials are not allowed")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"Cannot resolve host {parsed.hostname}") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ValueError(f"Non-public destination is not allowed: {ip}")


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> Any:
        _validate_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_page(url: str, *, timeout: float = 20.0) -> dict[str, Any]:
    _validate_public_url(url)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; ProductEngineeringResearch/1.0; "
                "+https://openai.com/)"
            ),
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip",
        },
    )
    opener = urllib.request.build_opener(SafeRedirectHandler())
    with opener.open(request, timeout=timeout) as response:
        final_url = response.geturl()
        _validate_public_url(final_url)
        content_type = response.headers.get_content_type()
        if content_type not in {"text/html", "application/xhtml+xml"}:
            raise ValueError(f"Expected HTML from {url}, got {content_type}")
        raw = response.read(MAX_PAGE_BYTES + 1)
        if len(raw) > MAX_PAGE_BYTES:
            raise ValueError(f"HTML response exceeds {MAX_PAGE_BYTES} bytes")
        if response.headers.get("Content-Encoding", "").lower() == "gzip":
            raw = gzip.decompress(raw)
            if len(raw) > MAX_PAGE_BYTES:
                raise ValueError(f"Decompressed HTML exceeds {MAX_PAGE_BYTES} bytes")
        charset = response.headers.get_content_charset() or "utf-8"
        html = raw.decode(charset, errors="replace")
    parsed = parse_html(html, url=final_url)
    parsed["requested_url"] = url
    return parsed
