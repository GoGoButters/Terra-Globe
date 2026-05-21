"""Pydantic schemas for diplomacy endpoints."""

from typing import Optional, Any
from pydantic import BaseModel


class DiplomaticDocument(BaseModel):
    title: str
    year: Optional[int] = None
    type: Optional[str] = None
    description: Optional[str] = None


class DiplomaticRelationResponse(BaseModel):
    country1_iso3: str
    country1_name: Optional[str] = None
    country2_iso3: str
    country2_name: Optional[str] = None
    summary: Optional[str] = None
    documents: list[DiplomaticDocument] = []
