from pydantic import BaseModel, Field


class StudentAcademicDetailsCreate(BaseModel):

    course: str = Field(
        min_length=2,
        max_length=100
    )

    graduation_year: int = Field(
        ge=2020,
        le=2100
    )

    cgpa: float = Field(
        ge=0,
        le=10
    )

    active_backlogs: int = Field(
        default=0,
        ge=0,
        le=50
    )


class StudentAcademicDetailsResponse(BaseModel):

    id: int
    course: str
    graduation_year: int
    cgpa: float
    active_backlogs: int

    class Config:
        from_attributes = True