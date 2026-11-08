from pydantic import BaseModel, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Name must contain at least 2 non-space characters.")
        return value

    @field_validator("password")
    @classmethod
    def enforce_bcrypt_byte_limit(cls, value: str) -> str:
        # bcrypt 5 rejects passwords longer than 72 UTF-8 bytes.
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be 72 UTF-8 bytes or fewer.")
        return value


class UserLogin(BaseModel):
    email: EmailStr
    password: str
