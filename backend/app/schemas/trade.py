"""Pydantic schemas for trade endpoints."""

from typing import Optional
from pydantic import BaseModel


class TradePartner(BaseModel):
    iso3: str
    name: Optional[str] = None
    export: float = 0.0
    import_: float = 0.0


class TradeCategory(BaseModel):
    name: str
    value: float = 0.0


class TradeSummary(BaseModel):
    reporter_iso3: str
    reporter_name: Optional[str] = None
    total_exports: float = 0.0
    total_imports: float = 0.0
    balance: float = 0.0
    year: int = 2024


class TradePartnersResponse(BaseModel):
    reporter_iso3: str
    year: int
    partners: list[TradePartner]


class TradeCategoriesResponse(BaseModel):
    reporter_iso3: str
    year: int
    top_exports: list[TradeCategory] = []
    top_imports: list[TradeCategory] = []
