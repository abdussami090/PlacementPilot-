from pydantic import BaseModel, Field


class EducationCreate(BaseModel):

    degree: str
    college: str
    year: str
    cgpa: str

    graduation_year: int | None = Field(
        default=None,
        ge=2020,
        le=2100
    )

    active_backlogs: int = Field(
        default=0,
        ge=0,
        le=50
    )