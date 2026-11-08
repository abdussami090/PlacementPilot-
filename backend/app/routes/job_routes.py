
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.job import Job
from app.company import Company
from app.placement_cycle import PlacementCycle
from app.placement_drive import CompanyRecruitmentDrive
from app.security import oauth2_scheme
from app.dependencies import get_current_student

from app.eligibility_service import evaluate_eligibility


router = APIRouter()


# =====================================
# GET AVAILABLE JOBS
# =====================================

@router.get("/jobs")
def get_jobs(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):

    user = get_current_student(token, db)

    today = date.today()

    # ---------------------------------
    # FETCH PUBLISHED JOBS
    # ---------------------------------

    jobs = (
        db.query(Job)
        .join(
            CompanyRecruitmentDrive,
            Job.recruitment_drive_id == CompanyRecruitmentDrive.id
        )
        .join(
            Company,
            CompanyRecruitmentDrive.company_id == Company.id
        )
        .join(
            PlacementCycle,
            CompanyRecruitmentDrive.placement_cycle_id == PlacementCycle.id
        )
        .filter(
            Job.status == "Open",
            CompanyRecruitmentDrive.status == "Published",
            Company.is_active.is_(True),
            PlacementCycle.status == "Active"
        )
        .all()
    )

    result = []

    # ---------------------------------
    # PROCESS EACH JOB
    # ---------------------------------

    for job in jobs:

        drive = job.recruitment_drive

        # Check application dates
        if (
            drive.application_start_date
            and today < drive.application_start_date
        ):
            application_state = "Upcoming"

        elif (
            drive.application_deadline
            and today > drive.application_deadline
        ):
            application_state = "Deadline Passed"

        else:
            application_state = "Open"

        # ---------------------------------
        # CHECK STUDENT ELIGIBILITY
        # ---------------------------------

        eligibility = evaluate_eligibility(
            db=db,
            user_id=user.id,
            job_id=job.id
        )

        is_eligible = eligibility["eligible"]

        eligibility_status = (
            "Eligible"
            if is_eligible
            else "Not Eligible"
        )

        # Student can apply only when:
        # 1. Application window is open.
        # 2. Student meets eligibility criteria.

        can_apply = (
            application_state == "Open"
            and is_eligible
        )

        # ---------------------------------
        # ADD JOB TO RESPONSE
        # ---------------------------------

        result.append({

            "job_id": job.id,

            "company": drive.company.name,

            "recruitment_drive_id": drive.id,

            "recruitment_drive": drive.name,

            "placement_cycle": drive.placement_cycle.name,

            "role": job.role,

            "package": job.package,

            "location": job.location,

            "job_status": job.status,

            "application_start_date": drive.application_start_date,

            "application_deadline": drive.application_deadline,

            "application_state": application_state,

            # Eligibility information
            "eligible": is_eligible,

            "eligibility_status": eligibility_status,

            "eligibility_criteria_configured": (
                eligibility["criteria_configured"]
            ),

            "eligibility_reasons": eligibility["reasons"],

            "can_apply": can_apply
        })

    return result
