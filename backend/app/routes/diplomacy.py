"""Diplomacy endpoints: embassy networks, bilateral tone, and static relations.

Endpoints:
  GET /api/diplomacy                — list static diplomatic relations
  GET /api/diplomacy/{iso3}         — full diplomatic profile for one country
  GET /api/diplomacy/{iso3_a}/{iso3_b} — bilateral detail between two countries
"""

import asyncio
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import DiplomaticRelation, Country
from app.schemas.diplomacy import DiplomaticRelationResponse

logger = logging.getLogger(__name__)
router = APIRouter()

# ── ISO3 → English name mapping for GDELT queries ──
# We need English country names for GDELT; this is the canonical mapping.
# If a country isn't here, we try the DB first, then skip tone data.
ISO3_TO_EN_NAME: dict[str, str] = {
    "AFG": "Afghanistan", "ALB": "Albania", "DZA": "Algeria", "AND": "Andorra",
    "AGO": "Angola", "ATG": "Antigua and Barbuda", "ARG": "Argentina",
    "ARM": "Armenia", "AUS": "Australia", "AUT": "Austria", "AZE": "Azerbaijan",
    "BHS": "Bahamas", "BHR": "Bahrain", "BGD": "Bangladesh", "BRB": "Barbados",
    "BLR": "Belarus", "BEL": "Belgium", "BLZ": "Belize", "BEN": "Benin",
    "BTN": "Bhutan", "BOL": "Bolivia", "BIH": "Bosnia and Herzegovina",
    "BWA": "Botswana", "BRA": "Brazil", "BRN": "Brunei", "BGR": "Bulgaria",
    "BFA": "Burkina Faso", "BDI": "Burundi", "KHM": "Cambodia", "CMR": "Cameroon",
    "CAN": "Canada", "CPV": "Cape Verde", "CAF": "Central African Republic",
    "TCD": "Chad", "CHL": "Chile", "CHN": "China", "COL": "Colombia",
    "COM": "Comoros", "COG": "Republic of the Congo", "COD": "Democratic Republic of the Congo",
    "CRI": "Costa Rica", "CIV": "Ivory Coast", "HRV": "Croatia", "CUB": "Cuba",
    "CYP": "Cyprus", "CZE": "Czech Republic", "DNK": "Denmark", "DJI": "Djibouti",
    "DMA": "Dominica", "DOM": "Dominican Republic", "ECU": "Ecuador", "EGY": "Egypt",
    "SLV": "El Salvador", "GNQ": "Equatorial Guinea", "ERI": "Eritrea",
    "EST": "Estonia", "SWZ": "Eswatini", "ETH": "Ethiopia", "FJI": "Fiji",
    "FIN": "Finland", "FRA": "France", "GAB": "Gabon", "GMB": "Gambia",
    "GEO": "Georgia", "DEU": "Germany", "GHA": "Ghana", "GRC": "Greece",
    "GRD": "Grenada", "GTM": "Guatemala", "GIN": "Guinea", "GNB": "Guinea-Bissau",
    "GUY": "Guyana", "HTI": "Haiti", "HND": "Honduras", "HUN": "Hungary",
    "ISL": "Iceland",     "IND": "India", "IDN": "Indonesia",  # noqa: E501 "IRN": "Iran",
    "IRQ": "Iraq", "IRL": "Ireland", "ISR": "Israel", "ITA": "Italy",
    "JAM": "Jamaica", "JPN": "Japan", "JOR": "Jordan", "KAZ": "Kazakhstan",
    "KEN": "Kenya", "KIR": "Kiribati", "PRK": "North Korea",
    "KOR": "South Korea", "KWT": "Kuwait", "KGZ": "Kyrgyzstan", "LAO": "Laos",
    "LVA": "Latvia", "LBN": "Lebanon", "LSO": "Lesotho", "LBR": "Liberia",
    "LBY": "Libya", "LIE": "Liechtenstein", "LTU": "Lithuania", "LUX": "Luxembourg",
    "MDG": "Madagascar", "MWI": "Malawi", "MYS": "Malaysia", "MDV": "Maldives",
    "MLI": "Mali", "MLT": "Malta", "MHL": "Marshall Islands", "MRT": "Mauritania",
    "MUS": "Mauritius", "MEX": "Mexico", "FSM": "Micronesia", "MDA": "Moldova",
    "MCO": "Monaco", "MNG": "Mongolia", "MNE": "Montenegro", "MAR": "Morocco",
    "MOZ": "Mozambique", "MMR": "Myanmar", "NAM": "Namibia", "NRU": "Nauru",
    "NPL": "Nepal", "NLD": "Netherlands", "NZL": "New Zealand",
    "NIC": "Nicaragua", "NER": "Niger", "NGA": "Nigeria", "MKD": "North Macedonia",
    "NOR": "Norway", "OMN": "Oman", "PAK": "Pakistan", "PLW": "Palau",
    "PSE": "Palestine", "PAN": "Panama", "PNG": "Papua New Guinea",
    "PRY": "Paraguay", "PER": "Peru", "PHL": "Philippines", "POL": "Poland",
    "PRT": "Portugal", "QAT": "Qatar", "ROU": "Romania", "RUS": "Russia",
    "RWA": "Rwanda", "KNA": "Saint Kitts and Nevis",
    "LCA": "Saint Lucia", "VCT": "Saint Vincent and the Grenadines",
    "WSM": "Samoa", "SMR": "San Marino", "STP": "Sao Tome and Principe",
    "SAU": "Saudi Arabia", "SEN": "Senegal", "SRB": "Serbia",
    "SYC": "Seychelles", "SLE": "Sierra Leone", "SGP": "Singapore",
    "SVK": "Slovakia", "SVN": "Slovenia", "SLB": "Solomon Islands",
    "SOM": "Somalia", "ZAF": "South Africa", "SSD": "South Sudan",
    "ESP": "Spain", "LKA": "Sri Lanka", "SDN": "Sudan", "SUR": "Suriname",
    "SWE": "Sweden", "CHE": "Switzerland", "SYR": "Syria", "TWN": "Taiwan",
    "TJK": "Tajikistan", "TZA": "Tanzania", "THA": "Thailand",
    "TLS": "East Timor", "TGO": "Togo", "TON": "Tonga",
    "TTO": "Trinidad and Tobago", "TUN": "Tunisia", "TUR": "Turkey",
    "TKM": "Turkmenistan", "TUV": "Tuvalu", "UGA": "Uganda", "UKR": "Ukraine",
    "ARE": "United Arab Emirates", "GBR": "United Kingdom",
    "USA": "United States", "URY": "Uruguay", "UZB": "Uzbekistan",
    "VUT": "Vanuatu", "VEN": "Venezuela", "VNM": "Vietnam",
    "YEM": "Yemen", "ZMB": "Zambia", "ZWE": "Zimbabwe",
}


