from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.dependencies import get_current_student
from app.resume import Resume
from app.resume_schema import ResumeCreate
from app.security import (
    oauth2_scheme,
    verify_token
)

router = APIRouter()


@router.post("/resume")
def create_resume(
    resume: ResumeCreate,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):

    user = get_current_student(token, db)

    new_resume = Resume(
        user_id=user.id,
        resume_name=resume.resume_name,
        resume_link=resume.resume_link
    )

    db.add(new_resume)
    db.commit()

    return {
        "message": "Resume added successfully"
    }

@router.get("/resume")
def get_resumes(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):

    user = get_current_student(token, db)

    resumes = db.query(Resume).filter(
        Resume.user_id == user.id
    ).all()

    return resumes

@router.delete("/resume/{resume_id}")
def delete_resume(
    resume_id: int,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):

    user = get_current_student(token, db)

    resume = db.query(Resume).filter(
        Resume.id == resume_id,
        Resume.user_id == user.id
    ).first()

    if not resume:
        raise HTTPException(
            status_code=404,
            detail="Resume not found"
        )

    db.delete(resume)
    db.commit()

    return {
        "message": "Resume deleted successfully"
    }