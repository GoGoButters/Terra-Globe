"""GDELT GEO 2.0 API client for bilateral diplomatic tone.

Tracks media tone between countries using SourceCountry mode.
Free, no API key, updated every 15 minutes.

GDELT GEO API docs:
  https://blog.gdeltproject.org/gdelt-geo-2-0-api-powering-location-aware-analysis/

The API returns tone values from -10 (very negative) to +10 (very positive).
We cache results for 6 hours (GDELT updates every 15 min, but tone
doesn't change dramatically within hours).
"""

import logging
from typing import Any

from app.services.cache import get_cached, set_cache
from app.services.http_client import get_shared_client

logger = logging.getLogger(__name__)

GDELT_GEO_API = "https://api.gdeltproject.org/api/v2/geo/geo"
CACHE_TTL = 21600  # 6 hours


def _gdelt_name(name: str) -> str:
    """Convert a country English name to GDELT-friendly format.

    GDELT uses lowercase, no spaces, no special chars.
    Examples:
      "United States" → "unitedstates"
      "United Kingdom" → "unitedkingdom"
      "Russia" → "russia"
      "South Korea" → "southkorea"
      "Czech Republic" → "czechrepublic"
      "Ivory Coast" → "ivorycoast"
    """
    # Known aliases where GDELT uses different names
    aliases = {
        "unitedstates": "unitedstates",
        "unitedstatesofamerica": "unitedstates",
        "usa": "unitedstates",
        "russia": "russia",
        "russianfederation": "russia",
        "unitedkingdom": "unitedkingdom",
        "greatbritain": "unitedkingdom",
        "uk": "unitedkingdom",
        "southkorea": "southkorea",
        "republicofkorea": "southkorea",
        "korea": "southkorea",
        "northkorea": "northkorea",
        "dprk": "northkorea",
        "czechrepublic": "czechrepublic",
        "czechia": "czechrepublic",
        "ivorycoast": "ivorycoast",
        "cotedivoire": "ivorycoast",
        "burmamyanmar": "myanmar",
        "myanmar": "myanmar",
        "burma": "myanmar",
        "uae": "unitedarabemirates",
        "emirates": "unitedarabemirates",
        "drc": "democraticrepublicofthecongo",
        "congokinshasa": "democraticrepublicofthecongo",
        "congobrazzaville": "republicofthecongo",
        "timorleste": "easttimor",
        "easttimor": "easttimor",
        "capoverde": "cabooverde",
        "caboroverde": "cabooverde",
    }

    normalized = name.strip().lower().replace(" ", "")
    if normalized in aliases:
        return aliases[normalized]
    return normalized


async def get_country_tone(
    country_name: str,
    target_names: list[str],
) -> dict[str, dict]:
    """Get media tone from country_name's media about multiple target countries.

    Uses GDELT SourceCountry mode to measure how country's media covers other countries.

    Args:
        country_name: English name of source country
        target_names: List of English country names to check tone for

    Returns:
        {target_name: {"tone": float, "count": int, "articles": [...], "trend": str}}
    """
    results: dict[str, dict] = {}
    source_gdelt = _gdelt_name(country_name)

    client = await get_shared_client()

    for target in target_names:
        target_gdelt = _gdelt_name(target)

        cache_key = f"tone:{source_gdelt}:{target_gdelt}"
        cached = await get_cached("gdelt", cache_key)
        if cached is not None:
            results[target] = cached
            continue

        # GDELT GEO 2.0 query format:
        #   sourcecountry:{source} locationcc:{target}
        # mode=sourcecountry gives us articles from source's media about target
        query = f"sourcecountry:{source_gdelt} locationcc:{target_gdelt}"

        try:
            resp = await client.get(
                GDELT_GEO_API,
                params={
                    "query": query,
                    "mode": "sourcecountry",
                    "timespan": "7d",
                    "format": "json",
                    "maxrecords": 10,
                },
                timeout=15.0,
            )

            if resp.status_code != 200:
                logger.debug(
                    "GDELT returned %d for %s → %s",
                    resp.status_code, country_name, target,
                )
                results[target] = {
                    "tone": 0,
                    "count": 0,
                    "articles": [],
                    "trend": "stable",
                }
                continue

            data = resp.json()

            # GDELT GEO response structure:
            # {
            #   "articles": [...],
            #   "tone": {...},
            #   "count": N
            # }
            # The tone field can be a dict with "avg" or a direct number.

            tone_val = 0.0
            count_val = 0

            if isinstance(data, dict):
                # Extract average tone
                tone_field = data.get("tone", {})
                if isinstance(tone_field, dict):
                    tone_val = float(tone_field.get("avg", 0) or 0)
                elif isinstance(tone_field, (int, float)):
                    tone_val = float(tone_field)

                count_val = int(data.get("count", 0) or 0)

                # Extract articles
                articles = []
                articles_field = data.get("articles", data.get("data", []))
                if isinstance(articles_field, list):
                    for item in articles_field[:5]:
                        if isinstance(item, dict):
                            articles.append({
                                "title": item.get("title", ""),
                                "url": item.get("url", ""),
                                "tone": float(item.get("tone", 0) or 0),
                                "date": item.get("date", ""),
                                "source": item.get("domain", ""),
                            })

                # Determine trend based on tone
                trend = "stable"
                if tone_val > 3:
                    trend = "up"
                elif tone_val < -3:
                    trend = "down"

                result = {
                    "tone": round(tone_val, 2),
                    "count": count_val,
                    "articles": articles,
                    "trend": trend,
                }
            else:
                result = {
                    "tone": 0,
                    "count": 0,
                    "articles": [],
                    "trend": "stable",
                }

            await set_cache("gdelt", cache_key, value=result, ttl=CACHE_TTL)
            results[target] = result

        except Exception as e:
            logger.warning("GDELT query failed for %s → %s: %s", country_name, target, e)
            results[target] = {
                "tone": 0,
                "count": 0,
                "articles": [],
                "trend": "stable",
            }

    return results