def _resolve_country_name(iso3: str, db_name: str | None) -> str:
    """Resolve English country name for GDELT: DB → static mapping → None."""
    if iso3 in ISO3_TO_EN_NAME:
        return ISO3_TO_EN_NAME[iso3]
    if db_name:
        return db_name
    return ""


# ────────────────────────────────────────────────────────────────
# GET /api/diplomacy  —  list static diplomatic relations (backward compat)
# ────────────────────────────────────────────────────────────────
@router.get("/diplomacy", response_model=list[DiplomaticRelationResponse])
async def list_diplomacy(
    country: Optional[str] = Query(None, description="Filter by country ISO3"),
    db: AsyncSession = Depends(get_db),
):
    """List diplomatic relations, optionally filtered by country."""
    query = select(DiplomaticRelation)

    if country:
        query = query.where(
            or_(
                DiplomaticRelation.country_iso3_a == country,
                DiplomaticRelation.country_iso3_b == country,
            )
        )

    result = await db.execute(query)
    relations = result.scalars().all()

    response = []
    for rel in relations:
        name_a = await db.execute(
            select(Country.name).where(Country.iso3 == rel.country_iso3_a)
        )
        name_b = await db.execute(
            select(Country.name).where(Country.iso3 == rel.country_iso3_b)
        )

        docs = rel.documents or []
        response.append(
            DiplomaticRelationResponse(
                country1_iso3=rel.country_iso3_a,
                country1_name=name_a.scalar_one_or_none(),
                country2_iso3=rel.country_iso3_b,
                country2_name=name_b.scalar_one_or_none(),
                summary=rel.summary,
                documents=[
                    {
                        "title": doc.get("title", ""),
                        "year": doc.get("year"),
                        "type": doc.get("type", ""),
                        "description": doc.get("description", ""),
                    }
                    for doc in docs
                ],
            )
        )

    return response


