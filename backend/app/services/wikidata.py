"""Wikidata SPARQL client for diplomatic relations data.

Fetches embassy data via Wikidata Query Service.
Free, no API key required.

Wikidata properties used:
  P298 = ISO 3166-1 alpha-3 code
  P137 = operator (who operates the diplomatic mission)
  P17  = country (where the mission is located)
  P31  = instance of
  Q3917681 = diplomatic mission

Strategy:
  Primary query uses P298 (ISO3) directly.
  Fallback: if SPARQL returns empty, we use a static embassy network
  based on the UN-member mutual-embassy standard (most UN members
  exchange embassies with each other's G7/BRICS partners).
"""

import asyncio
import hashlib
import logging
from typing import Any

from app.services.cache import get_cached, set_cache
from app.services.http_client import get_shared_client

logger = logging.getLogger(__name__)

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
CACHE_TTL = 86400  # 24 hours — embassies don't change often


async def _sparql_query(query: str) -> list[dict]:
    """Execute a SPARQL query against Wikidata, with caching."""
    cache_key = hashlib.sha256(query.encode()).hexdigest()[:32]
    cached = await get_cached("wikidata", cache_key)
    if cached is not None:
        return cached

    client = await get_shared_client()
    try:
        resp = await client.get(
            SPARQL_ENDPOINT,
            params={"query": query, "format": "json"},
            headers={"User-Agent": "TerraGlobe/3.0 (diplomacy; contact: terraglobe@example.com)"},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        bindings = data.get("results", {}).get("bindings", [])
        await set_cache("wikidata", cache_key, value=bindings, ttl=CACHE_TTL)
        return bindings
    except Exception as e:
        logger.warning("Wikidata SPARQL failed: %s", e)
        return []


async def get_embassies(iso3: str) -> dict[str, Any]:
    """Get embassy presence for a country.

    Returns dict with:
      - has_embassy_in: [iso3, ...] — countries where this country has embassies
      - embassies_from: [iso3, ...] — countries that have embassies in this country
    """
    # Query 1: countries where {country} has embassies
    #   ?country has ISO3 code = iso3
    #   ?mission is operated by ?country (P137)
    #   ?mission is instance of diplomatic mission (P31 → Q3917681)
    #   ?mission is located in ?hostCountry (P17)
    #   ?hostCountry has ISO3 code = ?hostISO3
    query_out = f"""
SELECT ?hostISO3 WHERE {{
  ?country wdt:P298 "{iso3}" .
  ?mission wdt:P137 ?country .
  ?mission wdt:P31/wdt:P279* wd:Q3917681 .
  ?mission wdt:P17 ?hostCountry .
  ?hostCountry wdt:P298 ?hostISO3 .
  FILTER(?hostISO3 != "{iso3}")
}}
LIMIT 500
"""
    # Query 2: countries that have embassies in {country}
    query_in = f"""
SELECT ?senderISO3 WHERE {{
  ?hostCountry wdt:P298 "{iso3}" .
  ?mission wdt:P17 ?hostCountry .
  ?mission wdt:P31/wdt:P279* wd:Q3917681 .
  ?mission wdt:P137 ?senderCountry .
  ?senderCountry wdt:P298 ?senderISO3 .
  FILTER(?senderISO3 != "{iso3}")
}}
LIMIT 500
"""

    # Run both queries concurrently
    results_out, results_in = await asyncio.gather(
        _sparql_query(query_out),
        _sparql_query(query_in),
    )

    has_embassy_in = sorted(set(
        r.get("hostISO3", {}).get("value", "")
        for r in results_out
        if r.get("hostISO3", {}).get("value")
    ))
    embassies_from = sorted(set(
        r.get("senderISO3", {}).get("value", "")
        for r in results_in
        if r.get("senderISO3", {}).get("value")
    ))

    # If both queries returned empty, try fallback with ISO2 property (P297)
    if not has_embassy_in and not embassies_from:
        logger.info("ISO3 embassy queries returned empty for %s, trying ISO2 fallback", iso3)
        has_embassy_in, embassies_from = await _embassy_fallback_iso2(iso3)

    return {
        "has_embassy_in": has_embassy_in,
        "embassies_from": embassies_from,
    }


async def _embassy_fallback_iso2(iso3: str) -> tuple[list[str], list[str]]:
    """Fallback: first resolve ISO3→ISO2, then query with P297."""
    # Resolve ISO2 for this country
    resolve_q = f"""
SELECT ?iso2 WHERE {{
  ?country wdt:P298 "{iso3}" .
  ?country wdt:P297 ?iso2 .
}}
LIMIT 1
"""
    result = await _sparql_query(resolve_q)
    if not result:
        return [], []

    iso2 = result[0].get("iso2", {}).get("value", "")
    if not iso2:
        return [], []

    # Now query with P297 (ISO2)
    query_out = f"""
SELECT ?hostISO3 WHERE {{
  ?country wdt:P297 "{iso2}" .
  ?mission wdt:P137 ?country .
  ?mission wdt:P31/wdt:P279* wd:Q3917681 .
  ?mission wdt:P17 ?hostCountry .
  ?hostCountry wdt:P298 ?hostISO3 .
  FILTER(?hostISO3 != "{iso3}")
}}
LIMIT 500
"""
    query_in = f"""
SELECT ?senderISO3 WHERE {{
  ?hostCountry wdt:P297 "{iso2}" .
  ?mission wdt:P17 ?hostCountry .
  ?mission wdt:P31/wdt:P279* wd:Q3917681 .
  ?mission wdt:P137 ?senderCountry .
  ?senderCountry wdt:P298 ?senderISO3 .
  FILTER(?senderISO3 != "{iso3}")
}}
LIMIT 500
"""
    results_out, results_in = await asyncio.gather(
        _sparql_query(query_out),
        _sparql_query(query_in),
    )

    has_embassy_in = sorted(set(
        r.get("hostISO3", {}).get("value", "")
        for r in results_out
        if r.get("hostISO3", {}).get("value")
    ))
    embassies_from = sorted(set(
        r.get("senderISO3", {}).get("value", "")
        for r in results_in
        if r.get("senderISO3", {}).get("value")
    ))

    return has_embassy_in, embassies_from


# ── Static fallback data ──
# Major diplomatic network: G7 + BRICS + key regional powers.
# Most countries exchange embassies with at least these partners.

_MAJOR_COUNTRIES = [
    "USA", "CHN", "RUS", "GBR", "FRA", "DEU", "JPN", "IND",
    "BRA", "CAN", "AUS", "KOR", "ITA", "ESP", "MEX", "TUR",
    "SAU", "IDN", "POL", "NLD", "CHE", "SWE", "NOR", "DNK",
    "FIN", "BEL", "AUT", "PRT", "GRC", "CZE", "ISR", "ARE",
    "EGY", "ZAF", "ARG", "COL", "CHL", "PER", "NGA", "KEN",
    "ETH", "GHA", "MAR", "TUN", "VNM", "THA", "MYS", "PHL",
    "SGP", "NZL", "IRL", "ISL", "LUX", "LVA", "LTU", "EST",
    "UKR", "GEO", "KAZ", "UZB", "AZE", "BLR", "SRB", "HRV",
    "BGR", "ROU", "HUN", "SVK", "SVN", "CYP", "MLT", "ROU",
]


def get_embassies_static(iso3: str) -> dict[str, Any]:
    """Static fallback: assume mutual embassies between major countries.

    Every country in _MAJOR_COUNTRIES has embassies in every other
    major country. This is a reasonable approximation for the ~150
    countries that maintain embassies in major capitals.
    """
    if iso3 not in _MAJOR_COUNTRIES:
        # Non-major country: only assume embassies from/to major countries
        return {
            "has_embassy_in": [],
            "embassies_from": [c for c in _MAJOR_COUNTRIES if c != iso3][:20],
        }

    return {
        "has_embassy_in": [c for c in _MAJOR_COUNTRIES if c != iso3],
        "embassies_from": [c for c in _MAJOR_COUNTRIES if c != iso3],
    }
