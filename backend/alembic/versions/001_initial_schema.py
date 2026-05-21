"""Initial schema: countries, indicators, alliances, trade, diplomacy, users

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-05-21

"""
from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry

revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── countries ──
    op.create_table(
        "countries",
        sa.Column("iso3", sa.String(3), primary_key=True),
        sa.Column("iso2", sa.String(2), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("official_name", sa.String(200), nullable=True),
        sa.Column("region", sa.String(50), nullable=True),
        sa.Column("subregion", sa.String(50), nullable=True),
        sa.Column("income_group", sa.String(50), nullable=True),
        sa.Column("geometry", Geometry("MULTIPOLYGON", srid=4326), nullable=True),
        sa.Column("centroid", Geometry("POINT", srid=4326), nullable=True),
        sa.Column("capital_name", sa.String(100), nullable=True),
        sa.Column("capital_lat", sa.Float, nullable=True),
        sa.Column("capital_lon", sa.Float, nullable=True),
        sa.Column("population", sa.BigInteger, nullable=True),
        sa.Column("area_km2", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("idx_countries_name", "countries", ["name"])
    op.create_index("idx_countries_geometry", "countries", ["geometry"], postgresql_using="gist")
    op.create_index("idx_countries_centroid", "countries", ["centroid"], postgresql_using="gist")

    # ── indicator_definitions ──
    op.create_table(
        "indicator_definitions",
        sa.Column("code", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("source", sa.String(20), nullable=True),
        sa.Column("source_code", sa.String(50), nullable=True),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("methodology", sa.Text, nullable=True),
        sa.Column("display_type", sa.String(20), nullable=True),
        sa.Column("categories", sa.JSON, nullable=True),
        sa.Column("gradient_stops", sa.JSON, nullable=True),
        sa.Column("sort_order", sa.Integer, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("idx_indicator_definitions_category", "indicator_definitions", ["category"])

    # ── indicator_values ──
    op.create_table(
        "indicator_values",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("country_iso3", sa.String(3), sa.ForeignKey("countries.iso3"), nullable=False),
        sa.Column("indicator_code", sa.String(50), sa.ForeignKey("indicator_definitions.code"), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("value", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_indicator_value", "indicator_values", ["country_iso3", "indicator_code", "year"])
    op.create_index("idx_indicator_values_lookup", "indicator_values", ["country_iso3", "indicator_code", "year"])

    # ── alliances ──
    op.create_table(
        "alliances",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(20), unique=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("founded", sa.Integer, nullable=True),
        sa.Column("headquarters", sa.String(100), nullable=True),
        sa.Column("info", sa.Text, nullable=True),
        sa.Column("features", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("idx_alliances_code", "alliances", ["code"])

    # ── alliance_members ──
    op.create_table(
        "alliance_members",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("alliance_id", sa.BigInteger, sa.ForeignKey("alliances.id"), nullable=False),
        sa.Column("country_iso3", sa.String(3), sa.ForeignKey("countries.iso3"), nullable=False),
        sa.Column("joined_year", sa.Integer, nullable=True),
    )
    op.create_unique_constraint("uq_alliance_member", "alliance_members", ["alliance_id", "country_iso3"])

    # ── trade_flows ──
    op.create_table(
        "trade_flows",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("reporter_iso3", sa.String(3), sa.ForeignKey("countries.iso3"), nullable=False),
        sa.Column("partner_iso3", sa.String(3), sa.ForeignKey("countries.iso3"), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("export_value_usd", sa.Float, nullable=True),
        sa.Column("import_value_usd", sa.Float, nullable=True),
        sa.Column("export_categories", sa.JSON, nullable=True),
        sa.Column("import_categories", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_trade_flow", "trade_flows", ["reporter_iso3", "partner_iso3", "year"])
    op.create_index("idx_trade_flows_reporter", "trade_flows", ["reporter_iso3", "year"])
    op.create_index("idx_trade_flows_partner", "trade_flows", ["partner_iso3", "year"])

    # ── diplomatic_relations ──
    op.create_table(
        "diplomatic_relations",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("country_iso3_a", sa.String(3), sa.ForeignKey("countries.iso3"), nullable=False),
        sa.Column("country_iso3_b", sa.String(3), sa.ForeignKey("countries.iso3"), nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("documents", sa.JSON, nullable=True),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_unique_constraint("uq_diplomatic_relation", "diplomatic_relations", ["country_iso3_a", "country_iso3_b"])

    # ── users ──
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=True),
        sa.Column("username", sa.String(50), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=True),
        sa.Column("full_name", sa.String(200), nullable=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("oauth_provider", sa.String(20), nullable=True),
        sa.Column("oauth_id", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("is_superuser", sa.Boolean, server_default=sa.text("false")),
        sa.Column("last_login", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("idx_users_email", "users", ["email"])
    op.create_index("idx_users_username", "users", ["username"])

    # ── refresh_tokens ──
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("revoked", sa.Boolean, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("idx_refresh_tokens_hash", "refresh_tokens", ["token_hash"])

    # ── api_cache ──
    op.create_table(
        "api_cache",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("cache_key", sa.String(500), nullable=False),
        sa.Column("response_data", sa.JSON, nullable=True),
        sa.Column("cached_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime, nullable=False),
    )
    op.create_index("idx_api_cache_source", "api_cache", ["source"])
    op.create_index("idx_api_cache_lookup", "api_cache", ["source", "cache_key"])


def downgrade() -> None:
    op.drop_table("api_cache")
    op.drop_table("refresh_tokens")
    op.drop_table("users")
    op.drop_table("diplomatic_relations")
    op.drop_table("trade_flows")
    op.drop_table("alliance_members")
    op.drop_table("alliances")
    op.drop_table("indicator_values")
    op.drop_table("indicator_definitions")
    op.drop_table("countries")
