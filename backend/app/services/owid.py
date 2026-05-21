"""Our World in Data (OWID) data fetcher.

Fetches indicators from OWID's GitHub-hosted CSV datasets.
Repository: https://github.com/owid/owid-datasets
"""

import asyncio
import csv
import io
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IndicatorDefinition, IndicatorValue, APICache

# OWID dataset URLs — these are stable GitHub raw URLs
OWID_DATASETS = {
    "hdi": {
        "url": "https://raw.githubusercontent.com/owid/owid-datasets/master/datasets/Human%20Development%20Index%20(HDI)/Human%20Development%20Index%20(HDI).csv",
        "entity_col": "Entity",
        "year_col": "Year",
        "value_col": "Human Development Index",
        "name": "Human Development Index",
    },
    "democracy_index": {
        "url": "https://raw.githubusercontent.com/owid/democracy-dataset/master/Output%20files/-%20Democracy%20Index.csv",
        "entity_col": "Entity",
        "year_col": "Year",
        "value_col": "democracy_index",
        "name": "Democracy Index",
    },
    "corruption": {
        "url": "https://raw.githubusercontent.com/owid/owid-datasets/master/datasets/Corruption%20Perceptions%20Index%20(CPI)/Corruption%20Perceptions%20Index%20(CPI).csv",
        "entity_col": "Entity",
        "year_col": "Year",
        "value_col": "Corruption Perceptions Index (CPI)",
        "name": "Corruption Perceptions Index",
    },
    "press_freedom": {
        "url": "https://raw.githubusercontent.com/owid/owid-datasets/master/datasets/Press%20Freedom%20Index/Press%20Freedom%20Index.csv",
        "entity_col": "Entity",
        "year_col": "Year",
        "value_col": "Press Freedom Index",
        "name": "Press Freedom Index",
    },
    "political_stability": {
        "url": "https://raw.githubusercontent.com/owid/owid-datasets/master/datasets/Political%20Stability%20Index/Political%20Stability%20Index.csv",
        "entity_col": "Entity",
        "year_col": "Year",
        "value_col": "Political Stability Index",
        "name": "Political Stability Index",
    },
    "freedom": {
        "url": "https://raw.githubusercontent.com/owid/owid-datasets/master/datasets/Freedom%20in%20the%20World/Freedom%20in%20the%20World.csv",
        "entity_col": "Entity",
        "year_col": "Year",
        "value_col": "Freedom in the World",
        "name": "Freedom in the World",
    },
}