# ────────────────────────────────────────────────────────────────
# GET /api/diplomacy/{iso3}  —  full diplomatic profile (Wikidata + GDELT)
# ────────────────────────────────────────────────────────────────
@router.get("/diplomacy/{iso3}")
async def get_diplomacy_profile(
    iso3: str,
    db: AsyncSession = Depends(get_db),
):
    """Full diplomatic profile for a country: embassies + bilateral media tone.

    Returns:
      - iso3, name, name_ru
      - embassies: { has_embassy_in: [...], embassies_from: [...] }
      - tone: { partner_iso3: { tone, count, trend, articles }, ... }
      - top_partners: [iso3, ...]   — top 5 by positive tone
      - top_adversaries: [iso3, ...] — top 5 by negative tone
    """
    iso3 = iso3.upper()

    # 1. Get country info from DB
    country_result = await db.execute(
        select(Country).where(Country.iso3 == iso3)
    )
    country = country_result.scalar_one_or_none()

    name = country.name if country else iso3
    name_ru = country.name_ru if country else None

    # 2. Get embassy data from Wikidata (with static fallback)
    from app.services.wikidata import get_embassies, get_embassies_static

    try:
        embassies = await get_embassies(iso3)
    except Exception as e:
        logger.warning("Wikidata embassy query failed for %s: %s", iso3, e)
        embassies = {"has_embassy_in": [], "embassies_from": []}

    # If Wikidata returned nothing, use static fallback
    if not embassies["has_embassy_in"] and not embassies["embassies_from"]:
        embassies = get_embassies_static(iso3)

    # 3. Get tone data from GDELT for key partners
    from app.services.gdelt import get_country_tone

    en_name = _resolve_country_name(iso3, name)

    # Combine embassy partners for tone queries (take union, limit to top 15)
    all_partners = list(set(
        embassies["has_embassy_in"][:20] + embassies["embassies_from"][:20]
    ))

    # Sort by a rough "importance" (G7/BRICS first), take top 15
    priority = [
        "USA", "CHN", "RUS", "GBR", "FRA", "DEU", "JPN", "IND",
        "BRA", "CAN", "AUS", "KOR", "ITA", "ESP", "TUR", "SAU",
        "POL", "NLD", "CHE", "SWE", "NOR", "UKR", "KAZ", "IDN",
    ]
    all_partners.sort(key=lambda x: (x not in priority, priority.index(x) if x in priority else 999))
    tone_partners = all_partners[:15]

    tone_data: dict[str, dict] = {}
    if en_name and tone_partners:
        # Resolve English names for tone partners
        target_names = []
        target_iso3s = []
        for p in tone_partners:
            p_name = _resolve_country_name(p, "")
            if p_name:
                target_names.append(p_name)
                target_iso3s.append(p)

        if target_names:
            try:
                raw_tone = await get_country_tone(en_name, target_names)
                # Map back to ISO3 keys
                for iso, t_name in zip(target_iso3s, target_names):
                    if t_name in raw_tone:
                        tone_data[iso] = raw_tone[t_name]
            except Exception as e:
                logger.warning("GDELT tone query failed for %s: %s", iso3, e)

    # 4. Compute top partners / adversaries
    partners_with_tone = [
        (iso, data.get("tone", 0))
        for iso, data in tone_data.items()
        if data.get("count", 0) > 0
    ]

    partners_with_tone.sort(key=lambda x: x[1], reverse=True)

    top_partners = [iso for iso, _ in partners_with_tone[:5]]
    top_adversaries = [iso for iso, _ in partners_with_tone[-5:]][::-1]

    # If we don't have enough tone data, fill from embassy list
    if len(top_partners) < 5:
        for iso in embassies["has_embassy_in"][:10]:
            if iso not in top_partners and iso not in top_adversaries:
                top_partners.append(iso)
                if len(top_partners) >= 5:
                    break

    if len(top_adversaries) < 5:
        for iso in reversed(embassies["embassies_from"][:10]):
            if iso not in top_adversaries and iso not in top_partners:
                top_adversaries.append(iso)
                if len(top_adversaries) >= 5:
                    break

    return {
        "iso3": iso3,
        "name": name,
        "name_ru": name_ru,
        "embassies": embassies,
        "tone": tone_data,
        "top_partners": top_partners[:5],
        "top_adversaries": top_adversaries[:5],
    }


# ────────────────────────────────────────────────────────────────
# GET /api/diplomacy/{iso3_a}/{iso3_b}  —  bilateral detail (backward compat)
# ────────────────────────────────────────────────────────────────
@router.get("/diplomacy/{iso3_a}/{iso3_b}")
async def get_diplomatic_relations(
    iso3_a: str,
    iso3_b: str,
    db: AsyncSession = Depends(get_db),
):
    """Get bilateral diplomatic relations between two countries."""
    # Try both orderings in static DB
    result = await db.execute(
        select(DiplomaticRelation).where(
            or_(
                (DiplomaticRelation.country_iso3_a == iso3_a)
                & (DiplomaticRelation.country_iso3_b == iso3_b),
                (DiplomaticRelation.country_iso3_a == iso3_b)
                & (DiplomaticRelation.country_iso3_b == iso3_a),
            )
        )
    )
    rel = result.scalar_one_or_none()

    if not rel:
        return DiplomaticRelationResponse(
            country1_iso3=iso3_a,
            country2_iso3=iso3_b,
            summary="Данные о дипломатических отношениях пока не загружены",
            documents=[],
        )

    name_a = await db.execute(select(Country.name).where(Country.iso3 == rel.country_iso3_a))
    name_b = await db.execute(select(Country.name).where(Country.iso3 == rel.country_iso3_b))

    docs = rel.documents or []
    return DiplomaticRelationResponse(
        country1_iso3=rel.country_iso3_a,
        country1_name=name_a.scalar_one_or_none(),
        country2_iso3=rel.country_iso3_b,
        country2_name=name_b.scalar_one_or_none(),
        summary=rel.summary,
        documents=[
            {
                "title": doc.get("title", ""),
                "year": doc.get("year"),
                "type": doc.get("type", ""),
                "description": doc.get("description", ""),
            }
            for doc in docs
        ],
    )
