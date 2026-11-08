from datetime import datetime

from pydantic import BaseModel, Field


class JobEligibilityCreate(BaseModel):

    eligible_courses: list[str] = Field(
        default_factory=list
    )

    eligible_branches: list[str] = Field(
        default_factory=list
    )

    graduation_years: list[int] = Field(
        default_factory=list
    )

    min_cgpa: float | None = Field(
        default=None,
        ge=0,
        le=10
    )

    max_active_backlogs: int | None = Field(
        default=None,
        ge=0,
        le=50
    )

    notes: str | None = None


class JobEligibilityResponse(BaseModel):

    id: int
    job_id: int
    eligible_courses: list[str]
    eligible_branches: list[str]
    graduation_years: list[int]
    min_cgpa: float | None
    max_active_backlogs: int | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True