# ISO3 mapping — OWID uses country names, we need ISO3 codes
# This is a partial mapping; for production, use a proper country name → ISO3 resolver
COUNTRY_NAME_TO_ISO3 = {
    "United States": "USA",
    "China": "CHN",
    "Russia": "RUS",
    "Germany": "DEU",
    "United Kingdom": "GBR",
    "France": "FRA",
    "Japan": "JPN",
    "India": "IND",
    "Brazil": "BRA",
    "Canada": "CAN",
    "Australia": "AUS",
    "South Korea": "KOR",
    "Italy": "ITA",
    "Spain": "ESP",
    "Mexico": "MEX",
    "Indonesia": "IDN",
    "Netherlands": "NLD",
    "Saudi Arabia": "SAU",
    "Turkey": "TUR",
    "Switzerland": "CHE",
    "Argentina": "ARG",
    "Poland": "POL",
    "Thailand": "THA",
    "Sweden": "SWE",
    "Nigeria": "NGA",
    "Austria": "AUT",
    "United Arab Emirates": "ARE",
    "Norway": "NOR",
    "Israel": "ISR",
    "South Africa": "ZAF",
    "Ireland": "IRL",
    "Singapore": "SGP",
    "Malaysia": "MYS",
    "Chile": "CHL",
    "Bangladesh": "BGD",
    "Colombia": "COL",
    "Philippines": "PHL",
    "Pakistan": "PAK",
    "Egypt": "EGY",
    "Vietnam": "VNM",
    "Denmark": "DNK",
    "Romania": "ROU",
    "Czech Republic": "CZE",
    "Portugal": "PRT",
    "New Zealand": "NZL",
    "Peru": "PER",
    "Iraq": "IRQ",
    "Algeria": "DZA",
    "Qatar": "QAT",
    "Kazakhstan": "KAZ",
    "Hungary": "HUN",
    "Kuwait": "KWT",
    "Ukraine": "UKR",
    "Morocco": "MAR",
    "Ecuador": "ECU",
    "Slovakia": "SVK",
    "Dominican Republic": "DOM",
    "Finland": "FIN",
    "Angola": "AGO",
    "Guatemala": "GTM",
    "Ethiopia": "ETH",
    "Sri Lanka": "LKA",
    "Oman": "OMN",
    "Kenya": "KEN",
    "Costa Rica": "CRI",
    "Panama": "PAN",
    "Uruguay": "URY",
    "Tanzania": "TZA",
    "Ghana": "GHA",
    "Uzbekistan": "UZB",
    "Venezuela": "VEN",
    "Bulgaria": "BGR",
    "Luxembourg": "LUX",
    "Lithuania": "LTU",
    "Croatia": "HRV",
    "Belarus": "BLR",
    "Azerbaijan": "AZE",
    "Serbia": "SRB",
    "Tunisia": "TUN",
    "Slovenia": "SVN",
    "Jordan": "JOR",
    "Latvia": "LVA",
    "Paraguay": "PRY",
    "Georgia": "GEO",
    "Estonia": "EST",
    "Bolivia": "BOL",
    "Honduras": "HND",
    "Cyprus": "CYP",
    "Nepal": "NPL",
    "Cambodia": "KHM",
    "El Salvador": "SLV",
    "Senegal": "SEN",
    "Zambia": "ZMB",
    "Zimbabwe": "ZWE",
    "Uganda": "UGA",
    "Cameroon": "CMR",
    "Cuba": "CUB",
    "Mozambique": "MOZ",
    "Mongolia": "MNG",
    "Armenia": "ARM",
    "Albania": "ALB",
    "Jamaica": "JAM",
    "Libya": "LBY",
    "Mali": "MLI",
    "Botswana": "BWA",
    "Gabon": "GAB",
    "Lesotho": "LSO",
    "Gambia": "GMB",
    "Benin": "BEN",
    "Guinea": "GIN",
    "Rwanda": "RWA",
    "Burundi": "BDI",
    "Somalia": "SOM",
    "Togo": "TGO",
    "Sierra Leone": "SLE",
    "Laos": "LAO",
    "Nicaragua": "NIC",
    "Kyrgyz Republic": "KGZ",
    "Mauritania": "MRT",
    "Malawi": "MWI",
    "Tajikistan": "TJK",
    "Republic of Congo": "COG",
    "Burkina Faso": "BFA",
    "Moldova": "MDA",
    "North Macedonia": "MKD",
    "Cote d'Ivoire": "CIV",
    "Namibia": "NAM",
    "Bosnia and Herzegovina": "BIH",
    "Montenegro": "MNE",
    "Iceland": "ISL",
    "Malta": "MLT",
    "Brunei": "BRN",
    "Bahrain": "BHR",
    "Trinidad and Tobago": "TTO",
    "Eswatini": "SWZ",
    "Fiji": "FJI",
    "Guyana": "GUY",
    "Timor-Leste": "TLS",
    "Mauritius": "MUS",
    "Maldives": "MDV",
    "Cape Verde": "CPV",
    "Suriname": "SUR",
    "Bhutan": "BTN",
    "Seychelles": "SYC",
    "Antigua and Barbuda": "ATG",
    "Andorra": "AND",
    "Dominica": "DMA",
    "Saint Lucia": "LCA",
    "Grenada": "GRD",
    "Samoa": "WSM",
    "Vanuatu": "VUT",
    "Barbados": "BRB",
    "Sao Tome and Principe": "STP",
    "Saint Vincent and the Grenadines": "VCT",
    "Comoros": "COM",
    "Tonga": "TON",
    "Micronesia": "FSM",
    "Palau": "PLW",
    "Marshall Islands": "MHL",
    "Kiribati": "KIR",
    "Nauru": "NRU",
    "Tuvalu": "TUV",
    "Solomon Islands": "SLB",
    "Papua New Guinea": "PNG",
    "Democratic Republic of Congo": "COD",
    "Central African Republic": "CAF",
    "Chad": "TCD",
    "South Sudan": "SSD",
    "Eritrea": "ERI",
    "Djibouti": "DJI",
    "Equatorial Guinea": "GNQ",
    "Guinea-Bissau": "GNB",
    "Liberia": "LBR",
    "Madagascar": "MDG",
    "Gambia, The": "GMB",
    "Congo, Rep.": "COG",
    "Congo, Dem. Rep.": "COD",
    "Egypt, Arab Rep.": "EGY",
    "Iran": "IRN",
    "Iran, Islamic Rep.": "IRN",
    "Korea, Rep.": "KOR",
    "Korea, Dem. Rep.": "PRK",
    "Yemen": "YEM",
    "Yemen, Rep.": "YEM",
    "Syria": "SYR",
    "Syrian Arab Republic": "SYR",
    "Sudan": "SDN",
    "North Korea": "PRK",
    "Venezuela, RB": "VEN",
    "Russian Federation": "RUS",
    "United Kingdom of Great Britain and Northern Ireland": "GBR",
    "United States of America": "USA",
    "Iran (Islamic Republic of)": "IRN",
    "Republic of Korea": "KOR",
    "Dem. People's Republic of Korea": "PRK",
    "Dem. Rep. of the Congo": "COD",
    "Congo (Dem. Rep.)": "COD",
    "Congo (Rep.)": "COG",
    "Congo": "COG",
    "Czechia": "CZE",
    "North Macedonia": "MKD",
    "Eswatini (formerly Swaziland)": "SWZ",
    "Cabo Verde": "CPV",
    "Türkiye": "TUR",
    "Brunei Darussalam": "BRN",
    "Myanmar": "MMR",
    "Burma": "MMR",
}

