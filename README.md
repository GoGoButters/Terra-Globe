# TerraGlobe — Geopolitical Globe

Interactive 3D geopolitical globe with real-time data from World Bank, Our World in Data, and IMF. Built with CesiumJS, FastAPI, PostgreSQL+PostGIS, and JWT + Google OAuth authentication.

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-336791.svg)](https://www.postgresql.org/)
[![CesiumJS](https://img.shields.io/badge/CesiumJS-1.113-0071BC.svg)](https://cesium.com/cesiumjs/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://www.docker.com/)

---

## Features

| Feature | Description |
|---------|-------------|
| **Country Explorer** | Click any country to view 20+ indicators across Economy, Society, Politics, and Military |
| **Data Layers** | 18+ choropleth layers with metadata, methodology, and source links |
| **Alliances** | 10 international alliances (EU, NATO, BRICS, CSTO, SCO, etc.) with color-coded visualization |
| **Country Comparison** | Select two countries and compare indicators side-by-side with color-coded better/worse |
| **Trade Flows** | Visualize bilateral trade with great-circle arcs, partner breakdown, and top categories |
| **Diplomacy** | View bilateral diplomatic relations and signed documents |
| **Authentication** | JWT + Google OAuth2 with access/refresh token rotation |
| **Real Data** | Automatic data fetching from World Bank, OWID, and IMF APIs |

---

## Quick Start

### Prerequisites

- **Docker** and **Docker Compose** (v2+)
- **Git**

### 1. Clone the Repository

```bash
git clone https://github.com/GoGoButters/Terra-Globe.git
cd Terra-Globe
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and set the following values:

| Variable | Description | Example |
|----------|-------------|---------|
| `POSTGRES_PASSWORD` | Database password | `my_secure_password_123` |
| `REDIS_PASSWORD` | Redis password | `my_redis_password` |
| `SECRET_KEY` | JWT signing key | Run: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID | `xxx.apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Client Secret | `GOCSPX-xxx` |
| `GOOGLE_REDIRECT_URI` | OAuth callback URL | `http://localhost:80/api/auth/google/callback` |
| `CESIUM_ION_TOKEN` | Cesium Ion access token | Get free at [ion.cesium.com](https://ion.cesium.com) |

> **Note:** Google OAuth is optional. The app works without it — just password-based auth.

### 3. Launch

```bash
docker compose up -d --build
```

This starts 4 containers:
- **PostgreSQL 16 + PostGIS** — database with geographic extensions
- **Redis 7** — session cache and rate limiting
- **FastAPI Backend** — REST API on port 8000 (internal)
- **Nginx** — reverse proxy + static file server on port 80

### 4. Seed the Database

Load existing static data (countries, indicators, alliances, trade, diplomacy) into the database:

```bash
docker compose exec backend python scripts/seed_data.py
```

### 5. Open the Application

- **Frontend**: [http://localhost:80](http://localhost:80)
- **API Docs (Swagger)**: [http://localhost:80/api/docs](http://localhost:80/api/docs)
- **API Docs (ReDoc)**: [http://localhost:80/api/redoc](http://localhost:80/api/redoc)

---

## Fetching Real Data

After seeding, you can pull live data from external APIs:

```bash
# Trigger data fetch (runs in background)
curl -X POST http://localhost:80/api/admin/data/fetch

# Check fetch status
curl http://localhost:80/api/admin/data/status
```

Or via Swagger UI at `/api/docs`.

### Data Sources

| Source | Indicators | Update Frequency | Auth Required |
|--------|-----------|-----------------|---------------|
| **World Bank** | GDP, population, inflation, unemployment, Gini, life expectancy, literacy, military budget | Annual | No |
| **Our World in Data** | HDI, democracy index, corruption perception, press freedom, political stability | Annual | No |
| **IMF SDMX** | GDP growth, government debt, current account balance, international reserves | Annual/Quarterly | No |

All fetched data is cached in the database for 24 hours to minimize API calls.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Nginx (port 80)                       │
│  ┌──────────────────────┐  ┌──────────────────────────────┐  │
│  │  Static Files        │  │  API Proxy /api/*            │  │
│  │  index.html, JS, CSS │  │  → FastAPI (port 8000)       │  │
│  │  gzip + 30d cache    │  │  gzip + timeouts             │  │
│  └──────────────────────┘  └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
     ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
     │  FastAPI    │  │ PostgreSQL  │  │   Redis 7   │
     │  (async)    │  │ 16+PostGIS  │  │             │
     │             │  │             │  │  Sessions   │
     │ JWT Auth    │  │ 10 tables   │  │  Rate limit │
     │ Google OAuth│  │ GeoJSON     │  │  Cache      │
     │ Data Pipeline│ │ GIST idx    │  │             │
     └─────────────┘  └─────────────┘  └─────────────┘
```

---

## API Reference

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/register` | Register with email + password |
| `POST` | `/api/auth/login` | Login with email + password |
| `POST` | `/api/auth/refresh` | Refresh access token |
| `POST` | `/api/auth/logout` | Revoke refresh token |
| `GET`  | `/api/auth/google/login` | Initiate Google OAuth |
| `GET`  | `/api/auth/google/callback` | Handle OAuth callback |
| `GET`  | `/api/auth/me` | Get current user (requires auth) |

### Countries

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/countries` | List all countries (optional `?bbox=` filter) |
| `GET` | `/api/countries/{iso3}` | Country details with latest indicators |
| `GET` | `/api/countries/geojson` | Full GeoJSON FeatureCollection (optional `?simplify=`) |

### Indicators

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/indicators/definitions` | All layer metadata |
| `GET` | `/api/indicators/values` | Values with filters (`?codes=`, `?countries=`, `?year=`) |
| `GET` | `/api/indicators/{code}/map` | Choropleth data as `{iso3: value}` |

### Alliances

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/alliances` | List all alliances with member counts |
| `GET` | `/api/alliances/{code}` | Alliance details with members |

### Trade

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/trade/{iso3}` | Trade summary (exports, imports, balance) |
| `GET` | `/api/trade/{iso3}/partners` | Top trade partners |
| `GET` | `/api/trade/{iso3}/categories` | Top export/import categories |

### Diplomacy

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/diplomacy` | List all relations (optional `?country=` filter) |
| `GET` | `/api/diplomacy/{iso3_a}/{iso3_b}` | Bilateral relations |

### Admin

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/admin/data/fetch` | Trigger data fetch from external APIs |
| `GET`  | `/api/admin/data/status` | Fetch status and cache info |

### Public

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/config` | Public config (Cesium token, OAuth providers) |

---

## Database Schema

```
countries            — ISO3 PK, geometry MULTIPOLYGON (GIST), centroid POINT (GIST)
indicator_definitions — code PK, source, display_type, categories JSONB
indicator_values      — time-series (country, indicator, year, value)
alliances             — political/economic organizations
alliance_members      — country membership in alliances
trade_flows           — bilateral trade (reporter, partner, year, exports, imports)
diplomatic_relations  — bilateral relations with documents JSONB
users                 — application users (local + OAuth)
refresh_tokens        — JWT refresh token tracking (revocable)
api_cache             — external API response cache with TTL
```

---

## Project Structure

```
Terra-Globe/
├── docker-compose.yml              # 4-service orchestration
├── .env.example                    # environment template
├── .gitignore
├── README.md
│
├── nginx/
│   └── default.conf                # reverse proxy + gzip + caching
│
├── db/
│   └── init/
│       └── 01_extensions.sql       # PostGIS + uuid-ossp
│
├── backend/
│   ├── Dockerfile                  # python:3.12-slim multi-stage
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py                  # async migration runner
│   │   └── versions/
│   │       └── 001_initial_schema.py
│   ├── app/
│   │   ├── main.py                 # FastAPI app factory
│   │   ├── config.py               # pydantic-settings
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   └── session.py          # async SQLAlchemy session
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── country.py          # all 10 SQLAlchemy models
│   │   ├── schemas/                # Pydantic request/response
│   │   │   ├── auth.py
│   │   │   ├── country.py
│   │   │   ├── indicator.py
│   │   │   ├── alliance.py
│   │   │   ├── trade.py
│   │   │   └── diplomacy.py
│   │   ├── routes/                 # API endpoint handlers
│   │   │   ├── auth.py
│   │   │   ├── countries.py
│   │   │   ├── indicators.py
│   │   │   ├── alliances.py
│   │   │   ├── trade.py
│   │   │   ├── diplomacy.py
│   │   │   └── admin.py
│   │   ├── services/
│   │   │   ├── auth_service.py     # JWT, bcrypt, OAuth
│   │   │   ├── worldbank.py        # World Bank API fetcher
│   │   │   ├── owid.py             # OWID CSV fetcher
│   │   │   ├── imf.py              # IMF SDMX fetcher
│   │   │   └── data_pipeline.py    # async orchestrator
│   │   └── utils/
│   └── scripts/
│       └── seed_data.py            # seed from static files
│
└── frontend/
    ├── index.html
    ├── css/
    │   ├── style.css
    │   ├── legend.css
    │   └── auth.css                # login modal styles
    ├── js/
    │   ├── config.js               # API config, Cesium token
    │   ├── api.js                  # fetch wrapper + JWT + auto-refresh
    │   ├── auth.js                 # AuthManager + login modal + Google OAuth
    │   ├── GlobeApp.js             # main orchestrator
    │   ├── DataStore.js            # country data from API
    │   ├── LayerManager.js         # choropleth + alliance rendering
    │   ├── CountryCard.js          # country info panel
    │   ├── CapitalsManager.js      # capital city labels
    │   ├── TradeManager.js         # trade flow visualization
    │   ├── DiplomacyManager.js     # bilateral relations
    │   └── ui.js                   # UI event handlers
    └── data/                       # seed source files (not used at runtime)
```

---

## Development

### Run Without Docker

```bash
# 1. Install dependencies
cd backend
pip install -r requirements.txt

# 2. Set environment variables
export DATABASE_URL="postgresql+asyncpg://terraglobe:password@localhost:5432/terraglobe"
export SECRET_KEY="your-secret-key"
export CESIUM_ION_TOKEN="your-token"

# 3. Start PostgreSQL + Redis (via Docker)
docker compose up -d db redis

# 4. Run migrations
alembic upgrade head

# 5. Seed database
python scripts/seed_data.py

# 6. Start backend
uvicorn app.main:app --reload --port 8000

# 7. Serve frontend
cd ../frontend
python3 -m http.server 3000
```

### Run Migrations

```bash
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head
```

### Run Tests

```bash
cd backend
pytest
```

---

## Troubleshooting

### Container won't start

```bash
# Check logs
docker compose logs backend
docker compose logs db

# Verify .env exists
ls -la .env
```

### Database connection refused

```bash
# Wait for PostgreSQL health check
docker compose ps

# Test connection
docker compose exec db pg_isready -U terraglobe
```

### Cesium globe not loading

- Verify `CESIUM_ION_TOKEN` is set in `.env`
- Check browser console for CORS errors
- Ensure Nginx is running: `docker compose ps nginx`

### Google OAuth not working

- Verify `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env`
- Add `http://localhost:80/api/auth/google/callback` to authorized redirect URIs in Google Cloud Console
- Check that `GOOGLE_REDIRECT_URI` matches exactly

### Port 80 already in use

```bash
# Change port in docker-compose.yml
# Or stop the conflicting service:
sudo lsof -i :80
```

---

## License

MIT

---

## Credits

- **CesiumJS** — 3D globe rendering
- **globe.gl** — inspiration for data visualization approach
- **World Bank Open Data** — economic indicators
- **Our World in Data** — social and political indicators
- **IMF SDMX** — macroeconomic forecasts
