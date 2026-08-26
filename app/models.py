from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Severity(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class IncidentStatus(StrEnum):
    open = "open"
    investigating = "investigating"
    resolved = "resolved"


class IncidentData(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=3, max_length=1_000)
    severity: Severity
    status: IncidentStatus


class IncidentCreate(IncidentData):
    pass


class Incident(IncidentData):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    id: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime


class IncidentList(BaseModel):
    items: list[Incident]
    returned: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    next_cursor: int | None = Field(default=None, ge=1)
