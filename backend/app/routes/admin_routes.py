from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import admin_required
from app.application_schema import ApplicationStatusUpdate

from app.models import User
from app.job import Job
from app.job_schema import JobCreate, JobUpdate
from app.application import Application
from app.company import Company
from app.company_schema import CompanyCreate, CompanyUpdate

from app.placement_cycle import PlacementCycle
from app.placement_cycle_schema import (
    PlacementCycleCreate,
    PlacementCycleUpdate
)

from app.placement_policy import PlacementPolicy
from app.placement_policy_schema import (
    PlacementPolicyCreate,
    PlacementPolicyUpdate
)

from app.placement_drive import CompanyRecruitmentDrive

from app.placement_drive_schema import (
    CompanyRecruitmentDriveCreate,
    CompanyRecruitmentDriveUpdate
)


router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)

APPLICATION_STATUS_ORDER = {
    "Applied": 0,
    "Under Review": 1,
    "Shortlisted": 2,
    "In Progress": 3,
    "Selected": 4,
}



# =========================
# USER MANAGEMENT
# =========================

@router.get("/users")
def get_all_users(
    user=Depends(admin_required),
    db: Session = Depends(get_db)
):
    users = db.query(User).all()

    return [
        {
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "role": u.role
        }
        for u in users
    ]


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    user=Depends(admin_required),
    db: Session = Depends(get_db)
):
    target_user = db.query(User).filter(
        User.id == user_id
    ).first()

    if not target_user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    if target_user.id == user.id:
        raise HTTPException(
            status_code=400,
            detail="Admin cannot delete their own account"
        )

    if target_user.role == "admin":
        raise HTTPException(
            status_code=403,
            detail="An administrator cannot delete another administrator account"
        )

    db.delete(target_user)
    db.commit()

    return {
        "message": "User deleted successfully"
    }

# =========================
# COMPANY MANAGEMENT
# =========================

@router.post("/companies")
def create_company(
    company_data: CompanyCreate,
    user=Depends(admin_required),
    db: Session = Depends(get_db)
):
    existing_company = db.query(Company).filter(
        Company.name == company_data.name
    ).first()

    if existing_company:
        raise HTTPException(
            status_code=400,
            detail="Company already exists"
        )

    new_company = Company(
        name=company_data.name,
        description=company_data.description,
        website=company_data.website,
        contact_person=company_data.contact_person,
        contact_email=company_data.contact_email,
        created_by=user.id
    )

    db.add(new_company)
    db.commit()
    db.refresh(new_company)

    return {
        "message": "Company created successfully",
        "company": {
            "id": new_company.id,
            "name": new_company.name,
            "description": new_company.description,
            "website": new_company.website,
            "contact_person": new_company.contact_person,
            "contact_email": new_company.contact_email,
            "is_active": new_company.is_active
        }
    }


@router.get("/companies")
def get_all_companies(
    user=Depends(admin_required),
    db: Session = Depends(get_db)
):
    companies = db.query(Company).all()

    return [
        {
            "id": company.id,
            "name": company.name,
            "description": company.description,
            "website": company.website,
            "contact_person": company.contact_person,
            "contact_email": company.contact_email,
            "is_active": company.is_active
        }
        for company in companies
    ]


@router.put("/companies/{company_id}")
def update_company(
    company_id: int,
    company_data: CompanyUpdate,
    user=Depends(admin_required),
    db: Session = Depends(get_db)
):
    company = db.query(Company).filter(
        Company.id == company_id
    ).first()

    if not company:
        raise HTTPException(
            status_code=404,
            detail="Company not found"
        )

    existing_company = db.query(Company).filter(
        Company.name == company_data.name,
        Company.id != company_id
    ).first()

    if existing_company:
        raise HTTPException(
            status_code=400,
            detail="Company name already exists"
        )

    company.name = company_data.name
    company.description = company_data.description
    company.website = company_data.website
    company.contact_person = company_data.contact_person
    company.contact_email = company_data.contact_email

    db.commit()
    db.refresh(company)

    return {
        "message": "Company updated successfully",
        "company": {
            "id": company.id,
            "name": company.name,
            "description": company.description,
            "website": company.website,
            "contact_person": company.contact_person,
            "contact_email": company.contact_email,
            "is_active": company.is_active
        }
    }


