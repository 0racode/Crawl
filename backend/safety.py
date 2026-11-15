"""URL safety: only public http(s) hosts. Blocks SSRF to private/loopback/link-local ranges."""
from __future__ import annotations

import asyncio
import ipaddress
import os
import socket
from urllib.parse import urlparse

ALLOW_PRIVATE = os.getenv("ALLOW_PRIVATE_HOSTS", "0") == "1"  # only for local testing


class UnsafeURL(ValueError):
    pass


def _is_public(ip: str) -> bool:
    a = ipaddress.ip_address(ip)
    return not (
        a.is_private or a.is_loopback or a.is_link_local or a.is_multicast
        or a.is_reserved or a.is_unspecified
    )


async def assert_public_url(url: str) -> None:
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise UnsafeURL("Only http(s) URLs are allowed")
    if ALLOW_PRIVATE:
        return
    host = p.hostname
    try:
        ipaddress.ip_address(host)
        ips = [host]
    except ValueError:
        loop = asyncio.get_running_loop()
        try:
            infos = await loop.getaddrinfo(host, p.port or (443 if p.scheme == "https" else 80),
                                           type=socket.SOCK_STREAM)
        except socket.gaierror as e:
            raise UnsafeURL(f"Cannot resolve host: {host}") from e
        ips = [i[4][0] for i in infos]
    if not ips or not all(_is_public(ip) for ip in ips):
        raise UnsafeURL("URL resolves to a non-public address")
