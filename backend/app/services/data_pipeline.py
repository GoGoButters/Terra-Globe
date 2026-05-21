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
    db: AsyncSession | None = None,
    iso3_list: Optional[list[str]] = None,
) -> DataPipelineStatus:
    """Run the full data pipeline.

    Each source (World Bank, OWID, IMF) gets its own DB session so that
    a failure in one does not corrupt the others.

    If *db* is provided it is used for status tracking only; actual
    fetch operations create their own sessions.
    """
    global _last_status
    _last_status = DataPipelineStatus()
    _last_status.started_at = datetime.now(timezone.utc)
    _last_status.status = "running"

    sources: list[tuple[str, str, bool]] = [
        ("worldbank", "fetch_all_indicators", True),
        ("owid", "fetch_all_indicators", False),
        ("imf", "fetch_all_indicators", False),
    ]

    for source, method_name, pass_iso3 in sources:
        try:
            module = {"worldbank": worldbank, "owid": owid, "imf": imf}[source]
            fetcher = getattr(module, method_name)

            async with async_session_factory() as src_db:
                async with src_db.begin():
                    if pass_iso3:
                        count = await fetcher(src_db, iso3_list)
                    else:
                        count = await fetcher(src_db)

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

    return _last_status


async def run_pipeline_standalone(iso3_list: Optional[list[str]] = None) -> DataPipelineStatus:
    """Run pipeline as a standalone script."""
    return await run_pipeline(iso3_list=iso3_list)


def get_last_status() -> Optional[dict]:
    """Get the status of the last pipeline run."""
    if _last_status:
        return _last_status.to_dict()
    return None
