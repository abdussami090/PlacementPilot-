from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.job import Job
from app.application import Application
from app.application_schema import ApplicationCreate
from app.placement_drive import CompanyRecruitmentDrive
from app.eligibility_service import evaluate_eligibility
from app.security import oauth2_scheme, verify_token

router = APIRouter()


# These statuses consume an active application slot in a placement cycle.
# Offer Released is deliberately excluded when the cycle allows students
# to continue applying after receiving an offer.
ACTIVE_APPLICATION_STATUSES = [
    "Applied",
    "Under Review",
    "Shortlisted",
    "In Progress",
    "Selected",
]

# If multiple positions in one recruitment drive are not allowed, only a
# current/in-progress application or a released offer blocks another role.
# Rejected, Withdrawn, and Offer Declined are terminal and do not block it.
SAME_DRIVE_BLOCKING_STATUSES = ACTIVE_APPLICATION_STATUSES + ["Offer Released"]


class OfferResponse(BaseModel):
    decision: Literal["accept", "decline"]


def get_current_student(token: str, db: Session):
    """Return the authenticated student associated with the bearer token."""
    email = verify_token(token)

    if not email:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User associated with token was not found",
        )

    if user.role != "student":
        raise HTTPException(
            status_code=403,
            detail="Only students can perform this action",
        )

    return user


def get_student_cycle_applications_query(db: Session, user_id: int, cycle_id: int):
    """Build a query for one student's applications in one placement cycle."""
    return (
        db.query(Application)
        .join(Job, Application.job_id == Job.id)
        .join(
            CompanyRecruitmentDrive,
            Job.recruitment_drive_id == CompanyRecruitmentDrive.id,
        )
        .filter(
            Application.user_id == user_id,
            CompanyRecruitmentDrive.placement_cycle_id == cycle_id,
        )
    )


def lock_student_for_application_updates(db: Session, user_id: int) -> User:
    """Serialize application creation and offer responses for one student."""
    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    if not user:
        raise HTTPException(status_code=401, detail="User associated with token was not found")
    return user


# =====================================
# APPLY FOR JOB
# =====================================

@router.post("/apply")
def apply_job(
    application: ApplicationCreate,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    # Serialize submissions per student so concurrent requests cannot bypass limits.
    user = lock_student_for_application_updates(db, get_current_student(token, db).id)

    job = db.query(Job).filter(Job.id == application.job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    drive = job.recruitment_drive

    if not drive:
        raise HTTPException(
            status_code=409,
            detail="Job is not linked to a recruitment drive",
        )

    cycle = drive.placement_cycle

    if not cycle:
        raise HTTPException(
            status_code=409,
            detail="Recruitment drive has no placement cycle",
        )

    company = drive.company
    if not company or not company.is_active:
        raise HTTPException(status_code=400, detail="Company is inactive")

    if job.status != "Open":
        raise HTTPException(status_code=400, detail="Job is not open")

    if drive.status != "Published":
        raise HTTPException(
            status_code=400,
            detail="Recruitment drive is not published",
        )

    if cycle.status != "Active":
        raise HTTPException(
            status_code=400,
            detail="Placement cycle is not active",
        )

    today = date.today()

    if drive.application_start_date and today < drive.application_start_date:
        raise HTTPException(
            status_code=400,
            detail="Applications have not started yet",
        )

    if drive.application_deadline and today > drive.application_deadline:
        raise HTTPException(
            status_code=400,
            detail="Application deadline has passed",
        )

    # ---------------------------------
    # CHECK STUDENT JOB ELIGIBILITY
    # ---------------------------------
    eligibility = evaluate_eligibility(
        db=db,
        user_id=user.id,
        job_id=job.id,
    )

    if not eligibility["eligible"]:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "You do not meet the eligibility criteria for this job.",
                "reasons": eligibility["reasons"],
            },
        )

    # Read the policy for this placement cycle. The fallbacks preserve the
    # agreed defaults if a cycle does not yet have a policy row.
    policy = cycle.policy

    max_active = policy.max_active_applications if policy else 1
    allow_reapply_after_rejection = (
        policy.allow_reapply_after_rejection if policy else True
    )
    allow_reapply_after_withdrawal = (
        policy.allow_reapply_after_withdrawal if policy else True
    )
    allow_multiple_positions = (
        policy.allow_multiple_positions_same_drive if policy else False
    )
    allow_applications_after_offer_release = (
        policy.allow_applications_after_offer_release if policy else True
    )
    lock_after_offer_acceptance = (
        policy.lock_after_offer_acceptance if policy else True
    )
    allow_reapply_after_offer_declined = (
        policy.allow_reapply_after_offer_declined if policy else True
    )

    cycle_applications = get_student_cycle_applications_query(
        db=db,
        user_id=user.id,
        cycle_id=cycle.id,
    )

    # ---------------------------------
    # CHECK ACCEPTED OFFER LOCK
    # ---------------------------------
    if lock_after_offer_acceptance:
        accepted_offer = cycle_applications.filter(
            Application.status.in_(["Offer Accepted", "Joined"])
        ).first()

        if accepted_offer:
            raise HTTPException(
                status_code=400,
                detail=(
                    "You have already accepted an offer in this placement cycle. "
                    "Further applications are locked."
                ),
            )

    # ---------------------------------
    # CHECK APPLICATIONS AFTER OFFER RELEASE
    # ---------------------------------
    if not allow_applications_after_offer_release:
        released_offer = cycle_applications.filter(
            Application.status == "Offer Released"
        ).first()

        if released_offer:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Applications to other jobs are not allowed after an offer "
                    "has been released in this placement cycle."
                ),
            )

    # ---------------------------------
    # CHECK REAPPLICATION AFTER OFFER DECLINED
    # ---------------------------------
    if not allow_reapply_after_offer_declined:
        declined_offer = cycle_applications.filter(
            Application.status == "Offer Declined"
        ).first()

        if declined_offer:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Reapplying after declining an offer is not allowed "
                    "in this placement cycle."
                ),
            )

    # ---------------------------------
    # CHECK DUPLICATE APPLICATION / REAPPLICATION
    # ---------------------------------
    existing_application = (
        db.query(Application)
        .filter(
            Application.user_id == user.id,
            Application.job_id == job.id,
        )
        .order_by(Application.id.desc())
        .first()
    )

    if existing_application:
        previous_status = existing_application.status

        can_reapply = (
            (previous_status == "Rejected" and allow_reapply_after_rejection)
            or (previous_status == "Withdrawn" and allow_reapply_after_withdrawal)
            or (
                previous_status == "Offer Declined"
                and allow_reapply_after_offer_declined
            )
        )

        if not can_reapply:
            raise HTTPException(
                status_code=400,
                detail="You have already applied to this job, or reapplication is not allowed.",
            )

    # ---------------------------------
    # CHECK MULTIPLE POSITIONS IN SAME DRIVE
    # ---------------------------------
    if not allow_multiple_positions:
        another_position_application = (
            db.query(Application)
            .join(Job, Application.job_id == Job.id)
            .filter(
                Application.user_id == user.id,
                Job.recruitment_drive_id == drive.id,
                Job.id != job.id,
                Application.status.in_(SAME_DRIVE_BLOCKING_STATUSES),
            )
            .first()
        )

        if another_position_application:
            raise HTTPException(
                status_code=400,
                detail=(
                    "You already have an active application or a released offer "
                    "for another position in this company recruitment drive."
                ),
            )

    # ---------------------------------
    # CHECK ACTIVE APPLICATION LIMIT
    # ---------------------------------
    active_application_count = cycle_applications.filter(
        Application.status.in_(ACTIVE_APPLICATION_STATUSES)
    ).count()

    if active_application_count >= max_active:
        raise HTTPException(
            status_code=400,
            detail=(
                f"You can have only {max_active} active application(s) "
                "in this placement cycle."
            ),
        )

    new_application = Application(
        user_id=user.id,
        job_id=job.id,
        status="Applied",
    )

    db.add(new_application)
    db.commit()
    db.refresh(new_application)

    return {
        "message": "Job applied successfully",
        "application_id": new_application.id,
        "job_id": job.id,
        "company": company.name,
        "role": job.role,
        "status": new_application.status,
    }


