"""Password hashing and JWT helpers for PlacementPilot."""

from datetime import datetime, timedelta, timezone

from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import (
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)

# Swagger uses this route to obtain an access token.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# Existing bcrypt hashes remain compatible with this context.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string.")
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except (TypeError, ValueError):
        return False


def create_access_token(data: dict) -> str:
    """Create a signed access token with a UTC expiration timestamp."""
    if not isinstance(data, dict) or not isinstance(data.get("sub"), str):
        raise ValueError("Token data must include a string 'sub' claim (user email).")

    payload = data.copy()
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload.update({"exp": expires_at, "type": "access"})

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> str | None:
    """Return the subject email only for a valid, unexpired access token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if payload.get("type", "access") != "access":
            return None
        return email if isinstance(email, str) and email.strip() else None
    except JWTError:
        return None
