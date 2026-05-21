"""Country endpoints: list, detail, GeoJSON."""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.functions import ST_AsGeoJSON, ST_Centroid, ST_Simplify

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
            # Use ST_Intersects with a bounding box polygon
            bbox_geom = (
                f"ST_MakeEnvelope({min_lon},{min_lat},{max_lon},{max_lat},4326)"
            )
            query = query.where(
                func.ST_Intersects(
                    Country.centroid,
                    func.func.ST_GeomFromText(
                        f"POLYGON(({min_lon} {min_lat},{max_lon} {min_lat},{max_lon} {max_lat},{min_lon} {max_lat},{min_lon} {min_lat}))",
                        4326,
                    ),
                )
            )
        except (ValueError, IndexError):
            pass  # Invalid bbox, return all

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
        from fastapi import HTTPException
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
    """Get all countries as a GeoJSON FeatureCollection.

    Supports optional ST_Simplify for reduced payload size at lower zoom levels.
    """
    if simplify and simplify > 0:
        # Simplified geometry
        geojson_query = f"""
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
                        'geometry', ST_AsGeoJSON(ST_Simplify(c.geometry, {simplify}))::jsonb
                    )
                ), '[]'::jsonb)
            )
            FROM countries c
            WHERE c.geometry IS NOT NULL
        """
    else:
        # Full resolution
        geojson_query = """
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
        """

    result = await db.execute(geojson_query)
    row = result.scalar_one()
    return row
