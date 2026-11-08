from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import oauth2_scheme, verify_token

from app.student_academic import StudentAcademicDetails
from app.student_academic_schema import (
    StudentAcademicDetailsCreate,
    StudentAcademicDetailsResponse
)


router = APIRouter(
    prefix="/student/academic-details",
    tags=["Student Academic Details"]
)


# =====================================
# GET CURRENT STUDENT
# =====================================

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
            detail="Only students can access academic details"
        )

    return user


# =====================================
# CREATE ACADEMIC DETAILS
# =====================================

@router.post(
    "",
    response_model=StudentAcademicDetailsResponse,
    status_code=201
)
def create_academic_details(
    data: StudentAcademicDetailsCreate,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):

    user = get_current_student(token, db)

    existing = db.query(StudentAcademicDetails).filter(
        StudentAcademicDetails.user_id == user.id
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Academic details already exist. Use PUT to update them."
        )

    academic = StudentAcademicDetails(
        user_id=user.id,
        course=data.course,
        graduation_year=data.graduation_year,
        cgpa=data.cgpa,
        active_backlogs=data.active_backlogs
    )

    db.add(academic)
    db.commit()
    db.refresh(academic)

    return academic


# =====================================
# VIEW ACADEMIC DETAILS
# =====================================

@router.get(
    "",
    response_model=StudentAcademicDetailsResponse
)
def get_academic_details(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):

    user = get_current_student(token, db)

    academic = db.query(StudentAcademicDetails).filter(
        StudentAcademicDetails.user_id == user.id
    ).first()

    if not academic:
        raise HTTPException(
            status_code=404,
            detail="Academic details not found"
        )

    return academic


# =====================================
# UPDATE ACADEMIC DETAILS
# =====================================

@router.put(
    "",
    response_model=StudentAcademicDetailsResponse
)
def update_academic_details(
    data: StudentAcademicDetailsCreate,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):

    user = get_current_student(token, db)

    academic = db.query(StudentAcademicDetails).filter(
        StudentAcademicDetails.user_id == user.id
    ).first()

    if not academic:
        raise HTTPException(
            status_code=404,
            detail="Academic details not found. Create them first."
        )

    academic.course = data.course
    academic.graduation_year = data.graduation_year
    academic.cgpa = data.cgpa
    academic.active_backlogs = data.active_backlogs

    db.commit()
    db.refresh(academic)

    return academic