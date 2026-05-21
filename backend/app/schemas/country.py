"""Pydantic schemas for country endpoints."""

from typing import Optional
from pydantic import BaseModel


class CountryBrief(BaseModel):
    iso3: str
    name: str
    capital_name: Optional[str] = None
    capital_lat: Optional[float] = None
    capital_lon: Optional[float] = None

    model_config = {"from_attributes": True}


class CountryDetail(BaseModel):
    iso3: str
    iso2: Optional[str] = None
    name: str
    official_name: Optional[str] = None
    region: Optional[str] = None
    subregion: Optional[str] = None
    income_group: Optional[str] = None
    capital_name: Optional[str] = None
    capital_lat: Optional[float] = None
    capital_lon: Optional[float] = None
    population: Optional[int] = None
    area_km2: Optional[float] = None
    indicators: dict[str, float] = {}

    model_config = {"from_attributes": True}
