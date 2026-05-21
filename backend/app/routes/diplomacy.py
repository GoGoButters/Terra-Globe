"""Diplomacy endpoints: list relations, bilateral detail."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import DiplomaticRelation, Country
from app.schemas.diplomacy import DiplomaticRelationResponse

router = APIRouter()


@router.get("/diplomacy")
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
        # Get country names
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


@router.get("/diplomacy/{iso3_a}/{iso3_b}")
async def get_diplomatic_relations(
    iso3_a: str,
    iso3_b: str,
    db: AsyncSession = Depends(get_db),
):
    """Get bilateral diplomatic relations between two countries."""
    # Try both orderings
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
        # Return empty response instead of 404 (matches original behavior)
        return DiplomaticRelationResponse(
            country1_iso3=iso3_a,
            country2_iso3=iso3_b,
            summary="Данные о дипломатических отношениях пока не загружены",
            documents=[],
        )

    # Get country names
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
