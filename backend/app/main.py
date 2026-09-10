from fastapi import FastAPI

from .database import Base, engine
from . import models

# Import Profile model so SQLAlchemy creates the table
from app.profile import Profile

# Import routers
from app.routes.auth_routes import router as auth_router
from app.routes.profile_routes import router as profile_router

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="PlacementPilot API",
    version="1.0.0"
)


@app.get("/")
def home():
    return {
        "message": "Welcome to PlacementPilot API"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "message": "Backend is running"
    }


# Authentication Routes
app.include_router(
    auth_router,
    prefix="/auth",
    tags=["Authentication"]
)

# Profile Routes
app.include_router(
    profile_router,
    tags=["Profile"]
)