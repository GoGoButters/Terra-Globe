from datetime import datetime, timezone
from uuid import uuid4, UUID
from typing import Optional

from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime,
    BigInteger, Boolean, ForeignKey, UniqueConstraint, Index,
    JSON, func,
)
from sqlalchemy.orm import DeclarativeBase, relationship
from geoalchemy2 import Geometry


class Base(DeclarativeBase):
    pass


class Country(Base):
    """Country with geographic boundaries and metadata."""

    __tablename__ = "countries"

    iso3 = Column(String(3), primary_key=True)
    iso2 = Column(String(2), nullable=True)
    name = Column(String(100), nullable=False, index=True)
    official_name = Column(String(200), nullable=True)
    region = Column(String(50), nullable=True)
    subregion = Column(String(50), nullable=True)
    income_group = Column(String(50), nullable=True)

    geometry = Column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)
    centroid = Column(Geometry("POINT", srid=4326), nullable=True)

    capital_name = Column(String(100), nullable=True)
    capital_lat = Column(Float, nullable=True)
    capital_lon = Column(Float, nullable=True)

    population = Column(BigInteger, nullable=True)
    area_km2 = Column(Float, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    indicator_values = relationship("IndicatorValue", back_populates="country")
    alliance_members = relationship("AllianceMember", back_populates="country")

    __table_args__ = (
        Index("idx_countries_geometry", "geometry", postgresql_using="gist"),
        Index("idx_countries_centroid", "centroid", postgresql_using="gist"),
    )


class IndicatorDefinition(Base):
    """Metadata for an economic/social indicator."""

    __tablename__ = "indicator_definitions"

    code = Column(String(50), primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=True, index=True)
    unit = Column(String(50), nullable=True)

    source = Column(String(20), nullable=True)  # worldbank, owid, imf
    source_code = Column(String(50), nullable=True)
    source_url = Column(String(500), nullable=True)

    methodology = Column(Text, nullable=True)
    display_type = Column(String(20), nullable=True)  # categorical, gradient

    categories = Column(JSON, nullable=True)
    gradient_stops = Column(JSON, nullable=True)

    sort_order = Column(Integer, default=0)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    values = relationship("IndicatorValue", back_populates="definition")


class IndicatorValue(Base):
    """Time-series value for a country-indicator pair."""

    __tablename__ = "indicator_values"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    country_iso3 = Column(String(3), ForeignKey("countries.iso3"), nullable=False)
    indicator_code = Column(String(50), ForeignKey("indicator_definitions.code"), nullable=False)
    year = Column(Integer, nullable=False)
    value = Column(Float, nullable=True)

    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    country = relationship("Country", back_populates="indicator_values")
    definition = relationship("IndicatorDefinition", back_populates="values")

    __table_args__ = (
        UniqueConstraint("country_iso3", "indicator_code", "year", name="uq_indicator_value"),
        Index("idx_indicator_values_lookup", "country_iso3", "indicator_code", "year"),
    )


class Alliance(Base):
    """Political/economic alliance or organization."""

    __tablename__ = "alliances"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    color = Column(String(7), nullable=True)  # hex color
    founded = Column(Integer, nullable=True)
    headquarters = Column(String(100), nullable=True)
    info = Column(Text, nullable=True)
    features = Column(JSON, nullable=True)

    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    members = relationship("AllianceMember", back_populates="alliance")


class AllianceMember(Base):
    """Membership of a country in an alliance."""

    __tablename__ = "alliance_members"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    alliance_id = Column(BigInteger, ForeignKey("alliances.id"), nullable=False)
    country_iso3 = Column(String(3), ForeignKey("countries.iso3"), nullable=False)
    joined_year = Column(Integer, nullable=True)

    # Relationships
    alliance = relationship("Alliance", back_populates="members")
    country = relationship("Country", back_populates="alliance_members")

    __table_args__ = (
        UniqueConstraint("alliance_id", "country_iso3", name="uq_alliance_member"),
    )


class TradeFlow(Base):
    """Bilateral trade flow between two countries."""

    __tablename__ = "trade_flows"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    reporter_iso3 = Column(String(3), ForeignKey("countries.iso3"), nullable=False)
    partner_iso3 = Column(String(3), ForeignKey("countries.iso3"), nullable=False)
    year = Column(Integer, nullable=False)

    export_value_usd = Column(Float, nullable=True)
    import_value_usd = Column(Float, nullable=True)

    export_categories = Column(JSON, nullable=True)
    import_categories = Column(JSON, nullable=True)

    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("reporter_iso3", "partner_iso3", "year", name="uq_trade_flow"),
        Index("idx_trade_flows_reporter", "reporter_iso3", "year"),
        Index("idx_trade_flows_partner", "partner_iso3", "year"),
    )


class DiplomaticRelation(Base):
    """Bilateral diplomatic relations between two countries."""

    __tablename__ = "diplomatic_relations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    country_iso3_a = Column(String(3), ForeignKey("countries.iso3"), nullable=False)
    country_iso3_b = Column(String(3), ForeignKey("countries.iso3"), nullable=False)

    summary = Column(Text, nullable=True)
    documents = Column(JSON, nullable=True)
    source_url = Column(String(500), nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("country_iso3_a", "country_iso3_b", name="uq_diplomatic_relation"),
    )


class User(Base):
    """Application user (local or OAuth)."""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email = Column(String(255), unique=True, nullable=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)
    full_name = Column(String(200), nullable=True)
    avatar_url = Column(String(500), nullable=True)

    oauth_provider = Column(String(20), nullable=True)  # google, github
    oauth_id = Column(String(255), nullable=True)

    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    refresh_tokens = relationship("RefreshToken", back_populates="user")


class RefreshToken(Base):
    """JWT refresh token tracking."""

    __tablename__ = "refresh_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="refresh_tokens")


class APICache(Base):
    """Cache for external API responses."""

    __tablename__ = "api_cache"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source = Column(String(20), nullable=False, index=True)  # worldbank, owid, imf
    cache_key = Column(String(500), nullable=False, index=True)
    response_data = Column(JSON, nullable=True)
    cached_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_api_cache_lookup", "source", "cache_key"),
    )
