"""World Bank API data fetcher.

Fetches economic indicators from the World Bank REST API.
API docs: https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api-documentation
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import IndicatorDefinition, IndicatorValue, APICache

settings = get_settings()

# World Bank indicator codes mapped to our internal codes
WB_INDICATORS = {
    "gdp": "NY.GDP.MKTP.CD",
    "gdp_per_capita": "NY.GDP.PCAP.CD",
    "pop": "SP.POP.TOTL",
    "inflation": "FP.CPI.TOTL.ZG",
    "unemployment": "SL.UEM.TOTL.ZS",
    "gini": "SI.POV.GINI",
    "life_expectancy": "SP.DYN.LE00.IN",
    "literacy": "SE.ADT.LITR.ZS",
    "military_budget": "MS.MIL.XPND.CD",
    "military_power": "MS.MIL.TOTL.TF",  # Armed forces personnel
}

WB_API_BASE = "https://api.worldbank.org/v2"
CACHE_TTL_HOURS = 24


async def _get_cached(cache_key: str, db: AsyncSession) -> Optional[dict]:
    """Check cache for a World Bank API response."""
    result = await db.execute(
        select(APICache).where(
            APICache.source == "worldbank",
            APICache.cache_key == cache_key,
            APICache.expires_at > datetime.now(timezone.utc),
        )
    )
    cached = result.scalar_one_or_none()
    if cached:
        return cached.response_data
    return None


async def _set_cache(cache_key: str, data: dict, db: AsyncSession) -> None:
    """Store World Bank API response in cache."""
    # Delete old cache entry
    await db.execute(
        delete(APICache).where(
            APICache.source == "worldbank",
            APICache.cache_key == cache_key,
        )
    )

    entry = APICache(
        source="worldbank",
        cache_key=cache_key,
        response_data=data,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=CACHE_TTL_HOURS),
    )
    db.add(entry)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def _fetch_wb_indicator(indicator_code: str, country_code: str = "all") -> list:
    """Fetch indicator data from World Bank API with retry."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{WB_API_BASE}/country/{country_code}/indicator/{indicator_code}",
            params={
                "format": "json",
                "per_page": 500,
                "date": "2000:2030",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        # WB returns [metadata, [data...]]
        if isinstance(data, list) and len(data) >= 2:
            return data[1]
        return []


async def fetch_indicator(
    our_code: str, db: AsyncSession, iso3_list: Optional[list[str]] = None
) -> list[dict]:
    """Fetch a single indicator from World Bank and store in DB.

    Returns list of {iso3, year, value} dicts.
    """
    wb_code = WB_INDICATORS.get(our_code)
    if not wb_code:
        return []

    cache_key = f"indicator/{wb_code}"
    cached = await _get_cached(cache_key, db)
    if cached:
        data = cached
    else:
        # Filter countries if provided
        country_param = "all"
        if iso3_list:
            # WB API supports semicolon-separated country codes
            country_param = ";".join(iso3_list[:10])  # Limit to avoid URL length issues

        data = await _fetch_wb_indicator(wb_code, country_param)
        await _set_cache(cache_key, data, db)

    results = []
    for entry in data:
        if not entry or not entry.get("date") or not entry.get("value"):
            continue

        country_iso3 = entry.get("countryiso3code", "")
        year = int(entry["date"])
        value = float(entry["value"])

        results.append({"iso3": country_iso3, "year": year, "value": value})

    return results


async def fetch_all_indicators(
    db: AsyncSession, iso3_list: Optional[list[str]] = None
) -> int:
    """Fetch all mapped indicators from World Bank.

    Returns total number of values stored.
    """
    total = 0

    # Ensure indicator definitions exist
    for our_code, wb_code in WB_INDICATORS.items():
        existing = await db.execute(
            select(IndicatorDefinition).where(IndicatorDefinition.code == our_code)
        )
        if not existing.scalar_one_or_none():
            defn = IndicatorDefinition(
                code=our_code,
                name=our_code.replace("_", " ").title(),
                source="worldbank",
                source_code=wb_code,
                source_url=f"https://data.worldbank.org/indicator/{wb_code}",
                display_type="gradient",
            )
            db.add(defn)

    # Fetch each indicator
    for our_code in WB_INDICATORS:
        try:
            values = await fetch_indicator(our_code, db, iso3_list)
            for v in values:
                # Upsert
                existing = await db.execute(
                    select(IndicatorValue).where(
                        IndicatorValue.country_iso3 == v["iso3"],
                        IndicatorValue.indicator_code == our_code,
                        IndicatorValue.year == v["year"],
                    )
                )
                iv = existing.scalar_one_or_none()
                if iv:
                    iv.value = v["value"]
                else:
                    iv = IndicatorValue(
                        country_iso3=v["iso3"],
                        indicator_code=our_code,
                        year=v["year"],
                        value=v["value"],
                    )
                    db.add(iv)
                total += 1
        except Exception as e:
            print(f"  Error fetching {our_code}: {e}")

    return total
