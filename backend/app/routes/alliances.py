"""Alliance endpoints: list and detail."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import Alliance, AllianceMember, Country
from app.schemas.alliance import AllianceResponse, AllianceListResponse

router = APIRouter()


@router.get("/alliances", response_model=list[AllianceListResponse])
async def list_alliances(db: AsyncSession = Depends(get_db)):
    """List all alliances with member counts."""
    result = await db.execute(select(Alliance).order_by(Alliance.name))
    alliances = result.scalars().all()

    response = []
    for alliance in alliances:
        count_result = await db.execute(
            select(func.count()).where(AllianceMember.alliance_id == alliance.id)
        )
        count = count_result.scalar_one() or 0
        response.append(
            AllianceListResponse(
                code=alliance.code,
                name=alliance.name,
                color=alliance.color,
                member_count=count,
            )
        )

    return response


@router.get("/alliances/{code}", response_model=AllianceResponse)
async def get_alliance(code: str, db: AsyncSession = Depends(get_db)):
    """Get alliance details with members."""
    result = await db.execute(
        select(Alliance).where(Alliance.code == code)
    )
    alliance = result.scalar_one_or_none()
    if not alliance:
        raise HTTPException(status_code=404, detail="Alliance not found")

    # Get members with country names
    members_result = await db.execute(
        select(AllianceMember, Country.name)
        .join(Country, Country.iso3 == AllianceMember.country_iso3)
        .where(AllianceMember.alliance_id == alliance.id)
        .order_by(Country.name)
    )

    members = [
        {
            "country_iso3": row[0].country_iso3,
            "country_name": row[1],
            "joined_year": row[0].joined_year,
        }
        for row in members_result.all()
    ]

    return AllianceResponse(
        code=alliance.code,
        name=alliance.name,
        color=alliance.color,
        founded=alliance.founded,
        headquarters=alliance.headquarters,
        info=alliance.info,
        features=alliance.features or [],
        members=members,
    )
