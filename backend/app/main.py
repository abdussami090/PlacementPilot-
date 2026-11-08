
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine, DATABASE_URL
from .config import CORS_ORIGINS, ENVIRONMENT
from . import models

# Import Profile model so SQLAlchemy creates the table
from app.job_eligibility import JobEligibility
from app.profile import Profile
from app.job import Job
from app.resume import Resume
from app.skill import Skill
from app.education import Education
from app.application import Application
from app.dependencies import admin_required
from app.company import Company
from app.placement_cycle import PlacementCycle
from app.placement_drive import CompanyRecruitmentDrive
from app.placement_policy import PlacementPolicy
from app.placement_round import PlacementRound
from app.saved_job import SavedJob
from app.candidate_round import CandidateRound
from app.resume_file import UploadedResume
from app.routes.resume_file_routes import router as resume_file_router

# Import routers
from app.routes.auth_routes import router as auth_router
from app.routes.profile_routes import router as profile_router
from app.routes.job_routes import router as job_router
from app.routes.resume_routes import router as resume_router
from app.routes.skill_routes import router as skill_router
from app.routes.education_routes import router as education_router
from app.routes.application_routes import router as application_router
from app.routes.admin_routes import router as admin_router
from app.routes.eligibility_routes import (
    router as eligibility_router
)
from app.routes.placement_round_routes import router as placement_round_router
from app.routes.student_portal_routes import router as student_portal_router


# Create database tables only for SQLite
if DATABASE_URL.startswith("sqlite") and ENVIRONMENT != "test":
    Base.metadata.create_all(bind=engine)


# Create FastAPI application
app = FastAPI(
    title="PlacementPilot API",
    version="1.0.0"
)


# CORS security configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS"
    ],
    allow_headers=[
        "Authorization",
        "Content-Type"
    ],
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if ENVIRONMENT == "production":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.get("/")
def home():
    return {
        "message": "Welcome to PlacementPilot API"
    }


@app.get("/health")
def health():
    """Readiness check: confirms the API process and database are reachable."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Service temporarily unavailable") from exc
    return {"status": "healthy", "message": "Backend and database are running"}


@app.get("/admin-test")
def admin_test(
    user=Depends(admin_required)
):
    return {
        "message": "Welcome Admin"
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

# Job Routes
app.include_router(
    job_router,
    tags=["Jobs"]
)

# Resume Routes
app.include_router(
    resume_router,
    tags=["Resumes"]
)

app.include_router(
    skill_router,
    tags=["Skills"]
)

app.include_router(
    education_router,
    tags=["Education"]
)

app.include_router(
    application_router,
    tags=["Applications"]
)

app.include_router(resume_file_router)
app.include_router(eligibility_router)
app.include_router(admin_router)
app.include_router(placement_round_router)
app.include_router(student_portal_router)
