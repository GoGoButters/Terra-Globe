"""Seed database from existing static data files.

Reads countries_data.csv, capitals.csv, countries.geojson, layers.json,
alliances.json, trade_data.json, diplomacy.json and populates the database.
"""

import asyncio
import csv
import json
from pathlib import Path
from typing import Any

from geoalchemy2.shape import from_shape
from shapely.geometry import shape, mapping
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models import (
    Country, IndicatorDefinition, IndicatorValue,
    Alliance, AllianceMember, TradeFlow, DiplomaticRelation,
)

# Path to static data files (relative to project root)
DATA_DIR = Path(__file__).parent.parent.parent / "frontend" / "data"


def _parse_csv(filepath: Path) -> list[dict[str, str]]:
    """Parse a CSV file into a list of dicts."""
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _parse_json(filepath: Path) -> dict[str, Any] | list[dict]:
    """Parse a JSON file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


async def seed_countries(session: AsyncSession) -> None:
    """Load countries from GeoJSON + CSV data."""
    geojson = _parse_json(DATA_DIR / "countries.geojson")
    csv_data = _parse_csv(DATA_DIR / "countries_data.csv")
    capitals = _parse_csv(DATA_DIR / "capitals.csv")

    # Index CSV data by iso3
    csv_by_iso3 = {row["iso3"]: row for row in csv_data}
    capitals_by_iso3 = {row["iso3"]: row for row in capitals}

    countries_to_insert = []

    for feature in geojson["features"]:
        props = feature["properties"]
        iso3 = props.get("ISO3166-1-Alpha-3", "")
        name = props.get("NAME", "")

        # Skip invalid entries
        if not iso3 or iso3 == "-99":
            continue

        csv_row = csv_by_iso3.get(iso3, {})
        capital_row = capitals_by_iso3.get(iso3, {})

        # Build geometry
        geom = None
        centroid = None
        try:
            geom_obj = shape(feature["geometry"])
            if geom_obj.is_valid:
                geom = from_shape(geom_obj, srid=4326)
                centroid = from_shape(geom_obj.centroid, srid=4326)
        except Exception:
            pass

        country = Country(
            iso3=iso3,
            name=name or csv_row.get("name", ""),
            official_name=csv_row.get("name", ""),
            region=csv_row.get("region", ""),
            subregion=csv_row.get("subregion", ""),
            income_group=csv_row.get("income", ""),
            geometry=geom,
            centroid=centroid,
            capital_name=capital_row.get("capital", ""),
            capital_lat=float(capital_row["lat"]) if capital_row.get("lat") else None,
            capital_lon=float(capital_row["lon"]) if capital_row.get("lon") else None,
            population=int(csv_row["pop"]) if csv_row.get("pop") and csv_row["pop"].isdigit() else None,
        )
        countries_to_insert.append(country)

    # Clear existing and insert
    await session.execute(delete(Country))
    session.add_all(countries_to_insert)
    await session.flush()
    print(f"  Seeded {len(countries_to_insert)} countries")


async def seed_indicators(session: AsyncSession) -> None:
    """Load indicator definitions and values from CSV + layers.json."""
    csv_data = _parse_csv(DATA_DIR / "countries_data.csv")
    layers = _parse_json(DATA_DIR / "layers.json")

    # Indicator columns from CSV
    indicator_columns = [
        "income", "gdp", "pop", "hdi", "freedom", "gdp_per_capita",
        "inflation", "gini", "unemployment", "life_expectancy", "literacy",
        "population_density", "urbanization", "democracy_index",
        "corruption", "press_freedom", "political_stability",
        "military_power", "military_budget", "nuclear_weapons",
    ]

    # Layer metadata
    layer_meta = {k: v for k, v in layers.items()}

    # Clear existing
    await session.execute(delete(IndicatorValue))
    await session.execute(delete(IndicatorDefinition))

    # Insert definitions
    definitions = []
    for col in indicator_columns:
        meta = layer_meta.get(col, {})
        defn = IndicatorDefinition(
            code=col,
            name=meta.get("name", col.replace("_", " ").title()),
            description=meta.get("description", ""),
            category=meta.get("category", ""),
            unit=meta.get("unit", ""),
            source=meta.get("source", "static"),
            source_url=meta.get("sourceUrl", ""),
            methodology=meta.get("methodology", ""),
            display_type=meta.get("type", "gradient"),
            categories=meta.get("categories"),
            gradient_stops=meta.get("stops"),
            sort_order=0,
        )
        definitions.append(defn)

    session.add_all(definitions)
    await session.flush()

    # Insert values (using 2024 as the year for static data)
    values = []
    for row in csv_data:
        iso3 = row.get("iso3", "")
        if not iso3:
            continue
        for col in indicator_columns:
            val_str = row.get(col, "").strip()
            if not val_str:
                continue
            try:
                val = float(val_str)
            except ValueError:
                continue
            iv = IndicatorValue(
                country_iso3=iso3,
                indicator_code=col,
                year=2024,
                value=val,
            )
            values.append(iv)

    session.add_all(values)
    await session.flush()
    print(f"  Seeded {len(definitions)} indicator definitions, {len(values)} values")


async def seed_alliances(session: AsyncSession) -> None:
    """Load alliances from JSON."""
    alliances_data = _parse_json(DATA_DIR / "alliances.json")

    await session.execute(delete(AllianceMember))
    await session.execute(delete(Alliance))

    alliances = []
    members = []

    for code, data in alliances_data.items():
        alliance = Alliance(
            code=code,
            name=data.get("name", ""),
            color=data.get("color", ""),
            founded=int(data["founded"]) if data.get("founded") else None,
            headquarters=data.get("headquarters", ""),
            info=data.get("info", ""),
            features=data.get("features", []),
        )
        alliances.append(alliance)
        # We need the alliance ID after insert, so we'll add members after flush
        session.add(alliance)

    await session.flush()

    # Now add members
    for code, data in alliances_data.items():
        alliance = await session.execute(
            select(Alliance).where(Alliance.code == code)
        )
        alliance_obj = alliance.scalar_one()
        for member_iso3 in data.get("members", []):
            member = AllianceMember(
                alliance_id=alliance_obj.id,
                country_iso3=member_iso3,
            )
            members.append(member)

    session.add_all(members)
    await session.flush()
    print(f"  Seeded {len(alliances)} alliances, {len(members)} members")


async def seed_trade(session: AsyncSession) -> None:
    """Load trade data from JSON."""
    trade_data = _parse_json(DATA_DIR / "trade_data.json")

    await session.execute(delete(TradeFlow))

    flows = []
    for reporter_iso3, data in trade_data.items():
        partners = data.get("partners", [])
        for partner in partners:
            flow = TradeFlow(
                reporter_iso3=reporter_iso3,
                partner_iso3=partner.get("iso3", ""),
                year=2024,
                export_value_usd=float(partner.get("export", 0) or 0),
                import_value_usd=float(partner.get("import", 0) or 0),
                export_categories=data.get("top_exports", []),
                import_categories=data.get("top_imports", []),
            )
            flows.append(flow)

    session.add_all(flows)
    await session.flush()
    print(f"  Seeded {len(flows)} trade flows")


async def seed_diplomacy(session: AsyncSession) -> None:
    """Load diplomatic relations from JSON."""
    diplomacy_data = _parse_json(DATA_DIR / "diplomacy.json")

    await session.execute(delete(DiplomaticRelation))

    relations = []
    for key, data in diplomacy_data.items():
        parts = key.split("_")
        if len(parts) != 2:
            continue
        iso3_a, iso3_b = parts

        relation = DiplomaticRelation(
            country_iso3_a=iso3_a,
            country_iso3_b=iso3_b,
            summary=data.get("summary", ""),
            documents=data.get("relations", []),
        )
        relations.append(relation)

    session.add_all(relations)
    await session.flush()
    print(f"  Seeded {len(relations)} diplomatic relations")


async def run_seed() -> None:
    """Run all seed operations."""
    print("Starting database seed...")

    async with async_session_factory() as session:
        async with session.begin():
            await seed_countries(session)
            await seed_indicators(session)
            await seed_alliances(session)
            await seed_trade(session)
            await seed_diplomacy(session)

    print("Database seed complete!")


if __name__ == "__main__":
    asyncio.run(run_seed())