@router.delete("/companies/{company_id}")
def delete_company(
    company_id: int,
    user=Depends(admin_required),
    db: Session = Depends(get_db)
):
    company = db.query(Company).filter(
        Company.id == company_id
    ).first()

    if not company:
        raise HTTPException(
            status_code=404,
            detail="Company not found"
        )

    db.delete(company)
    db.commit()

    return {
        "message": "Company deleted successfully"
    }

# =========================
# PLACEMENT CYCLE MANAGEMENT
# =========================

@router.post("/cycles")
def create_placement_cycle(
    cycle_data: PlacementCycleCreate,
    user=Depends(admin_required),
    db: Session = Depends(get_db)
):
    new_cycle = PlacementCycle(
        name=cycle_data.name,
        academic_year=cycle_data.academic_year,
        description=cycle_data.description,
        start_date=cycle_data.start_date,
        end_date=cycle_data.end_date,
        status=cycle_data.status,
        created_by=user.id
    )

    db.add(new_cycle)
    db.commit()
    db.refresh(new_cycle)

    return {
        "message": "Placement cycle created successfully",
        "cycle": {
            "id": new_cycle.id,
            "name": new_cycle.name,
            "academic_year": new_cycle.academic_year,
            "description": new_cycle.description,
            "start_date": new_cycle.start_date,
            "end_date": new_cycle.end_date,
            "status": new_cycle.status
        }
    }


@router.get("/cycles")
def get_all_placement_cycles(
    user=Depends(admin_required),
    db: Session = Depends(get_db)
):
    cycles = db.query(PlacementCycle).all()

    return [
        {
            "id": cycle.id,
            "name": cycle.name,
            "academic_year": cycle.academic_year,
            "description": cycle.description,
            "start_date": cycle.start_date,
            "end_date": cycle.end_date,
            "status": cycle.status
        }
        for cycle in cycles
    ]


@router.get("/cycles/{cycle_id}")
def get_placement_cycle(
    cycle_id: int,
    user=Depends(admin_required),
    db: Session = Depends(get_db)
):
    cycle = db.query(PlacementCycle).filter(
        PlacementCycle.id == cycle_id
    ).first()

    if not cycle:
        raise HTTPException(
            status_code=404,
            detail="Placement cycle not found"
        )

    return {
        "id": cycle.id,
        "name": cycle.name,
        "academic_year": cycle.academic_year,
        "description": cycle.description,
        "start_date": cycle.start_date,
        "end_date": cycle.end_date,
        "status": cycle.status
    }


@router.put("/cycles/{cycle_id}")
def update_placement_cycle(
    cycle_id: int,
    cycle_data: PlacementCycleUpdate,
    user=Depends(admin_required),
    db: Session = Depends(get_db)
):
    cycle = db.query(PlacementCycle).filter(
        PlacementCycle.id == cycle_id
    ).first()

    if not cycle:
        raise HTTPException(
            status_code=404,
            detail="Placement cycle not found"
        )

    cycle.name = cycle_data.name
    cycle.academic_year = cycle_data.academic_year
    cycle.description = cycle_data.description
    cycle.start_date = cycle_data.start_date
    cycle.end_date = cycle_data.end_date
    cycle.status = cycle_data.status

    db.commit()
    db.refresh(cycle)

    return {
        "message": "Placement cycle updated successfully",
        "cycle": {
            "id": cycle.id,
            "name": cycle.name,
            "academic_year": cycle.academic_year,
            "description": cycle.description,
            "start_date": cycle.start_date,
            "end_date": cycle.end_date,
            "status": cycle.status
        }
    }


@router.delete("/cycles/{cycle_id}")
def delete_placement_cycle(
    cycle_id: int,
    user=Depends(admin_required),
    db: Session = Depends(get_db)
):
    cycle = db.query(PlacementCycle).filter(
        PlacementCycle.id == cycle_id
    ).first()

    if not cycle:
        raise HTTPException(
            status_code=404,
            detail="Placement cycle not found"
        )

    db.delete(cycle)
    db.commit()

    return {
        "message": "Placement cycle deleted successfully"
    }


