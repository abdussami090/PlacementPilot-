from pydantic import BaseModel


class ProfileCreate(BaseModel):
    college: str
    branch: str
    year: str
    linkedin: str
    github: str
    skills: str


class ProfileResponse(BaseModel):
    id: int
    college: str
    branch: str
    year: str
    linkedin: str
    github: str
    skills: str

    class Config:
        from_attributes = True