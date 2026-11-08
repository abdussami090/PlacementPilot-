from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


CycleStatus = Literal[
    "Draft",
    "Active",
    "Completed",
    "Cancelled"
]


class PlacementCycleCreate(BaseModel):
    name: str = Field(min_length=3, max_length=150)
    academic_year: str
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: CycleStatus = "Draft"

    @model_validator(mode="after")
    def validate_dates(self):
        if (
            self.start_date
            and self.end_date
            and self.end_date < self.start_date
        ):
            raise ValueError("End date cannot be before start date")

        return self


class PlacementCycleUpdate(BaseModel):
    name: str = Field(min_length=3, max_length=150)
    academic_year: str
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: CycleStatus

    @model_validator(mode="after")
    def validate_dates(self):
        if (
            self.start_date
            and self.end_date
            and self.end_date < self.start_date
        ):
            raise ValueError("End date cannot be before start date")

        return self