# =====================================
# PLACEMENT POLICY MANAGEMENT
# =====================================

@router.post("/cycles/{cycle_id}/policy")
def create_placement_policy(
    cycle_id: int,
    policy_data: PlacementPolicyCreate,
    user=Depends(admin_required),
    db: Session = Depends(get_db)
):

    cycle = db.query(PlacementCycle).filter(
        PlacementCycle.id == cycle_id
    ).first()

    if not cycle:
        raise HTTPException(
            status_code=404,
            detail="Placement cycle not found"
        )

    existing_policy = db.query(PlacementPolicy).filter(
        PlacementPolicy.placement_cycle_id == cycle_id
    ).first()

    if existing_policy:
        raise HTTPException(
            status_code=409,
            detail="Placement policy already exists for this cycle. Use PUT to update it."
        )

    policy = PlacementPolicy(
        placement_cycle_id=cycle_id,
        max_active_applications=policy_data.max_active_applications,
        allow_reapply_after_rejection=policy_data.allow_reapply_after_rejection,
        allow_reapply_after_withdrawal=policy_data.allow_reapply_after_withdrawal,
        allow_multiple_positions_same_drive=policy_data.allow_multiple_positions_same_drive,
        allow_withdraw_after_shortlisting=policy_data.allow_withdraw_after_shortlisting,
        allow_applications_after_offer_release=policy_data.allow_applications_after_offer_release,
        lock_after_offer_acceptance=policy_data.lock_after_offer_acceptance,
        allow_reapply_after_offer_declined=policy_data.allow_reapply_after_offer_declined
    )

    db.add(policy)
    db.commit()
    db.refresh(policy)

    return {
        "message": "Placement policy created successfully",
        "policy": {
            "id": policy.id,
            "placement_cycle_id": policy.placement_cycle_id,
            "max_active_applications": policy.max_active_applications,
            "allow_reapply_after_rejection": policy.allow_reapply_after_rejection,
            "allow_reapply_after_withdrawal": policy.allow_reapply_after_withdrawal,
            "allow_multiple_positions_same_drive": policy.allow_multiple_positions_same_drive,
            "allow_withdraw_after_shortlisting": policy.allow_withdraw_after_shortlisting,
            "allow_applications_after_offer_release": policy.allow_applications_after_offer_release,
            "lock_after_offer_acceptance": policy.lock_after_offer_acceptance,
            "allow_reapply_after_offer_declined": policy.allow_reapply_after_offer_declined
        }
    }


# =====================================
# GET PLACEMENT POLICY
# =====================================

@router.get("/cycles/{cycle_id}/policy")
def get_placement_policy(
    cycle_id: int,
    user=Depends(admin_required),
    db: Session = Depends(get_db)
):

    policy = db.query(PlacementPolicy).filter(
        PlacementPolicy.placement_cycle_id == cycle_id
    ).first()

    if not policy:
        raise HTTPException(
            status_code=404,
            detail="Placement policy not found"
        )

    return {
        "id": policy.id,
        "placement_cycle_id": policy.placement_cycle_id,
        "max_active_applications": policy.max_active_applications,
        "allow_reapply_after_rejection": policy.allow_reapply_after_rejection,
        "allow_reapply_after_withdrawal": policy.allow_reapply_after_withdrawal,
        "allow_multiple_positions_same_drive": policy.allow_multiple_positions_same_drive,
        "allow_withdraw_after_shortlisting": policy.allow_withdraw_after_shortlisting,
        "allow_applications_after_offer_release": policy.allow_applications_after_offer_release,
        "lock_after_offer_acceptance": policy.lock_after_offer_acceptance,
        "allow_reapply_after_offer_declined": policy.allow_reapply_after_offer_declined
    }


# =====================================
# UPDATE PLACEMENT POLICY
# =====================================

