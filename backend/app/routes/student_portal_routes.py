from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application import Application
from app.candidate_round import CandidateRound
from app.company import Company
from app.database import get_db
from app.dependencies import admin_required
from app.eligibility_service import evaluate_eligibility
from app.job import Job
from app.models import User
from app.placement_cycle import PlacementCycle
from app.placement_drive import CompanyRecruitmentDrive
from app.placement_round import PlacementRound
from app.saved_job import SavedJob
from app.security import oauth2_scheme, verify_token

router = APIRouter(tags=["Student Portal", "Dashboards"])


ACTIVE_ROUND_STATUSES = {"Scheduled", "In Progress"}


def _get_student(token: str, db: Session) -> User:
    email = verify_token(token)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    student = db.query(User).filter(User.email == email).first()
    if not student:
        raise HTTPException(status_code=401, detail="User associated with token was not found")
    if student.role != "student":
        raise HTTPException(status_code=403, detail="Only students can access this endpoint")
    return student


def _job_payload(job: Job, eligibility: Optional[dict] = None) -> dict:
    drive = job.recruitment_drive
    company = drive.company if drive else None
    cycle = drive.placement_cycle if drive else None
    return {
        "id": job.id,
        "role": job.role,
        "package": job.package,
        "location": job.location,
        "status": job.status,
        "company": {
            "id": company.id,
            "name": company.name,
            "website": getattr(company, "website", None),
        } if company else None,
        "recruitment_drive": {
            "id": drive.id,
            "name": drive.name,
            "application_start_date": drive.application_start_date,
            "application_deadline": drive.application_deadline,
            "status": drive.status,
        } if drive else None,
        "placement_cycle": {
            "id": cycle.id,
            "name": cycle.name,
            "academic_year": cycle.academic_year,
        } if cycle else None,
        "eligibility": eligibility,
    }


def _official_open_jobs_query(db: Session):
    today = date.today()
    return (
        db.query(Job)
        .join(CompanyRecruitmentDrive, Job.recruitment_drive_id == CompanyRecruitmentDrive.id)
        .join(PlacementCycle, CompanyRecruitmentDrive.placement_cycle_id == PlacementCycle.id)
        .join(Company, CompanyRecruitmentDrive.company_id == Company.id)
        .filter(
            Job.status == "Open",
            CompanyRecruitmentDrive.status == "Published",
            PlacementCycle.status == "Active",
            Company.is_active.is_(True),
            or_(CompanyRecruitmentDrive.application_start_date.is_(None), CompanyRecruitmentDrive.application_start_date <= today),
            or_(CompanyRecruitmentDrive.application_deadline.is_(None), CompanyRecruitmentDrive.application_deadline >= today),
            or_(PlacementCycle.start_date.is_(None), PlacementCycle.start_date <= today),
            or_(PlacementCycle.end_date.is_(None), PlacementCycle.end_date >= today),
        )
    )


