from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator, model_validator


RoundStatus = Literal[
    "Draft",
    "Scheduled",
    "In Progress",
    "Completed",
    "Cancelled",
]


class PlacementRoundCreate(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    sequence: int = Field(gt=0)
    description: str | None = None
    scheduled_at: datetime | None = None
    scheduled_end: datetime | None = None
    venue: str | None = Field(default=None, max_length=250)
    meeting_link: str | None = Field(default=None, max_length=500)
    status: RoundStatus = "Draft"

    @field_validator("meeting_link")
    @classmethod
    def validate_meeting_link(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = value.strip()
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Meeting links must use a valid HTTP or HTTPS URL.")
        return value

    @model_validator(mode="after")
    def validate_schedule(self):
        if self.scheduled_end and not self.scheduled_at:
            raise ValueError("A scheduled start time is required when an end time is provided")
        if self.scheduled_at and self.scheduled_end and self.scheduled_end < self.scheduled_at:
            raise ValueError("Round end time cannot be before start time")
        if self.status in {"Scheduled", "In Progress", "Completed"} and not self.scheduled_at:
            raise ValueError("A scheduled start time is required for this round status")
        return self


class PlacementRoundUpdate(PlacementRoundCreate):
    status: RoundStatus