@router.put("/cycles/{cycle_id}/policy")
def update_placement_policy(
    cycle_id: int,
    policy_data: PlacementPolicyUpdate,
    user=Depends(admin_required),
    db: Session = Depends(get_db)
):

    policy = db.query(PlacementPolicy).filter(
        PlacementPolicy.placement_cycle_id == cycle_id
    ).first()

    if not policy:
        raise HTTPException(
            status_code=404,
            detail="Placement policy not found"
        )

    policy.max_active_applications = policy_data.max_active_applications
    policy.allow_reapply_after_rejection = policy_data.allow_reapply_after_rejection
    policy.allow_reapply_after_withdrawal = policy_data.allow_reapply_after_withdrawal
    policy.allow_multiple_positions_same_drive = policy_data.allow_multiple_positions_same_drive
    policy.allow_withdraw_after_shortlisting = policy_data.allow_withdraw_after_shortlisting
    policy.allow_applications_after_offer_release = policy_data.allow_applications_after_offer_release
    policy.lock_after_offer_acceptance = policy_data.lock_after_offer_acceptance
    policy.allow_reapply_after_offer_declined = policy_data.allow_reapply_after_offer_declined

    db.commit()
    db.refresh(policy)

    return {
        "message": "Placement policy updated successfully",
        "policy": {
            "id": policy.id,
            "placement_cycle_id": policy.placement_cycle_id,
            "max_active_applications": policy.max_active_applications,
            "allow_reapply_after_rejection": policy.allow_reapply_after_rejection,
            "allow_reapply_after_withdrawal": policy.allow_reapply_after_withdrawal,
            "allow_multiple_positions_same_drive": policy.allow_multiple_positions_same_drive,
            "allow_withdraw_after_shortlisting": policy.allow_withdraw_after_shortlisting,
            "allow_applications_after_offer_release": policy.allow_applications_after_offer_release,
            "lock_after_offer_acceptance": policy.lock_after_offer_acceptance,
            "allow_reapply_after_offer_declined": policy.allow_reapply_after_offer_declined
        }
    }


# =====================================
# COMPANY RECRUITMENT DRIVE MANAGEMENT
# =====================================

@router.post("/recruitment-drives")
def create_recruitment_drive(
    drive_data: CompanyRecruitmentDriveCreate,
    user=Depends(admin_required),
    db: Session = Depends(get_db)
):
    company = db.query(Company).filter(
        Company.id == drive_data.company_id
    ).first()

    if not company:
        raise HTTPException(
            status_code=404,
            detail="Company not found"
        )

    cycle = db.query(PlacementCycle).filter(
        PlacementCycle.id == drive_data.placement_cycle_id
    ).first()

    if not cycle:
        raise HTTPException(
            status_code=404,
            detail="Placement cycle not found"
        )

    if (
        drive_data.application_start_date
        and drive_data.application_deadline
        and drive_data.application_deadline
        < drive_data.application_start_date
    ):
        raise HTTPException(
            status_code=400,
            detail="Application deadline cannot be before start date"
        )

    new_drive = CompanyRecruitmentDrive(
        company_id=drive_data.company_id,
        placement_cycle_id=drive_data.placement_cycle_id,
        name=drive_data.name,
        description=drive_data.description,
        application_start_date=drive_data.application_start_date,
        application_deadline=drive_data.application_deadline,
        status=drive_data.status,
        created_by=user.id
    )

    db.add(new_drive)
    db.commit()
    db.refresh(new_drive)

    return {
        "message": "Company recruitment drive created successfully",
        "drive": {
            "id": new_drive.id,
            "company_id": new_drive.company_id,
            "company_name": company.name,
            "placement_cycle_id": new_drive.placement_cycle_id,
            "cycle_name": cycle.name,
            "name": new_drive.name,
            "description": new_drive.description,
            "application_start_date": new_drive.application_start_date,
            "application_deadline": new_drive.application_deadline,
            "status": new_drive.status
        }
    }


@router.get("/recruitment-drives")
def get_all_recruitment_drives(
    user=Depends(admin_required),
    db: Session = Depends(get_db)
):
    drives = db.query(CompanyRecruitmentDrive).all()

    return [
        {
            "id": drive.id,
            "company_id": drive.company_id,
            "company_name": drive.company.name,
            "placement_cycle_id": drive.placement_cycle_id,
            "cycle_name": drive.placement_cycle.name,
            "name": drive.name,
            "description": drive.description,
            "application_start_date": drive.application_start_date,
            "application_deadline": drive.application_deadline,
            "status": drive.status
        }
        for drive in drives
    ]


