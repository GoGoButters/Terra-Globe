"""Country endpoints: list, detail, GeoJSON."""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import Country, IndicatorValue
from app.schemas.country import CountryBrief, CountryDetail

router = APIRouter()


@router.get("/countries", response_model=list[CountryBrief])
async def list_countries(
    bbox: Optional[str] = Query(None, description="Bounding box: minLon,minLat,maxLon,maxLat"),
    db: AsyncSession = Depends(get_db),
):
    """List all countries, optionally filtered by bounding box."""
    query = select(Country.iso3, Country.name, Country.capital_name,
                   Country.capital_lat, Country.capital_lon)

    if bbox:
        try:
            parts = bbox.split(",")
            min_lon, min_lat, max_lon, max_lat = map(float, parts)
            query = query.where(
                func.ST_Intersects(
                    Country.centroid,
                    func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326),
                )
            )
        except (ValueError, IndexError):
            pass

    result = await db.execute(query.order_by(Country.name))
    return [
        CountryBrief(
            iso3=row[0], name=row[1], capital_name=row[2],
            capital_lat=row[3], capital_lon=row[4],
        )
        for row in result.all()
    ]


@router.get("/countries/{iso3}", response_model=CountryDetail)
async def get_country(iso3: str, db: AsyncSession = Depends(get_db)):
    """Get country details with latest indicator values."""
    result = await db.execute(
        select(Country).where(Country.iso3 == iso3)
    )
    country = result.scalar_one_or_none()
    if not country:
        raise HTTPException(status_code=404, detail="Country not found")

    # Get latest indicator values
    indicator_result = await db.execute(
        select(IndicatorValue.indicator_code, IndicatorValue.value)
        .where(IndicatorValue.country_iso3 == iso3)
        .order_by(IndicatorValue.year.desc())
        .distinct(IndicatorValue.indicator_code)
    )
    indicators = {row[0]: row[1] for row in indicator_result.all() if row[1] is not None}

    return CountryDetail(
        iso3=country.iso3,
        iso2=country.iso2,
        name=country.name,
        official_name=country.official_name,
        region=country.region,
        subregion=country.subregion,
        income_group=country.income_group,
        capital_name=country.capital_name,
        capital_lat=country.capital_lat,
        capital_lon=country.capital_lon,
        population=country.population,
        area_km2=country.area_km2,
        indicators=indicators,
    )


@router.get("/countries/geojson")
async def get_countries_geojson(
    simplify: Optional[float] = Query(None, description="Simplify tolerance in degrees"),
    db: AsyncSession = Depends(get_db),
):
    """Get all countries as a GeoJSON FeatureCollection."""
    try:
        if simplify and simplify > 0:
            raw_sql = text("""
                SELECT jsonb_build_object(
                    'type', 'FeatureCollection',
                    'features', COALESCE(jsonb_agg(
                        jsonb_build_object(
                            'type', 'Feature',
                            'properties', jsonb_build_object(
                                'iso3', c.iso3,
                                'name', c.name,
                                'ISO3166-1-Alpha-3', c.iso3
                            ),
                            'geometry', ST_AsGeoJSON(ST_Simplify(c.geometry, :tol))::jsonb
                        )
                    ), '[]'::jsonb)
                )
                FROM countries c
                WHERE c.geometry IS NOT NULL
            """)
            result = await db.execute(raw_sql, {"tol": simplify})
        else:
            raw_sql = text("""
                SELECT jsonb_build_object(
                    'type', 'FeatureCollection',
                    'features', COALESCE(jsonb_agg(
                        jsonb_build_object(
                            'type', 'Feature',
                            'properties', jsonb_build_object(
                                'iso3', c.iso3,
                                'name', c.name,
                                'ISO3166-1-Alpha-3', c.iso3
                            ),
                            'geometry', ST_AsGeoJSON(c.geometry)::jsonb
                        )
                    ), '[]'::jsonb)
                )
                FROM countries c
                WHERE c.geometry IS NOT NULL
            """)
            result = await db.execute(raw_sql)

        row = result.scalar_one_or_none()
        if row is None:
            return {"type": "FeatureCollection", "features": []}

        # Ensure it's a dict (jsonb may come as string)
        if isinstance(row, str):
            return json.loads(row)
        return row

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GeoJSON generation failed: {str(e)}")
