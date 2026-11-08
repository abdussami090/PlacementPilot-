from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.job import Job
from app.application import Application

from app.database import get_db
from app.models import User
from app.dependencies import get_current_student
from app.profile import Profile
from app.profile_schema import (
    ProfileCreate,
    ProfileResponse)
from app.security import (
    oauth2_scheme,
    verify_token
)

router = APIRouter()



@router.post("/profile")
def create_profile(
    profile: ProfileCreate,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):

    user = get_current_student(token, db)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    existing_profile = db.query(Profile).filter(
        Profile.user_id == user.id
    ).first()

    if existing_profile:
        raise HTTPException(
            status_code=400,
            detail="Profile already exists"
        )

    new_profile = Profile(
        user_id=user.id,
        college=profile.college,
        branch=profile.branch,
        year=profile.year,
        linkedin=profile.linkedin,
        github=profile.github,
        skills=profile.skills
    )

    db.add(new_profile)
    db.commit()

    return {
        "message": "Profile created successfully"
    }

@router.get("/profile")
def get_profile(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    user = get_current_student(token, db)

    profile = db.query(Profile).filter(
        Profile.user_id == user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Profile not found"
        )

    return profile

@router.put("/profile")
def update_profile(
    profile_data: ProfileCreate,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    user = get_current_student(token, db)

    profile = db.query(Profile).filter(
        Profile.user_id == user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Profile not found"
        )

    profile.college = profile_data.college
    profile.branch = profile_data.branch
    profile.year = profile_data.year
    profile.linkedin = profile_data.linkedin
    profile.github = profile_data.github
    profile.skills = profile_data.skills

    db.commit()

    return {
        "message": "Profile updated successfully"
    }

@router.get("/dashboard")
def dashboard(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):

    user = get_current_student(token, db)

    profile = db.query(Profile).filter(
        Profile.user_id == user.id
    ).first()

    jobs_count = db.query(Job).filter(
        Job.user_id == user.id
    ).count()

    applications = db.query(Application).filter(
        Application.user_id == user.id
    ).all()

    total_applications = len(applications)

    applied = 0
    under_review = 0
    selected = 0
    rejected = 0
    withdrawn = 0

    for application in applications:

        if application.status == "Applied":
            applied += 1

        elif application.status == "Under Review":
            under_review += 1

        elif application.status == "Selected":
            selected += 1

        elif application.status == "Rejected":
            rejected += 1

        elif application.status == "Withdrawn":
            withdrawn += 1

    return {
        "user_name": user.name,
        "email": user.email,

        "profile": {
            "college": profile.college if profile else None,
            "branch": profile.branch if profile else None,
            "year": profile.year if profile else None
        },

        "total_jobs_created": jobs_count,

        "total_applications": total_applications,

        "applied": applied,
        "under_review": under_review,
        "selected": selected,
        "rejected": rejected,
        "withdrawn": withdrawn
    }