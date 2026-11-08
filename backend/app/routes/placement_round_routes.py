from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application import Application
from app.candidate_round import CandidateRound
from app.candidate_round_schema import CandidateRoundResultUpdate
from app.database import get_db
from app.dependencies import admin_required
from app.job import Job
from app.models import User
from app.placement_drive import CompanyRecruitmentDrive
from app.placement_round import PlacementRound
from app.placement_round_schema import PlacementRoundCreate, PlacementRoundUpdate
from app.security import oauth2_scheme, verify_token


router = APIRouter(tags=["Placement Rounds"])

ACTIVE_APPLICATION_STATUSES = [
    "Applied",
    "Under Review",
    "Shortlisted",
    "In Progress",
    "Selected",
]

TERMINAL_APPLICATION_STATUSES = [
    "Rejected",
    "Withdrawn",
    "Offer Released",
    "Offer Accepted",
    "Offer Declined",
    "Joined",
]

ROUND_STATUS_TRANSITIONS = {
    "Draft": {"Draft", "Scheduled", "Cancelled"},
    "Scheduled": {"Scheduled", "In Progress", "Cancelled"},
    "In Progress": {"In Progress", "Completed", "Cancelled"},
    "Completed": {"Completed"},
    "Cancelled": {"Cancelled"},
}


def _get_round(db: Session, round_id: int) -> PlacementRound:
    round_record = db.query(PlacementRound).filter(PlacementRound.id == round_id).first()
    if not round_record:
        raise HTTPException(status_code=404, detail="Placement round not found")
    return round_record


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


def _previous_round(db: Session, round_record: PlacementRound):
    return (
        db.query(PlacementRound)
        .filter(
            PlacementRound.recruitment_drive_id == round_record.recruitment_drive_id,
            PlacementRound.sequence < round_record.sequence,
            PlacementRound.status != "Cancelled",
        )
        .order_by(PlacementRound.sequence.desc())
        .first()
    )


def _can_progress(db: Session, round_record: PlacementRound, application: Application) -> bool:
    """First round accepts active applicants; later rounds require a pass in the prior round."""
    if application.job.recruitment_drive_id != round_record.recruitment_drive_id:
        return False
    if application.status not in ACTIVE_APPLICATION_STATUSES:
        return False

    previous = _previous_round(db, round_record)
    if previous is None:
        return True

    prior_result = (
        db.query(CandidateRound)
        .filter(
            CandidateRound.placement_round_id == previous.id,
            CandidateRound.application_id == application.id,
        )
        .first()
    )
    return bool(
        prior_result
        and prior_result.attendance == "Present"
        and prior_result.result == "Pass"
    )


def _round_to_dict(round_record: PlacementRound) -> dict:
    return {
        "id": round_record.id,
        "recruitment_drive_id": round_record.recruitment_drive_id,
        "name": round_record.name,
        "sequence": round_record.sequence,
        "description": round_record.description,
        "scheduled_at": round_record.scheduled_at,
        "scheduled_end": round_record.scheduled_end,
        "venue": round_record.venue,
        "meeting_link": round_record.meeting_link,
        "status": round_record.status,
        "created_at": round_record.created_at,
        "updated_at": round_record.updated_at,
    }


