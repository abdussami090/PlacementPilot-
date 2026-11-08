from pydantic import BaseModel


class ApplicationCreate(BaseModel):
    job_id: int


class ApplicationStatusUpdate(BaseModel):
    status: str