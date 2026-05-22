import asyncio
import logging
from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.session import async_session_factory
from app.routes import auth, countries, indicators, alliances, trade, diplomacy, admin
from app.services.data_pipeline import run_pipeline
from scripts.seed_data import run_seed

settings = get_settings()
logger = logging.getLogger(__name__)


def _run_alembic() -> None:
    """Run alembic migrations synchronously before app starts."""
    alembic_cfg = Config("/app/alembic.ini")
    command.upgrade(alembic_cfg, "head")
    logger.info("Alembic migrations applied")


async def _seed_static_data() -> None:
    """Seed countries, alliances, trade, diplomacy from static files."""
    logger.info("Seeding static data...")
    await run_seed()
    logger.info("Static data seed complete")


async def _run_pipeline_background() -> None:
    """Run data pipeline in background (non-blocking)."""
    try:
        status = await run_pipeline()
        result = status.to_dict()
        logger.info(
            "Background pipeline completed: %d values (WB=%d, OWID=%d, IMF=%d), errors=%d",
            result["total_values"],
            result["worldbank_values"],
            result["owid_values"],
            result["imf_values"],
            len(result["errors"]),
        )
        if result["errors"]:
            for err in result["errors"]:
                logger.warning("Pipeline error: %s", err)
    except Exception:
        logger.exception("Background data pipeline failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup sequence: migrations → seed → background pipeline."""
    try:
        # 1. Run alembic migrations in a thread (avoids asyncio.run() conflict)
        logger.info("Running alembic migrations...")
        await asyncio.to_thread(_run_alembic)
    except Exception:
        logger.exception("Alembic migrations failed — continuing anyway")

    try:
        # 2. Seed static data (countries, alliances, etc.)
        await _seed_static_data()
    except Exception:
        logger.exception("Static data seed failed — continuing anyway")

    try:
        # 3. Kick off external data pipeline in background
        asyncio.create_task(_run_pipeline_background())
    except Exception:
        logger.exception("Background pipeline task failed to start")

    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Terra Globe API",
        description="Geopolitical globe backend with real-time data from World Bank, OWID, and IMF.",
        version="2.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )

    # ── CORS ──
    origins = [settings.frontend_url or "http://localhost:80"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ──
    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(countries.router, prefix="/api", tags=["countries"])
    app.include_router(indicators.router, prefix="/api", tags=["indicators"])
    app.include_router(alliances.router, prefix="/api", tags=["alliances"])
    app.include_router(trade.router, prefix="/api", tags=["trade"])
    app.include_router(diplomacy.router, prefix="/api", tags=["diplomacy"])
    app.include_router(admin.router, prefix="/api/admin", tags=["admin"])

    # ── Health check ──
    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": "2.0.0"}

    # ── Config endpoint (public) ──
    @app.get("/api/config")
    async def get_config():
        return {
            "cesium_ion_token": settings.cesium_ion_token,
            "oauth_providers": ["google"] if settings.google_client_id else [],
        }

    return app


app = create_app()