@router.post("/admin/recruitment-drives/{drive_id}/rounds")
def create_placement_round(
    drive_id: int,
    round_data: PlacementRoundCreate,
    user=Depends(admin_required),
    db: Session = Depends(get_db),
):
    drive = db.query(CompanyRecruitmentDrive).filter(CompanyRecruitmentDrive.id == drive_id).first()
    if not drive:
        raise HTTPException(status_code=404, detail="Recruitment drive not found")
    if drive.status in {"Closed", "Cancelled"}:
        raise HTTPException(status_code=409, detail="Cannot add rounds to a closed or cancelled drive")

    duplicate = db.query(PlacementRound).filter(
        PlacementRound.recruitment_drive_id == drive_id,
        PlacementRound.sequence == round_data.sequence,
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="This round sequence already exists for the drive")

    round_record = PlacementRound(
        recruitment_drive_id=drive_id,
        name=round_data.name,
        sequence=round_data.sequence,
        description=round_data.description,
        scheduled_at=round_data.scheduled_at,
        scheduled_end=round_data.scheduled_end,
        venue=round_data.venue,
        meeting_link=round_data.meeting_link,
        status=round_data.status,
        created_by=user.id,
    )
    db.add(round_record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Round sequence already exists for this drive")
    db.refresh(round_record)
    return {"message": "Placement round created successfully", "round": _round_to_dict(round_record)}


@router.get("/admin/recruitment-drives/{drive_id}/rounds")
def get_drive_rounds(
    drive_id: int,
    user=Depends(admin_required),
    db: Session = Depends(get_db),
):
    drive = db.query(CompanyRecruitmentDrive).filter(CompanyRecruitmentDrive.id == drive_id).first()
    if not drive:
        raise HTTPException(status_code=404, detail="Recruitment drive not found")

    rounds = (
        db.query(PlacementRound)
        .filter(PlacementRound.recruitment_drive_id == drive_id)
        .order_by(PlacementRound.sequence.asc())
        .all()
    )
    return [_round_to_dict(item) for item in rounds]


@router.put("/admin/rounds/{round_id}")
def update_placement_round(
    round_id: int,
    round_data: PlacementRoundUpdate,
    user=Depends(admin_required),
    db: Session = Depends(get_db),
):
    round_record = _get_round(db, round_id)

    if round_data.status not in ROUND_STATUS_TRANSITIONS[round_record.status]:
        raise HTTPException(
            status_code=409,
            detail=f"Invalid round status transition from {round_record.status} to {round_data.status}",
        )

    if round_data.sequence != round_record.sequence:
        has_assignments = db.query(CandidateRound.id).filter(
            CandidateRound.placement_round_id == round_id
        ).first()
        has_later_rounds = db.query(PlacementRound.id).filter(
            PlacementRound.recruitment_drive_id == round_record.recruitment_drive_id,
            PlacementRound.sequence > round_record.sequence,
            PlacementRound.status != "Cancelled",
        ).first()
        if has_assignments or has_later_rounds:
            raise HTTPException(
                status_code=409,
                detail="Round sequence cannot be changed after candidates are assigned or a later round exists",
            )

    duplicate = db.query(PlacementRound).filter(
        PlacementRound.recruitment_drive_id == round_record.recruitment_drive_id,
        PlacementRound.sequence == round_data.sequence,
        PlacementRound.id != round_id,
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="This round sequence already exists for the drive")

    round_record.name = round_data.name
    round_record.sequence = round_data.sequence
    round_record.description = round_data.description
    round_record.scheduled_at = round_data.scheduled_at
    round_record.scheduled_end = round_data.scheduled_end
    round_record.venue = round_data.venue
    round_record.meeting_link = round_data.meeting_link
    round_record.status = round_data.status

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Round sequence already exists for this drive")
    db.refresh(round_record)
    return {"message": "Placement round updated successfully", "round": _round_to_dict(round_record)}


@router.delete("/admin/rounds/{round_id}")
def delete_placement_round(
    round_id: int,
    user=Depends(admin_required),
    db: Session = Depends(get_db),
):
    round_record = _get_round(db, round_id)
    if round_record.status != "Draft":
        raise HTTPException(status_code=409, detail="Only Draft rounds can be deleted. Cancel scheduled rounds instead.")

    has_candidates = db.query(CandidateRound.id).filter(
        CandidateRound.placement_round_id == round_id
    ).first()
    if has_candidates:
        raise HTTPException(status_code=409, detail="This round has candidate assignments and cannot be deleted")

    db.delete(round_record)
    db.commit()
    return {"message": "Placement round deleted successfully", "round_id": round_id}


@router.post("/admin/rounds/{round_id}/assign-candidates")
def assign_candidates_to_round(
    round_id: int,
    user=Depends(admin_required),
    db: Session = Depends(get_db),
):
    round_record = _get_round(db, round_id)
    if round_record.status not in {"Scheduled", "In Progress"}:
        raise HTTPException(status_code=409, detail="Only Scheduled or In Progress rounds can receive candidates")

    query = (
        db.query(Application)
        .join(Job, Application.job_id == Job.id)
        .filter(
            Job.recruitment_drive_id == round_record.recruitment_drive_id,
            Application.status.in_(ACTIVE_APPLICATION_STATUSES),
        )
    )

    previous = _previous_round(db, round_record)
    if previous:
        passed_application_ids = (
            db.query(CandidateRound.application_id)
            .filter(
                CandidateRound.placement_round_id == previous.id,
                CandidateRound.attendance == "Present",
                CandidateRound.result == "Pass",
            )
        )
        query = query.filter(Application.id.in_(passed_application_ids))

    applications = query.all()
    existing_ids = {
        row[0]
        for row in db.query(CandidateRound.application_id)
        .filter(CandidateRound.placement_round_id == round_id)
        .all()
    }

    new_rows = [
        CandidateRound(application_id=app.id, placement_round_id=round_id)
        for app in applications
        if app.id not in existing_ids
    ]
    if new_rows:
        db.add_all(new_rows)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="One or more candidates were assigned concurrently; refresh and retry")

    return {
        "message": "Candidate assignment completed",
        "round_id": round_id,
        "assigned_count": len(new_rows),
        "already_assigned_count": len(existing_ids),
        "progression_rule": (
            f"Candidates who passed round {previous.sequence}"
            if previous else "All active applicants in this recruitment drive"
        ),
    }


