"""Trade endpoints: summary, partners, categories."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import TradeFlow, Country
from app.schemas.trade import TradeSummary, TradePartnersResponse, TradeCategoriesResponse

router = APIRouter()


@router.get("/trade/{iso3}")
async def get_trade_summary(
    iso3: str,
    year: Optional[int] = Query(None, description="Year (default: latest)"),
    db: AsyncSession = Depends(get_db),
):
    """Get trade summary for a country."""
    # Check country exists
    country_result = await db.execute(select(Country).where(Country.iso3 == iso3))
    country = country_result.scalar_one_or_none()
    if not country:
        raise HTTPException(status_code=404, detail="Country not found")

    # Determine year
    if year is None:
        year_result = await db.execute(
            select(func.max(TradeFlow.year)).where(TradeFlow.reporter_iso3 == iso3)
        )
        year = year_result.scalar_one() or 2024

    # Aggregate trade data
    result = await db.execute(
        select(
            func.coalesce(func.sum(TradeFlow.export_value_usd), 0),
            func.coalesce(func.sum(TradeFlow.import_value_usd), 0),
        ).where(
            TradeFlow.reporter_iso3 == iso3,
            TradeFlow.year == year,
        )
    )
    row = result.first()
    total_exports = row[0] if row else 0
    total_imports = row[1] if row else 0

    return TradeSummary(
        reporter_iso3=iso3,
        reporter_name=country.name,
        total_exports=total_exports,
        total_imports=total_imports,
        balance=total_exports - total_imports,
        year=year,
    )


@router.get("/trade/{iso3}/partners")
async def get_trade_partners(
    iso3: str,
    year: Optional[int] = Query(None, description="Year (default: latest)"),
    limit: int = Query(10, ge=1, le=50, description="Number of partners to return"),
    db: AsyncSession = Depends(get_db),
):
    """Get top trade partners for a country."""
    # Check country exists
    country_result = await db.execute(select(Country).where(Country.iso3 == iso3))
    country = country_result.scalar_one_or_none()
    if not country:
        raise HTTPException(status_code=404, detail="Country not found")

    # Determine year
    if year is None:
        year_result = await db.execute(
            select(func.max(TradeFlow.year)).where(TradeFlow.reporter_iso3 == iso3)
        )
        year = year_result.scalar_one() or 2024

    # Get top partners by total turnover
    result = await db.execute(
        select(
            TradeFlow.partner_iso3,
            func.coalesce(TradeFlow.export_value_usd, 0),
            func.coalesce(TradeFlow.import_value_usd, 0),
        )
        .where(
            TradeFlow.reporter_iso3 == iso3,
            TradeFlow.year == year,
        )
        .order_by(
            (func.coalesce(TradeFlow.export_value_usd, 0) + func.coalesce(TradeFlow.import_value_usd, 0)).desc()
        )
        .limit(limit)
    )

    partners = []
    for row in result.all():
        # Get partner name
        name_result = await db.execute(
            select(Country.name).where(Country.iso3 == row[0])
        )
        partner_name = name_result.scalar_one_or_none()
        partners.append({
            "iso3": row[0],
            "name": partner_name,
            "export": row[1],
            "import": row[2],
        })

    return {"reporter_iso3": iso3, "year": year, "partners": partners}


@router.get("/trade/{iso3}/categories")
async def get_trade_categories(
    iso3: str,
    year: Optional[int] = Query(None, description="Year (default: latest)"),
    db: AsyncSession = Depends(get_db),
):
    """Get top export/import categories for a country."""
    # Check country exists
    country_result = await db.execute(select(Country).where(Country.iso3 == iso3))
    country = country_result.scalar_one_or_none()
    if not country:
        raise HTTPException(status_code=404, detail="Country not found")

    # Determine year
    if year is None:
        year_result = await db.execute(
            select(func.max(TradeFlow.year)).where(TradeFlow.reporter_iso3 == iso3)
        )
        year = year_result.scalar_one() or 2024

    # Get all flows for this country/year
    result = await db.execute(
        select(TradeFlow.export_categories, TradeFlow.import_categories)
        .where(
            TradeFlow.reporter_iso3 == iso3,
            TradeFlow.year == year,
        )
    )

    # Aggregate categories across all partners
    export_totals = {}
    import_totals = {}

    for row in result.all():
        if row[0]:  # export_categories
            for cat in row[0]:
                if isinstance(cat, dict):
                    name = cat.get("name", cat.get("category", "Unknown"))
                    value = cat.get("value", 0)
                    export_totals[name] = export_totals.get(name, 0) + value
                elif isinstance(cat, str):
                    export_totals[cat] = export_totals.get(cat, 0) + 1

        if row[1]:  # import_categories
            for cat in row[1]:
                if isinstance(cat, dict):
                    name = cat.get("name", cat.get("category", "Unknown"))
                    value = cat.get("value", 0)
                    import_totals[name] = import_totals.get(name, 0) + value
                elif isinstance(cat, str):
                    import_totals[cat] = import_totals.get(cat, 0) + 1

    # Sort and take top 5
    top_exports = sorted(
        [{"name": k, "value": v} for k, v in export_totals.items()],
        key=lambda x: x["value"],
        reverse=True,
    )[:5]

    top_imports = sorted(
        [{"name": k, "value": v} for k, v in import_totals.items()],
        key=lambda x: x["value"],
        reverse=True,
    )[:5]

    return {
        "reporter_iso3": iso3,
        "year": year,
        "top_exports": top_exports,
        "top_imports": top_imports,
    }
