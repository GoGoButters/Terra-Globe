"""Pydantic schemas for alliance endpoints."""

from typing import Optional, Any
from pydantic import BaseModel


class AllianceMemberBrief(BaseModel):
    country_iso3: str
    country_name: Optional[str] = None
    joined_year: Optional[int] = None


class AllianceResponse(BaseModel):
    code: str
    name: str
    color: Optional[str] = None
    founded: Optional[int] = None
    headquarters: Optional[str] = None
    info: Optional[str] = None
    features: Optional[list[str]] = None
    members: list[AllianceMemberBrief] = []

    model_config = {"from_attributes": True}


class AllianceListResponse(BaseModel):
    code: str
    name: str
    color: Optional[str] = None
    member_count: int
