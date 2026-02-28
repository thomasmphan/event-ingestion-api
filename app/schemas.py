import uuid

from datetime import datetime, timezone
from pydantic import BaseModel, Field, model_validator
from typing import Any


class EventCreate(BaseModel):
    event_type: str = Field(..., min_length=1, max_length=100)
    source: str | None = Field(None, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime | None = Field(None)

    @model_validator(mode="after")
    def default_timestamp(self) -> "EventCreate":
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)
        return self


class EventResponse(BaseModel):
    id: uuid.UUID
    event_type: str
    source: str | None
    payload: dict[str, Any]
    timestamp: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class EventListResponse(BaseModel):
    items: list[EventResponse]
    total: int
    limit: int
    next_cursor: str | None  # None = no more pages


class ReadinessResponse(BaseModel):
    status: str
    db: str


class LivenessResponse(BaseModel):
    status: str
    uptime_seconds: int
