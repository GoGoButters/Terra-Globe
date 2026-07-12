"""HTTP client factory with SOCKS5 proxy support and caching."""

import logging
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def get_http_client(*, timeout: float = 30.0) -> httpx.AsyncClient:
    """Create an httpx AsyncClient routed through the SOCKS5 proxy if configured."""
    kwargs: dict = {"timeout": httpx.Timeout(timeout)}
    proxy_url = settings.all_proxy
    if proxy_url:
        # httpx expects socks5:// scheme for SOCKS5 proxy
        if proxy_url.startswith("socks5://") or proxy_url.startswith("socks5h://"):
            kwargs["proxy"] = proxy_url
            logger.debug("Using SOCKS5 proxy: %s", proxy_url)
        else:
            kwargs["proxy"] = proxy_url
    return httpx.AsyncClient(**kwargs)


# Singleton client for reuse
_client: Optional[httpx.AsyncClient] = None


async def get_shared_client() -> httpx.AsyncClient:
    """Get or create a shared httpx client (reuse connection pool)."""
    global _client
    if _client is None or _client.is_closed:
        _client = get_http_client()
    return _client


async def close_shared_client():
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
