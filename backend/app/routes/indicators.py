"""Indicator endpoints: definitions, values, map data."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import IndicatorDefinition, IndicatorValue
from app.schemas.indicator import (
    IndicatorDefinitionResponse, IndicatorValueResponse, IndicatorMapResponse,
)

router = APIRouter()


@router.get("/indicators/definitions", response_model=list[IndicatorDefinitionResponse])
async def list_indicator_definitions(db: AsyncSession = Depends(get_db)):
    """Get all indicator definitions (layer metadata)."""
    result = await db.execute(
        select(IndicatorDefinition).order_by(IndicatorDefinition.sort_order, IndicatorDefinition.code)
    )
    return result.scalars().all()


@router.get("/indicators/values", response_model=list[IndicatorValueResponse])
async def get_indicator_values(
    codes: Optional[str] = Query(None, description="Comma-separated indicator codes"),
    countries: Optional[str] = Query(None, description="Comma-separated ISO3 codes"),
    year: Optional[int] = Query(None, description="Filter by year"),
    db: AsyncSession = Depends(get_db),
):
    """Get indicator values with optional filters."""
    query = select(IndicatorValue)

    if codes:
        code_list = [c.strip() for c in codes.split(",") if c.strip()]
        query = query.where(IndicatorValue.indicator_code.in_(code_list))

    if countries:
        country_list = [c.strip() for c in countries.split(",") if c.strip()]
        query = query.where(IndicatorValue.country_iso3.in_(country_list))

    if year:
        query = query.where(IndicatorValue.year == year)
    else:
        # Default: latest year per country-indicator pair
        subquery = (
            select(
                IndicatorValue.country_iso3,
                IndicatorValue.indicator_code,
                func.max(IndicatorValue.year).label("max_year"),
            )
            .group_by(IndicatorValue.country_iso3, IndicatorValue.indicator_code)
            .subquery()
        )
        query = query.join(
            subquery,
            (IndicatorValue.country_iso3 == subquery.c.country_iso3)
            & (IndicatorValue.indicator_code == subquery.c.indicator_code)
            & (IndicatorValue.year == subquery.c.max_year),
        )

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/indicators/{code}/map", response_model=IndicatorMapResponse)
async def get_indicator_map(
    code: str,
    year: Optional[int] = Query(None, description="Year (default: latest)"),
    db: AsyncSession = Depends(get_db),
):
    """Get indicator values for all countries as {iso3: value} for choropleth rendering."""
    # Check if indicator exists
    defn_result = await db.execute(
        select(IndicatorDefinition).where(IndicatorDefinition.code == code)
    )
    if not defn_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Indicator '{code}' not found")

    if year:
        query = select(IndicatorValue.country_iso3, IndicatorValue.value).where(
            IndicatorValue.indicator_code == code,
            IndicatorValue.year == year,
        )
    else:
        # Latest year per country
        subquery = (
            select(func.max(IndicatorValue.year).label("max_year"))
            .where(IndicatorValue.indicator_code == code)
            .scalar_subquery()
        )
        query = select(IndicatorValue.country_iso3, IndicatorValue.value).where(
            IndicatorValue.indicator_code == code,
            IndicatorValue.year == subquery,
        )

    result = await db.execute(query)
    values = {row[0]: row[1] for row in result.all() if row[1] is not None}

    # Determine the year used
    if year is None and values:
        year_result = await db.execute(
            select(func.max(IndicatorValue.year)).where(
                IndicatorValue.indicator_code == code
            )
        )
        year = year_result.scalar_one() or 0

    return IndicatorMapResponse(indicator_code=code, year=year, values=values)