# =====================================
# VIEW MY APPLICATIONS
# =====================================

@router.get("/applications")
def get_my_applications(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    user = get_current_student(token, db)

    applications = (
        db.query(Application)
        .filter(Application.user_id == user.id)
        .order_by(Application.id.desc())
        .all()
    )

    result = []

    for application in applications:
        job = application.job
        drive = job.recruitment_drive if job else None

        result.append(
            {
                "application_id": application.id,
                "job_id": application.job_id,
                "company": (
                    drive.company.name
                    if drive and drive.company
                    else None
                ),
                "recruitment_drive": drive.name if drive else None,
                "placement_cycle": (
                    drive.placement_cycle.name
                    if drive and drive.placement_cycle
                    else None
                ),
                "role": job.role if job else None,
                "package": job.package if job else None,
                "location": job.location if job else None,
                "status": application.status,
            }
        )

    return result


# =====================================
# RESPOND TO A RELEASED OFFER
# =====================================

@router.post("/application/{application_id}/offer-response")
def respond_to_offer(
    application_id: int,
    response_data: OfferResponse,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    user = get_current_student(token, db)
    user = lock_student_for_application_updates(db, user.id)

    application = db.query(Application).filter(
        Application.id == application_id,
        Application.user_id == user.id,
    ).with_for_update().first()

    if not application:
        raise HTTPException(
            status_code=404,
            detail="Application not found",
        )

    if application.status != "Offer Released":
        raise HTTPException(
            status_code=409,
            detail="You can respond only to an application with an Offer Released status.",
        )

    if response_data.decision == "accept":
        application.status = "Offer Accepted"
    else:
        application.status = "Offer Declined"

    db.commit()
    db.refresh(application)

    return {
        "message": (
            "Offer accepted successfully"
            if response_data.decision == "accept"
            else "Offer declined successfully"
        ),
        "application_id": application.id,
        "status": application.status,
    }


# =====================================
# WITHDRAW APPLICATION
# =====================================

@router.delete("/application/{application_id}")
def withdraw_application(
    application_id: int,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    user = get_current_student(token, db)

    application = db.query(Application).filter(
        Application.id == application_id,
        Application.user_id == user.id,
    ).first()

    if not application:
        raise HTTPException(
            status_code=404,
            detail="Application not found",
        )

    non_withdrawable_statuses = [
        "Rejected",
        "Withdrawn",
        "Offer Released",
        "Offer Accepted",
        "Offer Declined",
        "Joined",
    ]

    if application.status in non_withdrawable_statuses:
        raise HTTPException(
            status_code=400,
            detail="This application cannot be withdrawn",
        )

    job = application.job
    drive = job.recruitment_drive if job else None
    cycle = drive.placement_cycle if drive else None
    policy = cycle.policy if cycle else None

    shortlisted_statuses = ["Shortlisted", "In Progress", "Selected"]

    if (
        application.status in shortlisted_statuses
        and not (policy and policy.allow_withdraw_after_shortlisting)
    ):
        raise HTTPException(
            status_code=400,
            detail="Withdrawal after shortlisting is not allowed",
        )

    application.status = "Withdrawn"
    db.commit()
    db.refresh(application)

    return {
        "message": "Application withdrawn successfully",
        "application_id": application.id,
        "status": application.status,
    }