@router.get("/recruitment-drives/{drive_id}")
def get_recruitment_drive(
    drive_id: int,
    user=Depends(admin_required),
    db: Session = Depends(get_db)
):
    drive = db.query(CompanyRecruitmentDrive).filter(
        CompanyRecruitmentDrive.id == drive_id
    ).first()

    if not drive:
        raise HTTPException(
            status_code=404,
            detail="Recruitment drive not found"
        )

    return {
        "id": drive.id,
        "company_id": drive.company_id,
        "company_name": drive.company.name,
        "placement_cycle_id": drive.placement_cycle_id,
        "cycle_name": drive.placement_cycle.name,
        "name": drive.name,
        "description": drive.description,
        "application_start_date": drive.application_start_date,
        "application_deadline": drive.application_deadline,
        "status": drive.status
    }


@router.put("/recruitment-drives/{drive_id}")
def update_recruitment_drive(
    drive_id: int,
    drive_data: CompanyRecruitmentDriveUpdate,
    user=Depends(admin_required),
    db: Session = Depends(get_db)
):
    drive = db.query(CompanyRecruitmentDrive).filter(
        CompanyRecruitmentDrive.id == drive_id
    ).first()

    if not drive:
        raise HTTPException(
            status_code=404,
            detail="Recruitment drive not found"
        )

    company = db.query(Company).filter(
        Company.id == drive_data.company_id
    ).first()

    if not company:
        raise HTTPException(
            status_code=404,
            detail="Company not found"
        )

    cycle = db.query(PlacementCycle).filter(
        PlacementCycle.id == drive_data.placement_cycle_id
    ).first()

    if not cycle:
        raise HTTPException(
            status_code=404,
            detail="Placement cycle not found"
        )

    if (
        drive_data.application_start_date
        and drive_data.application_deadline
        and drive_data.application_deadline
        < drive_data.application_start_date
    ):
        raise HTTPException(
            status_code=400,
            detail="Application deadline cannot be before start date"
        )

    drive.company_id = drive_data.company_id
    drive.placement_cycle_id = drive_data.placement_cycle_id
    drive.name = drive_data.name
    drive.description = drive_data.description
    drive.application_start_date = drive_data.application_start_date
    drive.application_deadline = drive_data.application_deadline
    drive.status = drive_data.status

    db.commit()
    db.refresh(drive)

    return {
        "message": "Recruitment drive updated successfully",
        "id": drive.id,
        "name": drive.name,
        "status": drive.status
    }


@router.delete("/recruitment-drives/{drive_id}")
def delete_recruitment_drive(
    drive_id: int,
    user=Depends(admin_required),
    db: Session = Depends(get_db)
):
    drive = db.query(CompanyRecruitmentDrive).filter(
        CompanyRecruitmentDrive.id == drive_id
    ).first()

    if not drive:
        raise HTTPException(
            status_code=404,
            detail="Recruitment drive not found"
        )

    if drive.jobs:
        raise HTTPException(
            status_code=409,
            detail="This drive contains jobs. Close or cancel it instead of deleting it."
        )

    db.delete(drive)
    db.commit()

    return {
        "message": "Recruitment drive deleted successfully"
    }

# =========================
# JOB MANAGEMENT
# =========================

@router.post("/jobs")
def create_job(
    job_data: JobCreate,
    user=Depends(admin_required),
    db: Session = Depends(get_db)
):
    drive = db.query(CompanyRecruitmentDrive).filter(
        CompanyRecruitmentDrive.id == job_data.recruitment_drive_id
    ).first()

    if not drive:
        raise HTTPException(
            status_code=404,
            detail="Recruitment drive not found"
        )

    if drive.status in ["Closed", "Cancelled"]:
        raise HTTPException(
            status_code=400,
            detail="Cannot add a job to a closed or cancelled drive"
        )

    new_job = Job(
        user_id=user.id,
        recruitment_drive_id=drive.id,
        role=job_data.role,
        package=job_data.package,
        location=job_data.location,
        status=job_data.status
    )

    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    return {
        "message": "Job created successfully",
        "job": {
            "id": new_job.id,
            "recruitment_drive_id": new_job.recruitment_drive_id,
            "company": drive.company.name,
            "role": new_job.role,
            "package": new_job.package,
            "location": new_job.location,
            "status": new_job.status
        }
    }


