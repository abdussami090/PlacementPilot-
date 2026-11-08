
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import admin_required

from app.job import Job
from app.job_eligibility import JobEligibility

from app.job_eligibility_schema import (
    JobEligibilityCreate,
    JobEligibilityResponse
)


router = APIRouter(
    prefix="/admin/jobs",
    tags=["Job Eligibility"]
)


# =====================================
# CREATE JOB ELIGIBILITY
# =====================================

@router.post(
    "/{job_id}/eligibility",
    response_model=JobEligibilityResponse,
    status_code=201
)
def create_job_eligibility(
    job_id: int,
    data: JobEligibilityCreate,
    admin=Depends(admin_required),
    db: Session = Depends(get_db)
):
    job = db.query(Job).filter(
        Job.id == job_id
    ).first()

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    existing = db.query(JobEligibility).filter(
        JobEligibility.job_id == job_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Eligibility criteria already exist. Use PUT to update."
        )

    eligibility = JobEligibility(
        job_id=job_id,
        **data.model_dump()
    )

    db.add(eligibility)
    db.commit()
    db.refresh(eligibility)

    return eligibility


# =====================================
# GET JOB ELIGIBILITY
# =====================================

@router.get(
    "/{job_id}/eligibility",
    response_model=JobEligibilityResponse
)
def get_job_eligibility(
    job_id: int,
    admin=Depends(admin_required),
    db: Session = Depends(get_db)
):
    eligibility = db.query(JobEligibility).filter(
        JobEligibility.job_id == job_id
    ).first()

    if not eligibility:
        raise HTTPException(
            status_code=404,
            detail="Eligibility criteria not found"
        )

    return eligibility


# =====================================
# UPDATE JOB ELIGIBILITY
# =====================================

@router.put(
    "/{job_id}/eligibility",
    response_model=JobEligibilityResponse
)
def update_job_eligibility(
    job_id: int,
    data: JobEligibilityCreate,
    admin=Depends(admin_required),
    db: Session = Depends(get_db)
):
    eligibility = db.query(JobEligibility).filter(
        JobEligibility.job_id == job_id
    ).first()

    if not eligibility:
        raise HTTPException(
            status_code=404,
            detail="Eligibility criteria not found"
        )

    for key, value in data.model_dump().items():
        setattr(eligibility, key, value)

    db.commit()
    db.refresh(eligibility)

    return eligibility


# =====================================
# DELETE JOB ELIGIBILITY
# =====================================

@router.delete("/{job_id}/eligibility")
def delete_job_eligibility(
    job_id: int,
    admin=Depends(admin_required),
    db: Session = Depends(get_db)
):
    eligibility = db.query(JobEligibility).filter(
        JobEligibility.job_id == job_id
    ).first()

    if not eligibility:
        raise HTTPException(
            status_code=404,
            detail="Eligibility criteria not found"
        )

    db.delete(eligibility)
    db.commit()

    return {
        "message": "Job eligibility criteria deleted successfully"
    }