@router.post("/admin/rounds/{round_id}/assignments/{application_id}")
def assign_candidate_to_round(
    round_id: int,
    application_id: int,
    user=Depends(admin_required),
    db: Session = Depends(get_db),
):
    round_record = _get_round(db, round_id)
    if round_record.status not in {"Scheduled", "In Progress"}:
        raise HTTPException(status_code=409, detail="Only Scheduled or In Progress rounds can receive candidates")

    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    if not _can_progress(db, round_record, application):
        raise HTTPException(
            status_code=409,
            detail="Candidate does not belong to this drive, is not active, or has not passed the previous round",
        )

    existing = db.query(CandidateRound).filter(
        CandidateRound.application_id == application_id,
        CandidateRound.placement_round_id == round_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Candidate is already assigned to this round")

    assignment = CandidateRound(application_id=application_id, placement_round_id=round_id)
    db.add(assignment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Candidate is already assigned to this round")
    db.refresh(assignment)
    return {
        "message": "Candidate assigned to placement round successfully",
        "assignment_id": assignment.id,
        "application_id": application_id,
        "round_id": round_id,
        "attendance": assignment.attendance,
        "result": assignment.result,
    }


@router.get("/admin/rounds/{round_id}/candidates")
def get_round_candidates(
    round_id: int,
    user=Depends(admin_required),
    db: Session = Depends(get_db),
):
    _get_round(db, round_id)
    rows = (
        db.query(CandidateRound, Application, User, Job)
        .join(Application, CandidateRound.application_id == Application.id)
        .join(User, Application.user_id == User.id)
        .join(Job, Application.job_id == Job.id)
        .filter(CandidateRound.placement_round_id == round_id)
        .order_by(User.name.asc())
        .all()
    )
    return [
        {
            "assignment_id": assignment.id,
            "application_id": application.id,
            "student_id": student.id,
            "student_name": student.name,
            "student_email": student.email,
            "job_id": job.id,
            "job_role": job.role,
            "application_status": application.status,
            "attendance": assignment.attendance,
            "result": assignment.result,
            "score": assignment.score,
            "feedback": assignment.feedback,
            "assigned_at": assignment.assigned_at,
            "evaluated_at": assignment.evaluated_at,
        }
        for assignment, application, student, job in rows
    ]


@router.put("/admin/rounds/{round_id}/candidates/{application_id}/result")
def update_candidate_round_result(
    round_id: int,
    application_id: int,
    result_data: CandidateRoundResultUpdate,
    user=Depends(admin_required),
    db: Session = Depends(get_db),
):
    round_record = _get_round(db, round_id)
    if round_record.status not in {"Scheduled", "In Progress"}:
        raise HTTPException(status_code=409, detail="Results can only be updated for Scheduled or In Progress rounds")

    assignment = db.query(CandidateRound).filter(
        CandidateRound.placement_round_id == round_id,
        CandidateRound.application_id == application_id,
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Candidate is not assigned to this round")

    assignment.attendance = result_data.attendance
    assignment.result = result_data.result
    assignment.score = result_data.score
    assignment.feedback = result_data.feedback
    assignment.evaluated_by = user.id
    assignment.evaluated_at = datetime.utcnow()

    db.commit()
    db.refresh(assignment)
    return {
        "message": "Candidate round result updated successfully",
        "assignment_id": assignment.id,
        "application_id": assignment.application_id,
        "round_id": assignment.placement_round_id,
        "attendance": assignment.attendance,
        "result": assignment.result,
        "score": assignment.score,
        "feedback": assignment.feedback,
        "evaluated_at": assignment.evaluated_at,
    }


@router.get("/student/rounds")
def get_my_placement_rounds(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    student = _get_student(token, db)
    rows = (
        db.query(CandidateRound, PlacementRound, Application, Job, CompanyRecruitmentDrive)
        .join(PlacementRound, CandidateRound.placement_round_id == PlacementRound.id)
        .join(Application, CandidateRound.application_id == Application.id)
        .join(Job, Application.job_id == Job.id)
        .join(CompanyRecruitmentDrive, PlacementRound.recruitment_drive_id == CompanyRecruitmentDrive.id)
        .filter(Application.user_id == student.id)
        .filter(PlacementRound.status != "Cancelled")
        .order_by(PlacementRound.scheduled_at.asc(), PlacementRound.sequence.asc())
        .all()
    )

    return [
        {
            "application_id": application.id,
            "job_role": job.role,
            "recruitment_drive_id": drive.id,
            "recruitment_drive": drive.name,
            "round_id": round_record.id,
            "round_name": round_record.name,
            "round_sequence": round_record.sequence,
            "scheduled_at": round_record.scheduled_at,
            "scheduled_end": round_record.scheduled_end,
            "venue": round_record.venue,
            "meeting_link": round_record.meeting_link,
            "round_status": round_record.status,
            "attendance": assignment.attendance,
            "result": assignment.result,
            "score": assignment.score,
            "feedback": assignment.feedback,
        }
        for assignment, round_record, application, job, drive in rows
    ]
