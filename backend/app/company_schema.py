from pydantic import BaseModel


class CompanyCreate(BaseModel):
    name: str
    description: str | None = None
    website: str | None = None
    contact_person: str | None = None
    contact_email: str | None = None


class CompanyUpdate(BaseModel):
    name: str
    description: str | None = None
    website: str | None = None
    contact_person: str | None = None
    contact_email: str | None = None