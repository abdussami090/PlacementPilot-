from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.education import Education
from app.education_schema import EducationCreate
from app.security import (
    oauth2_scheme,
    verify_token
)

router = APIRouter()


def get_current_student(token: str, db: Session):

    email = verify_token(token)

    if not email:
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )

    user = db.query(User).filter(
        User.email == email
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    if user.role != "student":
        raise HTTPException(
            status_code=403,
            detail="Only students can manage education details"
        )

    return user


# CREATE EDUCATION

@router.post("/education")
def create_education(
    education: EducationCreate,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):

    user = get_current_student(token, db)

    new_education = Education(
        user_id=user.id,
        degree=education.degree,
        college=education.college,
        year=education.year,
        cgpa=education.cgpa,
        graduation_year=education.graduation_year,
        active_backlogs=education.active_backlogs
    )

    db.add(new_education)
    db.commit()
    db.refresh(new_education)

    return {
        "message": "Education added successfully",
        "education_id": new_education.id
    }


# GET EDUCATION

@router.get("/education")
def get_education(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):

    user = get_current_student(token, db)

    education = db.query(Education).filter(
        Education.user_id == user.id
    ).all()

    return education


# UPDATE EDUCATION

@router.put("/education/{education_id}")
def update_education(
    education_id: int,
    education_data: EducationCreate,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):

    user = get_current_student(token, db)

    education = db.query(Education).filter(
        Education.id == education_id,
        Education.user_id == user.id
    ).first()

    if not education:
        raise HTTPException(
            status_code=404,
            detail="Education not found"
        )

    education.degree = education_data.degree
    education.college = education_data.college
    education.year = education_data.year
    education.cgpa = education_data.cgpa
    education.graduation_year = education_data.graduation_year
    education.active_backlogs = education_data.active_backlogs

    db.commit()
    db.refresh(education)

    return {
        "message": "Education updated successfully"
    }


# DELETE EDUCATION

@router.delete("/education/{education_id}")
def delete_education(
    education_id: int,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):

    user = get_current_student(token, db)

    education = db.query(Education).filter(
        Education.id == education_id,
        Education.user_id == user.id
    ).first()

    if not education:
        raise HTTPException(
            status_code=404,
            detail="Education not found"
        )

    db.delete(education)
    db.commit()

    return {
        "message": "Education deleted successfully"
    }