@router.get("/student/jobs")
def discover_jobs(
    search: Optional[str] = Query(default=None, min_length=1, max_length=100),
    location: Optional[str] = Query(default=None, min_length=1, max_length=100),
    company_id: Optional[int] = Query(default=None, ge=1),
    drive_id: Optional[int] = Query(default=None, ge=1),
    cycle_id: Optional[int] = Query(default=None, ge=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    """Discover only official, published jobs currently open for applications."""
    student = _get_student(token, db)
    query = _official_open_jobs_query(db)

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Job.role.ilike(term),
                Company.name.ilike(term),
                CompanyRecruitmentDrive.name.ilike(term),
            )
        )
    if location:
        query = query.filter(Job.location.ilike(f"%{location.strip()}%"))
    if company_id:
        query = query.filter(CompanyRecruitmentDrive.company_id == company_id)
    if drive_id:
        query = query.filter(CompanyRecruitmentDrive.id == drive_id)
    if cycle_id:
        query = query.filter(CompanyRecruitmentDrive.placement_cycle_id == cycle_id)

    total = query.count()
    jobs = (
        query.order_by(Job.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    saved_ids = {
        row[0]
        for row in db.query(SavedJob.job_id)
        .filter(SavedJob.user_id == student.id, SavedJob.job_id.in_([job.id for job in jobs]))
        .all()
    } if jobs else set()

    results = []
    for job in jobs:
        eligibility = evaluate_eligibility(db=db, user_id=student.id, job_id=job.id)
        item = _job_payload(job, eligibility)
        item["is_saved"] = job.id in saved_ids
        results.append(item)

    return {
        "items": results,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_items": total,
            "total_pages": (total + page_size - 1) // page_size,
            "has_next": page * page_size < total,
            "has_previous": page > 1,
        },
        "filters": {
            "search": search,
            "location": location,
            "company_id": company_id,
            "drive_id": drive_id,
            "cycle_id": cycle_id,
        },
    }


@router.get("/student/jobs/{job_id}")
def get_job_details(
    job_id: int,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    student = _get_student(token, db)
    job = _official_open_jobs_query(db).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Open published job not found")

    is_saved = db.query(SavedJob.id).filter(
        SavedJob.user_id == student.id,
        SavedJob.job_id == job_id,
    ).first() is not None
    eligibility = evaluate_eligibility(db=db, user_id=student.id, job_id=job.id)
    payload = _job_payload(job, eligibility)
    payload["is_saved"] = is_saved
    return payload


@router.post("/student/saved-jobs/{job_id}", status_code=201)
def save_job(
    job_id: int,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    student = _get_student(token, db)
    job = _official_open_jobs_query(db).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Open published job not found")

    existing = db.query(SavedJob).filter(
        SavedJob.user_id == student.id,
        SavedJob.job_id == job_id,
    ).first()
    if existing:
        return JSONResponse(status_code=200, content={"message": "Job is already saved", "job_id": job_id, "is_saved": True})

    saved = SavedJob(user_id=student.id, job_id=job_id)
    db.add(saved)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This job is already saved")
    return {"message": "Job saved successfully", "job_id": job_id, "is_saved": True}


@router.get("/student/saved-jobs")
def get_saved_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    student = _get_student(token, db)
    base_query = (
        db.query(SavedJob, Job)
        .join(Job, SavedJob.job_id == Job.id)
        .filter(SavedJob.user_id == student.id)
    )
    total = base_query.count()
    rows = (
        base_query.order_by(SavedJob.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = []
    for saved, job in rows:
        eligibility = evaluate_eligibility(db=db, user_id=student.id, job_id=job.id)
        payload = _job_payload(job, eligibility)
        payload["saved_at"] = saved.created_at
        payload["is_saved"] = True
        items.append(payload)
    return {
        "items": items,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_items": total,
            "total_pages": (total + page_size - 1) // page_size,
            "has_next": page * page_size < total,
            "has_previous": page > 1,
        },
    }


@router.delete("/student/saved-jobs/{job_id}")
def remove_saved_job(
    job_id: int,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    student = _get_student(token, db)
    saved = db.query(SavedJob).filter(
        SavedJob.user_id == student.id,
        SavedJob.job_id == job_id,
    ).first()
    if not saved:
        raise HTTPException(status_code=404, detail="Saved job not found")
    db.delete(saved)
    db.commit()
    return {"message": "Job removed from saved jobs", "job_id": job_id, "is_saved": False}


@router.get("/student/dashboard")
def get_student_dashboard(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    student = _get_student(token, db)
    applications = db.query(Application).filter(Application.user_id == student.id).all()
    status_counts = {}
    for application in applications:
        status_counts[application.status] = status_counts.get(application.status, 0) + 1

    saved_count = db.query(SavedJob).filter(SavedJob.user_id == student.id).count()
    now = datetime.utcnow()
    upcoming_rows = (
        db.query(CandidateRound, PlacementRound, Application, Job, CompanyRecruitmentDrive, Company)
        .join(PlacementRound, CandidateRound.placement_round_id == PlacementRound.id)
        .join(Application, CandidateRound.application_id == Application.id)
        .join(Job, Application.job_id == Job.id)
        .join(CompanyRecruitmentDrive, PlacementRound.recruitment_drive_id == CompanyRecruitmentDrive.id)
        .join(Company, CompanyRecruitmentDrive.company_id == Company.id)
        .filter(
            Application.user_id == student.id,
            PlacementRound.status.in_(list(ACTIVE_ROUND_STATUSES)),
            PlacementRound.scheduled_at.is_not(None),
            PlacementRound.scheduled_at >= now,
        )
        .order_by(PlacementRound.scheduled_at.asc())
        .limit(5)
        .all()
    )
    upcoming = [
        {
            "round_id": round_record.id,
            "round_name": round_record.name,
            "sequence": round_record.sequence,
            "scheduled_at": round_record.scheduled_at,
            "scheduled_end": round_record.scheduled_end,
            "venue": round_record.venue,
            "meeting_link": round_record.meeting_link,
            "round_status": round_record.status,
            "company": company.name,
            "job_role": job.role,
            "attendance": assignment.attendance,
            "result": assignment.result,
        }
        for assignment, round_record, application, job, drive, company in upcoming_rows
    ]

    return {
        "student": {"id": student.id, "name": student.name, "email": student.email},
        "statistics": {
            "total_applications": len(applications),
            "active_applications": sum(
                status_counts.get(status, 0)
                for status in ["Applied", "Under Review", "Shortlisted", "In Progress", "Selected"]
            ),
            "offers_released": status_counts.get("Offer Released", 0),
            "offers_accepted": status_counts.get("Offer Accepted", 0),
            "rejected": status_counts.get("Rejected", 0),
            "saved_jobs": saved_count,
        },
        "applications_by_status": status_counts,
        "upcoming_rounds": upcoming,
    }


@router.get("/student/timeline")
def get_student_timeline(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    """Return application snapshots and timestamped round assignment/result events."""
    student = _get_student(token, db)
    app_rows = (
        db.query(Application, Job, CompanyRecruitmentDrive, Company, PlacementCycle)
        .join(Job, Application.job_id == Job.id)
        .join(CompanyRecruitmentDrive, Job.recruitment_drive_id == CompanyRecruitmentDrive.id)
        .join(Company, CompanyRecruitmentDrive.company_id == Company.id)
        .join(PlacementCycle, CompanyRecruitmentDrive.placement_cycle_id == PlacementCycle.id)
        .filter(Application.user_id == student.id)
        .order_by(Application.id.desc())
        .all()
    )
    applications = [
        {
            "application_id": app.id,
            "job_id": job.id,
            "job_role": job.role,
            "company": company.name,
            "drive": drive.name,
            "placement_cycle": cycle.name,
            "current_status": app.status,
        }
        for app, job, drive, company, cycle in app_rows
    ]

    round_rows = (
        db.query(CandidateRound, PlacementRound, Application, Job, Company)
        .join(Application, CandidateRound.application_id == Application.id)
        .join(PlacementRound, CandidateRound.placement_round_id == PlacementRound.id)
        .join(Job, Application.job_id == Job.id)
        .join(CompanyRecruitmentDrive, PlacementRound.recruitment_drive_id == CompanyRecruitmentDrive.id)
        .join(Company, CompanyRecruitmentDrive.company_id == Company.id)
        .filter(Application.user_id == student.id)
        .order_by(CandidateRound.assigned_at.desc())
        .all()
    )
    events = []
    for assignment, round_record, application, job, company in round_rows:
        events.append({
            "event_type": "Round Assigned",
            "occurred_at": assignment.assigned_at,
            "application_id": application.id,
            "job_role": job.role,
            "company": company.name,
            "round_id": round_record.id,
            "round_name": round_record.name,
            "round_sequence": round_record.sequence,
            "scheduled_at": round_record.scheduled_at,
            "attendance": assignment.attendance,
            "result": assignment.result,
        })
        if assignment.evaluated_at:
            events.append({
                "event_type": "Round Result Recorded",
                "occurred_at": assignment.evaluated_at,
                "application_id": application.id,
                "job_role": job.role,
                "company": company.name,
                "round_id": round_record.id,
                "round_name": round_record.name,
                "round_sequence": round_record.sequence,
                "scheduled_at": round_record.scheduled_at,
                "attendance": assignment.attendance,
                "result": assignment.result,
                "score": assignment.score,
                "feedback": assignment.feedback,
            })
    events.sort(key=lambda item: item["occurred_at"] or datetime.min, reverse=True)
    return {"applications": applications, "events": events}


@router.get("/admin/dashboard/overview")
def get_admin_dashboard_overview(
    user=Depends(admin_required),
    db: Session = Depends(get_db),
):
    total_students = db.query(User).filter(User.role == "student").count()
    total_admins = db.query(User).filter(User.role == "admin").count()
    active_cycles = db.query(PlacementCycle).filter(PlacementCycle.status == "Active").count()
    published_drives = db.query(CompanyRecruitmentDrive).filter(CompanyRecruitmentDrive.status == "Published").count()
    open_jobs = db.query(Job).filter(Job.status == "Open").count()
    total_applications = db.query(Application).count()

    applications_by_status = {
        status: db.query(Application).filter(Application.status == status).count()
        for status in [
            "Applied", "Under Review", "Shortlisted", "In Progress", "Selected",
            "Rejected", "Withdrawn", "Offer Released", "Offer Accepted", "Offer Declined", "Joined",
        ]
    }
    upcoming_rounds = db.query(PlacementRound).filter(
        PlacementRound.status == "Scheduled",
        PlacementRound.scheduled_at.is_not(None),
        PlacementRound.scheduled_at >= datetime.utcnow(),
    ).count()

    return {
        "users": {"students": total_students, "admins": total_admins},
        "placement_cycles_active": active_cycles,
        "recruitment_drives_published": published_drives,
        "open_jobs": open_jobs,
        "total_applications": total_applications,
        "applications_by_status": applications_by_status,
        "upcoming_rounds": upcoming_rounds,
    }
