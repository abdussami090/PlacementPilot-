"""Environment-backed application configuration for PlacementPilot."""

import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_DIR / ".env"
load_dotenv(dotenv_path=ENV_FILE, override=False)

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
if ENVIRONMENT not in {"development", "test", "production"}:
    raise RuntimeError("ENVIRONMENT must be development, test, or production.")

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "").strip()
if len(SECRET_KEY) < 32:
    raise RuntimeError(
        "JWT_SECRET_KEY is missing or too short. Set a randomly generated "
        "secret (at least 32 characters) in backend/.env or the environment."
    )

ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256").strip().upper()
if ALGORITHM != "HS256":
    raise RuntimeError("JWT_ALGORITHM must be HS256 for this application configuration.")

try:
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
except ValueError as exc:
    raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES must be an integer.") from exc

if not 5 <= ACCESS_TOKEN_EXPIRE_MINUTES <= 120:
    raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES must be between 5 and 120.")

CORS_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

RESUME_STORAGE_BACKEND = os.getenv("RESUME_STORAGE_BACKEND", "local").strip().lower()
if RESUME_STORAGE_BACKEND not in {"local", "s3"}:
    raise RuntimeError("RESUME_STORAGE_BACKEND must be either 'local' or 's3'.")

S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "").strip()
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "").strip()
S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID", "").strip()
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY", "").strip()
S3_REGION = os.getenv("S3_REGION", "auto").strip() or "auto"

if RESUME_STORAGE_BACKEND == "s3":
    missing = [
        key for key, value in {
            "S3_ENDPOINT_URL": S3_ENDPOINT_URL,
            "S3_BUCKET_NAME": S3_BUCKET_NAME,
            "S3_ACCESS_KEY_ID": S3_ACCESS_KEY_ID,
            "S3_SECRET_ACCESS_KEY": S3_SECRET_ACCESS_KEY,
        }.items() if not value
    ]
    if missing:
        raise RuntimeError("Missing object-storage configuration: " + ", ".join(missing))
    if urlsplit(S3_ENDPOINT_URL).scheme != "https":
        raise RuntimeError("S3_ENDPOINT_URL must use HTTPS.")

if ENVIRONMENT == "production":
    if not CORS_ORIGINS:
        raise RuntimeError("Set CORS_ORIGINS to the production frontend origin.")
    if any(urlsplit(origin).scheme != "https" for origin in CORS_ORIGINS):
        raise RuntimeError("Production CORS_ORIGINS must contain HTTPS origins only.")
    if RESUME_STORAGE_BACKEND != "s3":
        raise RuntimeError("Production requires RESUME_STORAGE_BACKEND=s3 for persistent private resumes.")
