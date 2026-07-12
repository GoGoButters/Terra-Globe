"""Redis cache layer with 30-minute TTL for external API responses."""

import hashlib
import json
import logging
from typing import Optional, Any

import redis.asyncio as redis

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

CACHE_TTL = 1800  # 30 minutes

_pool: Optional[redis.ConnectionPool] = None


async def get_redis() -> redis.Redis:
    global _pool
    if _pool is None:
        _pool = redis.ConnectionPool.from_url(
            settings.redis_url,
            max_connections=10,
            decode_responses=False,
        )
    return redis.Redis(connection_pool=_pool)


def _cache_key(prefix: str, *parts: str) -> str:
    """Generate a deterministic cache key."""
    raw = ":".join(parts)
    h = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"tg:{prefix}:{h}"


async def get_cached(prefix: str, *key_parts: str) -> Optional[Any]:
    """Get cached value. Returns None on miss or error."""
    try:
        r = await get_redis()
        key = _cache_key(prefix, *key_parts)
        data = await r.get(key)
        if data:
            return json.loads(data)
    except Exception:
        logger.debug("Cache get failed", exc_info=True)
    return None


async def set_cache(prefix: str, *key_parts: str, value: Any, ttl: int = CACHE_TTL) -> None:
    """Set cached value with TTL."""
    try:
        r = await get_redis()
        key = _cache_key(prefix, *key_parts)
        await r.setex(key, ttl, json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        logger.debug("Cache set failed", exc_info=True)


async def invalidate_prefix(prefix: str) -> None:
    """Invalidate all cached entries with a given prefix."""
    try:
        r = await get_redis()
        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor, match=f"tg:{prefix}:*", count=100)
            if keys:
                await r.delete(*keys)
            if cursor == 0:
                break
    except Exception:
        logger.debug("Cache invalidate failed", exc_info=True)
