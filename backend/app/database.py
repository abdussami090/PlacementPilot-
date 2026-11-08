"""Database connection setup for PlacementPilot."""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import BACKEND_DIR, ENVIRONMENT

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    if ENVIRONMENT == "production":
        raise RuntimeError("DATABASE_URL is required in production; refusing to fall back to SQLite.")
    DATABASE_URL = f"sqlite:///{(BACKEND_DIR / 'placementpilot.db').as_posix()}"

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

if ENVIRONMENT == "production" and not DATABASE_URL.startswith("postgresql+psycopg://"):
    raise RuntimeError("Production DATABASE_URL must use PostgreSQL with the psycopg driver.")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Provide one SQLAlchemy session per request and always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
