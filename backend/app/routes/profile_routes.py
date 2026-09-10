from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import User
from app.profile import Profile
from app.profile_schema import (
    ProfileCreate,
    ProfileResponse)
from app.security import (
    oauth2_scheme,
    verify_token
)

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/profile")
def create_profile(
    profile: ProfileCreate,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):

    email = verify_token(token)

    user = db.query(User).filter(
        User.email == email
    ).first()

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
    email = verify_token(token)

    user = db.query(User).filter(
        User.email == email
    ).first()

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
    email = verify_token(token)

    user = db.query(User).filter(
        User.email == email
    ).first()

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
    email = verify_token(token)

    user = db.query(User).filter(
        User.email == email
    ).first()

    profile = db.query(Profile).filter(
        Profile.user_id == user.id
    ).first()

    return {
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email
        },
        "profile": {
            "college": profile.college,
            "branch": profile.branch,
            "year": profile.year,
            "linkedin": profile.linkedin,
            "github": profile.github,
            "skills": profile.skills
        }
    }