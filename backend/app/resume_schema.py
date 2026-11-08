from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator


class ResumeCreate(BaseModel):
    resume_name: str = Field(min_length=1, max_length=120)
    resume_link: str = Field(min_length=1, max_length=2048)

    @field_validator("resume_link")
    @classmethod
    def require_http_url(cls, value: str) -> str:
        value = value.strip()
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Resume links must use a valid HTTP or HTTPS URL.")
        return value
