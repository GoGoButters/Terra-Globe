from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.routes import auth, countries, indicators, alliances, trade, diplomacy, admin

settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Terra Globe API",
        description="Geopolitical globe backend with real-time data from World Bank, OWID, and IMF.",
        version="2.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
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
