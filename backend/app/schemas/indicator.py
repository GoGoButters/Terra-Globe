"""Pydantic schemas for indicator endpoints."""

from typing import Optional, Any
from pydantic import BaseModel


class IndicatorDefinitionResponse(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    unit: Optional[str] = None
    source: Optional[str] = None
    source_url: Optional[str] = None
    methodology: Optional[str] = None
    display_type: Optional[str] = None
    categories: Optional[Any] = None
    gradient_stops: Optional[Any] = None

    model_config = {"from_attributes": True}


class IndicatorValueResponse(BaseModel):
    country_iso3: str
    indicator_code: str
    year: int
    value: Optional[float] = None

    model_config = {"from_attributes": True}


class IndicatorMapResponse(BaseModel):
    indicator_code: str
    year: int
    values: dict[str, float]  # {iso3: value}
