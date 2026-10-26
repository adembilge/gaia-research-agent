"""Bounded public-URL downloads. Every redirect is validated before following it."""

import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import httpx

MAX_DOWNLOAD = 25 * 1024 * 1024


def validate_public_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only public http(s) URLs are supported.")
    if parsed.username or parsed.password or parsed.port not in {None, 80, 443}:
        raise ValueError("Credentials and nonstandard ports are not allowed in URLs.")
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError("Private, local, and reserved network addresses are blocked.")
    return url


def fetch_url(url: str, max_bytes: int = MAX_DOWNLOAD) -> tuple[bytes, str, str]:
    with httpx.Client(
        timeout=30, follow_redirects=False, headers={"User-Agent": "CourseResearchAgent/1.0"}
    ) as client:
        for _ in range(6):
            validate_public_url(url)
            with client.stream("GET", url) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    url = urljoin(url, response.headers["location"])
                    continue
                response.raise_for_status()
                if int(response.headers.get("content-length", 0)) > max_bytes:
                    raise ValueError("Download exceeds the size limit.")
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > max_bytes:
                        raise ValueError("Download exceeds the size limit.")
                return bytes(data), response.headers.get("content-type", ""), str(response.url)
    raise ValueError("Too many redirects.")
