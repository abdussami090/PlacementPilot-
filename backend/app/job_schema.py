from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    recruitment_drive_id: int = Field(gt=0)
    role: str = Field(min_length=2, max_length=150)
    package: str | None = None
    location: str | None = None
    status: str = "Open"


class JobUpdate(BaseModel):
    role: str = Field(min_length=2, max_length=150)
    package: str | None = None
    location: str | None = None
    status: str