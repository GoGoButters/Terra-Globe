"""IMF SDMX API data fetcher.

Fetches economic indicators from IMF SDMX REST API.
API docs: https://datahelp.imf.org/knowledgebase/articles/1726777-sdmx-rest-web-service
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
import xml.etree.ElementTree as ET

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IndicatorDefinition, IndicatorValue, APICache

logger = logging.getLogger(__name__)

IMF_API_BASE = "https://sdmxcentral.imf.org/ws/public/sdmxapi/rest"
CACHE_TTL_HOURS = 24

# IMF data flows and key codes
IMF_INDICATORS = {
    "gdp_growth": {
        "flow": "IFS",
        "key": "A.5A.NGDP_R_PDPC",  # Real GDP growth
        "name": "GDP Growth Rate",
    },
    "government_debt": {
        "flow": "WEO",
        "key": "A.5N.NGGDPGDPS_NGDP",  # Government debt to GDP
        "name": "Government Debt to GDP",
    },
    "current_account": {
        "flow": "WEO",
        "key": "A.5N.BCA_NGDPD",  # Current account balance
        "name": "Current Account Balance",
    },
    "reserves": {
        "flow": "IFS",
        "key": "A.5A.NRA_NGDP",  # International reserves
        "name": "International Reserves",
    },
}


async def _get_cached(cache_key: str, db: AsyncSession) -> Optional[dict]:
    """Check cache for an IMF response."""
    result = await db.execute(
        select(APICache).where(
            APICache.source == "imf",
            APICache.cache_key == cache_key,
            APICache.expires_at > datetime.now(timezone.utc),
        )
    )
    cached = result.scalar_one_or_none()
    return cached.response_data if cached else None


async def _set_cache(cache_key: str, data: dict, db: AsyncSession) -> None:
    """Store IMF response in cache."""
    await db.execute(
        delete(APICache).where(
            APICache.source == "imf",
            APICache.cache_key == cache_key,
        )
    )
    entry = APICache(
        source="imf",
        cache_key=cache_key,
        response_data=data,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=CACHE_TTL_HOURS),
    )
    db.add(entry)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=3, max=15))
async def _fetch_imf_data(flow: str, key: str) -> Optional[list[dict]]:
    """Fetch data from IMF SDMX API.

    Returns list of {iso3, year, value} dicts.
    """
    # SDMX REST URL: /data/{dataflow}/{key}
    url = f"{IMF_API_BASE}/data/{flow}/{key}"
    params = {
        "startPeriod": "2000",
        "endPeriod": "2030",
        "format": "sdmx-2.1",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=params)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()

        # Parse SDMX XML response
        try:
            root = ET.fromstring(resp.text)
            return _parse_sdmx_xml(root)
        except ET.ParseError:
            return None


def _parse_sdmx_xml(root: ET.Element) -> list[dict]:
    """Parse SDMX XML response into list of {iso3, year, value} dicts."""
    results = []

    # SDMX 2.1 structure: <message:GenericData> -> <generic:DataSet> -> <generic:Series> -> <generic:Obs>
    ns = {
        "generic": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/generic",
        "message": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message",
        "common": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common",
    }

    for series in root.iter("{http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/generic}Series"):
        # Extract series key (country code)
        series_key = series.find("generic:SeriesKey", ns)
        iso3 = ""
        if series_key is not None:
            for val in series_key.findall("generic:Value", ns):
                if val.get("id") == "REF_AREA":
                    iso3 = val.get("value", "")

        for obs in series.iter("{http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/generic}Obs"):
            time_elem = obs.find("generic:ObsDimension", ns)
            value_elem = obs.find("generic:ObsValue", ns)

            if time_elem is not None and value_elem is not None:
                try:
                    year = int(time_elem.get("value", 0))
                    value = float(value_elem.get("value", 0))
                    if iso3 and year and value:
                        results.append({"iso3": iso3, "year": year, "value": value})
                except (ValueError, TypeError):
                    continue

    return results


async def fetch_indicator(
    our_code: str, db: AsyncSession
) -> list[dict]:
    """Fetch a single indicator from IMF."""
    imf_config = IMF_INDICATORS.get(our_code)
    if not imf_config:
        return []

    cache_key = f"indicator/{imf_config['flow']}/{imf_config['key']}"
    cached = await _get_cached(cache_key, db)
    if cached:
        data = cached.get("data", [])
    else:
        data = await _fetch_imf_data(imf_config["flow"], imf_config["key"])
        if data is None:
            return []
        await _set_cache(cache_key, {"data": data}, db)

    return data


async def fetch_all_indicators(db: AsyncSession) -> int:
    """Fetch all IMF indicators.

    Returns total number of values stored.
    """
    total = 0

    for our_code, imf_config in IMF_INDICATORS.items():
        # Ensure indicator definition exists
        existing = await db.execute(
            select(IndicatorDefinition).where(IndicatorDefinition.code == our_code)
        )
        if not existing.scalar_one_or_none():
            defn = IndicatorDefinition(
                code=our_code,
                name=imf_config.get("name", our_code.replace("_", " ").title()),
                source="imf",
                display_type="gradient",
            )
            db.add(defn)

        # Fetch values
        try:
            values = await fetch_indicator(our_code, db)
            for v in values:
                existing_iv = await db.execute(
                    select(IndicatorValue).where(
                        IndicatorValue.country_iso3 == v["iso3"],
                        IndicatorValue.indicator_code == our_code,
                        IndicatorValue.year == v["year"],
                    )
                )
                iv = existing_iv.scalar_one_or_none()
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
            logger.error("Error fetching IMF indicator %s: %s", our_code, e, exc_info=True)

    return total