CACHE_TTL_HOURS = 24


async def _get_cached(cache_key: str, db: AsyncSession) -> Optional[dict]:
    """Check cache for an OWID response."""
    result = await db.execute(
        select(APICache).where(
            APICache.source == "owid",
            APICache.cache_key == cache_key,
            APICache.expires_at > datetime.now(timezone.utc),
        )
    )
    cached = result.scalar_one_or_none()
    return cached.response_data if cached else None


async def _set_cache(cache_key: str, data: dict, db: AsyncSession) -> None:
    """Store OWID response in cache."""
    await db.execute(
        delete(APICache).where(
            APICache.source == "owid",
            APICache.cache_key == cache_key,
        )
    )
    entry = APICache(
        source="owid",
        cache_key=cache_key,
        response_data=data,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=CACHE_TTL_HOURS),
    )
    db.add(entry)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=3, max=15))
async def _fetch_owid_dataset(dataset_key: str) -> Optional[pd.DataFrame]:
    """Fetch an OWID dataset CSV and parse it."""
    dataset = OWID_DATASETS.get(dataset_key)
    if not dataset:
        return None

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(dataset["url"])
        resp.raise_for_status()

        # Try to parse CSV
        try:
            df = pd.read_csv(io.StringIO(resp.text))
            return df
        except Exception:
            return None


async def fetch_indicator(
    our_code: str, db: AsyncSession
) -> list[dict]:
    """Fetch a single indicator from OWID and store in DB.

    Returns list of {iso3, year, value} dicts.
    """
    dataset = OWID_DATASETS.get(our_code)
    if not dataset:
        return []

    cache_key = f"dataset/{our_code}"
    cached = await _get_cached(cache_key, db)
    if cached:
        # Reconstruct DataFrame from cached data
        df = pd.DataFrame(cached.get("data", []))
    else:
        df = await _fetch_owid_dataset(our_code)
        if df is None:
            return []
        # Cache the data
        await _set_cache(cache_key, {"data": df.to_dict(orient="records")}, db)

    results = []
    entity_col = dataset.get("entity_col", "Entity")
    year_col = dataset.get("year_col", "Year")
    value_col = dataset.get("value_col")

    if value_col not in df.columns:
        # Try to find a numeric column
        numeric_cols = df.select_dtypes(include=["number"]).columns
        if len(numeric_cols) >= 1:
            value_col = numeric_cols[-1]  # Last numeric column
        else:
            return []

    for _, row in df.iterrows():
        entity = str(row.get(entity_col, "")).strip()
        year = int(row.get(year_col, 0))
        value = row.get(value_col)

        if pd.isna(value) or not year:
            continue

        iso3 = COUNTRY_NAME_TO_ISO3.get(entity)
        if not iso3:
            continue

        try:
            value = float(value)
        except (ValueError, TypeError):
            continue

        results.append({"iso3": iso3, "year": year, "value": value})

    return results


async def fetch_all_indicators(db: AsyncSession) -> int:
    """Fetch all OWID indicators.

    Returns total number of values stored.
    """
    total = 0

    for our_code in OWID_DATASETS:
        dataset = OWID_DATASETS[our_code]

        # Ensure indicator definition exists
        existing = await db.execute(
            select(IndicatorDefinition).where(IndicatorDefinition.code == our_code)
        )
        if not existing.scalar_one_or_none():
            defn = IndicatorDefinition(
                code=our_code,
                name=dataset.get("name", our_code.replace("_", " ").title()),
                source="owid",
                source_url=dataset.get("url", ""),
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
            print(f"  Error fetching OWID {our_code}: {e}")

    return total
