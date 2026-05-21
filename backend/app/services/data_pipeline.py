"""Data pipeline orchestrator.

Coordinates fetching from World Bank, OWID, and IMF.
Run via POST /api/admin/data/fetch or as a standalone script.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.services import worldbank, owid, imf


class DataPipelineStatus:
    """Tracks pipeline execution status."""

    def __init__(self):
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.worldbank_count: int = 0
        self.owid_count: int = 0
        self.imf_count: int = 0
        self.errors: list[str] = []
        self.status: str = "pending"  # pending, running, completed, failed

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "worldbank_values": self.worldbank_count,
            "owid_values": self.owid_count,
            "imf_values": self.imf_count,
            "total_values": self.worldbank_count + self.owid_count + self.imf_count,
            "errors": self.errors,
        }


# Global status (in production, use Redis or DB)
_last_status: Optional[DataPipelineStatus] = None


async def run_pipeline(
    db: AsyncSession,
    iso3_list: Optional[list[str]] = None,
) -> DataPipelineStatus:
    """Run the full data pipeline.

    Fetches from World Bank, OWID, and IMF concurrently.
    """
    global _last_status
    _last_status = DataPipelineStatus()
    _last_status.started_at = datetime.now(timezone.utc)
    _last_status.status = "running"

    try:
        # Run fetchers concurrently
        tasks = []

        # World Bank
        wb_task = asyncio.create_task(
            worldbank.fetch_all_indicators(db, iso3_list)
        )
        tasks.append(("worldbank", wb_task))

        # OWID
        owid_task = asyncio.create_task(
            owid.fetch_all_indicators(db)
        )
        tasks.append(("owid", owid_task))

        # IMF
        imf_task = asyncio.create_task(
            imf.fetch_all_indicators(db)
        )
        tasks.append(("imf", imf_task))

        # Wait for all tasks
        for source, task in tasks:
            try:
                count = await task
                if source == "worldbank":
                    _last_status.worldbank_count = count
                elif source == "owid":
                    _last_status.owid_count = count
                elif source == "imf":
                    _last_status.imf_count = count
            except Exception as e:
                _last_status.errors.append(f"{source}: {str(e)}")

        _last_status.completed_at = datetime.now(timezone.utc)
        _last_status.status = "completed" if not _last_status.errors else "completed_with_errors"

    except Exception as e:
        _last_status.completed_at = datetime.now(timezone.utc)
        _last_status.status = "failed"
        _last_status.errors.append(f"Pipeline: {str(e)}")

    return _last_status


async def run_pipeline_standalone(iso3_list: Optional[list[str]] = None) -> DataPipelineStatus:
    """Run pipeline as a standalone script."""
    async with async_session_factory() as db:
        async with db.begin():
            return await run_pipeline(db, iso3_list)


def get_last_status() -> Optional[dict]:
    """Get the status of the last pipeline run."""
    if _last_status:
        return _last_status.to_dict()
    return None
