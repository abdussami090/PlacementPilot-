from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


DriveStatus = Literal[
    "Draft",
    "Published",
    "Closed",
    "Cancelled"
]


class CompanyRecruitmentDriveCreate(BaseModel):
    company_id: int = Field(gt=0)
    placement_cycle_id: int = Field(gt=0)

    name: str = Field(min_length=3, max_length=150)
    description: str | None = None

    application_start_date: date | None = None
    application_deadline: date | None = None

    status: DriveStatus = "Draft"


class CompanyRecruitmentDriveUpdate(BaseModel):
    company_id: int = Field(gt=0)
    placement_cycle_id: int = Field(gt=0)

    name: str = Field(min_length=3, max_length=150)
    description: str | None = None

    application_start_date: date | None = None
    application_deadline: date | None = None

    status: DriveStatus