@router.get("/jobs")
def get_all_jobs(
    user=Depends(admin_required),
    db: Session = Depends(get_db)
):
    jobs = db.query(Job).all()

    return [
        {
            "id": job.id,
            "recruitment_drive_id": job.recruitment_drive_id,
            "company": (
                job.recruitment_drive.company.name
                if job.recruitment_drive else None
            ),
            "recruitment_drive": (
                job.recruitment_drive.name
                if job.recruitment_drive else None
            ),
            "role": job.role,
            "package": job.package,
            "location": job.location,
            "status": job.status
        }
        for job in jobs
    ]


@router.put("/jobs/{job_id}")
def update_job(
    job_id: int,
    job_data: JobUpdate,
    user=Depends(admin_required),
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

    if job.recruitment_drive.status in ["Closed", "Cancelled"]:
        raise HTTPException(
            status_code=400,
            detail="Cannot update a job in a closed or cancelled drive"
        )

    allowed_statuses = ["Open", "Closed", "Cancelled"]

    if job_data.status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail="Invalid job status"
        )

    job.role = job_data.role
    job.package = job_data.package
    job.location = job_data.location
    job.status = job_data.status

    db.commit()
    db.refresh(job)

    return {
        "message": "Job updated successfully",
        "job_id": job.id,
        "status": job.status
    }


@router.delete("/jobs/{job_id}")
def delete_job(
    job_id: int,
    user=Depends(admin_required),
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

    if job.applications:
        raise HTTPException(
            status_code=409,
            detail="This job has applications. Close it instead of deleting it."
        )

    db.delete(job)
    db.commit()

    return {
        "message": "Job deleted successfully"
    }

# =========================
# APPLICATION MANAGEMENT
# =========================

@router.get("/applications")
def get_all_applications(
    user=Depends(admin_required),
    db: Session = Depends(get_db)
):
    applications = db.query(Application).all()

    result = []

    for application in applications:
        student = db.query(User).filter(
            User.id == application.user_id
        ).first()

        job = db.query(Job).filter(
            Job.id == application.job_id
        ).first()

        result.append({
            "application_id": application.id,
            "student_id": application.user_id,
            "student_name": student.name if student else None,
            "student_email": student.email if student else None,
            "job_id": application.job_id,
            "company": (
                job.recruitment_drive.company.name
                if job and job.recruitment_drive and job.recruitment_drive.company
                else None
            ),
            "recruitment_drive": (
                job.recruitment_drive.name
                if job and job.recruitment_drive
                else None
            ),
            "role": job.role if job else None,
            "status": application.status
        })
    return result


@router.put("/applications/{application_id}/status")
def update_application_status(
    application_id: int,
    status_data: ApplicationStatusUpdate,
    user=Depends(admin_required),
    db: Session = Depends(get_db)
):
    # Step 1: Find the application
    application = db.query(Application).filter(
        Application.id == application_id
    ).first()

    if not application:
        raise HTTPException(
            status_code=404,
            detail="Application not found"
        )

    status = status_data.status
    if status not in {*APPLICATION_STATUS_ORDER, "Rejected", "Offer Released"}:
        raise HTTPException(
            status_code=400,
            detail="Invalid status"
        )

    current_status = application.status
    valid_progression = (
        status == current_status
        or (
            current_status in APPLICATION_STATUS_ORDER
            and status in APPLICATION_STATUS_ORDER
            and APPLICATION_STATUS_ORDER[status] > APPLICATION_STATUS_ORDER[current_status]
        )
        or (current_status in APPLICATION_STATUS_ORDER and status == "Rejected")
        or (current_status == "Selected" and status == "Offer Released")
    )
    if not valid_progression:
        raise HTTPException(
            status_code=409,
            detail=f"Invalid application status transition from {current_status} to {status}"
        )

    application.status = status

    db.commit()
    db.refresh(application)

    # Step 6: Return response
    return {
        "message": "Application status updated successfully",
        "application_id": application.id,
        "status": application.status
    }