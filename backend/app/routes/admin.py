"""Admin endpoints: trigger data fetch, check status."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import APICache
from app.services.data_pipeline import run_pipeline, get_last_status

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/data/fetch")
async def fetch_external_data(
    background_tasks: BackgroundTasks,
):
    """Trigger data fetch from World Bank, OWID, IMF.

    Runs asynchronously in the background with its own DB session.
    """

    async def _run_pipeline():
        status = await run_pipeline()
        result = status.to_dict()
        logger.info(
            "Manual pipeline completed: %d values, errors=%d",
            result["total_values"],
            len(result["errors"]),
        )
        if result["errors"]:
            for err in result["errors"]:
                logger.warning("Pipeline error: %s", err)

    background_tasks.add_task(_run_pipeline)

    return {
        "status": "started",
        "message": "Data fetch pipeline started in background",
    }


@router.get("/data/status")
async def fetch_status(db: AsyncSession = Depends(get_db)):
    """Get status of last data fetch from each source."""
    # Get pipeline status
    pipeline_status = get_last_status()

    # Get cache status per source
    sources = ["worldbank", "owid", "imf"]
    cache_status = {}

    for source in sources:
        result = await db.execute(
            select(func.count(APICache.id), func.max(APICache.cached_at))
            .where(APICache.source == source)
        )
        row = result.first()
        cache_status[source] = {
            "cached_entries": row[0] if row else 0,
            "last_cached": row[1].isoformat() if row and row[1] else None,
        }

    return {
        "pipeline": pipeline_status,
        "cache": cache_status,
    }
