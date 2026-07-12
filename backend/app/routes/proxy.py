"""Generic proxy endpoint for frontend Cesium requests through xray."""

import logging
from urllib.parse import urlparse
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
import httpx

from app.services.cache import get_cached, set_cache
from app.services.http_client import get_shared_client

logger = logging.getLogger(__name__)
router = APIRouter()
CACHE_TTL = 1800  # 30 minutes

# Domains allowed for proxying (Cesium assets, etc.)
ALLOWED_DOMAINS = [
    "api.cesium.com",
    "assets.cesium.com",
    "ion.cesium.com",
    "tiles.arcgis.com",
    "services.arcgisonline.com",
    "raw.githubusercontent.com",
]


@router.get("/proxy")
async def proxy_get(
    url: str = Query(..., description="Target URL to proxy"),
    request: Request = None,
):
    """Proxy a GET request through xray, with 30-min Redis cache."""
    # Validate URL
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.hostname or ""

    if not domain:
        raise HTTPException(status_code=400, detail="Invalid URL")

    if not any(domain == allowed or domain.endswith("." + allowed) for allowed in ALLOWED_DOMAINS):
        raise HTTPException(status_code=403, detail=f"Domain not allowed: {domain}")

    # Check cache
    cached = await get_cached("proxy", url)
    if cached is not None:
        logger.debug("Proxy cache hit: %s", url[:80])
        body = cached.get("body", "")
        # Body stored as string, encode back to bytes if needed
        if isinstance(body, str):
            body = body.encode("latin-1")
        return Response(
            content=body,
            media_type=cached.get("content_type", "application/octet-stream"),
            status_code=cached.get("status_code", 200),
        )

    # Proxy request
    client = await get_shared_client()
    try:
        # Collect original request headers we want to forward
        forward_headers = {}
        if request:
            for key in ["accept", "accept-encoding", "accept-language", "if-none-match", "if-modified-since"]:
                val = request.headers.get(key)
                if val:
                    forward_headers[key] = val

        resp = await client.get(url, headers=forward_headers, follow_redirects=True)

        # Build response headers (filter hop-by-hop headers)
        resp_headers = {}
        skip = {"transfer-encoding", "connection", "keep-alive", "content-encoding", "content-length"}
        for k, v in resp.headers.items():
            if k.lower() not in skip:
                resp_headers[k] = v

        # Cache the response
        cache_data = {
            "body": resp.content.decode("latin-1"),
            "content_type": resp.headers.get("content-type", "application/octet-stream"),
            "status_code": resp.status_code,
            "headers": resp_headers,
        }
        await set_cache("proxy", url, value=cache_data, ttl=CACHE_TTL)

        return Response(
            content=resp.content,
            media_type=resp.headers.get("content-type"),
            status_code=resp.status_code,
            headers=resp_headers,
        )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Upstream timeout")
    except httpx.ConnectError as e:
        logger.error("Proxy connect error for %s: %s", url[:80], e)
        raise HTTPException(status_code=502, detail=f"Connection failed: {e}")
    except Exception as e:
        logger.error("Proxy error for %s: %s", url[:80], e)
        raise HTTPException(status_code=502, detail=str(e))
