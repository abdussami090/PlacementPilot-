import logging
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.database import get_db
from app.dependencies import admin_required
from app.models import User
from app.resume_file import UploadedResume
from app.resume_storage import (
    MAX_RESUME_BYTES,
    delete_stored_resume,
    read_stored_resume,
    resume_response,
    restore_stored_resume,
    store_resume,
)
from app.security import oauth2_scheme, verify_token

router = APIRouter(tags=["PDF Resumes"])
logger = logging.getLogger(__name__)


def _current_student(token: str, db: Session) -> User:
    email = verify_token(token)
    if not email:
        raise HTTPException(401, "Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(401, "User associated with token was not found")
    if user.role != "student":
        raise HTTPException(403, "Only students can manage their own resume")
    return user


def _resume_payload(record: UploadedResume) -> dict:
    return {
        "id": record.id,
        "original_filename": record.original_filename,
        "content_type": record.content_type,
        "file_size": record.file_size,
        "uploaded_at": record.uploaded_at.isoformat() if record.uploaded_at else None,
    }


@router.post("/resume/upload", status_code=status.HTTP_201_CREATED)
async def upload_or_replace_resume(
    file: UploadFile = File(...),
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    """Upload one PDF resume. Uploading again replaces the student's current PDF."""
    student = _current_student(token, db)
    incoming_name = Path((file.filename or "").replace("\\", "/")).name
    if not incoming_name or Path(incoming_name).suffix.lower() != ".pdf":
        await file.close()
        raise HTTPException(400, "Only PDF files are accepted")
    if (file.content_type or "").split(";", 1)[0].strip().lower() != "application/pdf":
        await file.close()
        raise HTTPException(415, "The uploaded file must have PDF content type")

    try:
        content = await file.read(MAX_RESUME_BYTES + 1)
    finally:
        await file.close()
    if not content:
        raise HTTPException(400, "The selected PDF is empty")
    if len(content) > MAX_RESUME_BYTES:
        raise HTTPException(413, "PDF must be 5 MB or smaller")
    if not content.startswith(b"%PDF-") or b"%%EOF" not in content[-1024:]:
        raise HTTPException(400, "The file does not have valid PDF content")

    stored_name = f"{uuid4().hex}.pdf"
    try:
        new_location = await run_in_threadpool(store_resume, student.id, stored_name, content)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    old_location = None
    committed = False
    try:
        record = db.query(UploadedResume).filter(UploadedResume.user_id == student.id).first()
        if record:
            old_location = record.storage_path
            record.original_filename = incoming_name[:255]
            record.stored_filename = stored_name
            record.storage_path = new_location
            record.content_type = "application/pdf"
            record.file_size = len(content)
        else:
            record = UploadedResume(
                user_id=student.id,
                original_filename=incoming_name[:255],
                stored_filename=stored_name,
                storage_path=new_location,
                content_type="application/pdf",
                file_size=len(content),
            )
            db.add(record)

        db.commit()
        committed = True
        db.refresh(record)
    except Exception:
        db.rollback()
        if not committed:
            try:
                await run_in_threadpool(delete_stored_resume, new_location)
            except RuntimeError:
                logger.exception("Unable to clean up an unreferenced resume after upload failure.")
        raise

    cleanup_warning = False
    if old_location and old_location != new_location:
        try:
            await run_in_threadpool(delete_stored_resume, old_location)
        except RuntimeError:
            logger.exception("Replacement succeeded, but the previous resume requires cleanup.")
            cleanup_warning = True

    return {
        "message": "PDF resume uploaded successfully",
        "resume": _resume_payload(record),
        "cleanup_warning": cleanup_warning,
    }


@router.get("/resume/uploaded")
def get_my_uploaded_resume(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    student = _current_student(token, db)
    record = db.query(UploadedResume).filter(UploadedResume.user_id == student.id).first()
    return _resume_payload(record) if record else None


@router.get("/resume/uploaded/{resume_id}/download")
def download_my_resume(resume_id: int, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    student = _current_student(token, db)
    record = db.query(UploadedResume).filter(
        UploadedResume.id == resume_id, UploadedResume.user_id == student.id
    ).first()
    if not record:
        raise HTTPException(404, "Resume not found")
    return resume_response(record.storage_path, record.original_filename, "attachment")


@router.get("/resume/uploaded/{resume_id}/view")
def view_my_resume(resume_id: int, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    student = _current_student(token, db)
    record = db.query(UploadedResume).filter(
        UploadedResume.id == resume_id, UploadedResume.user_id == student.id
    ).first()
    if not record:
        raise HTTPException(404, "Resume not found")
    return resume_response(record.storage_path, record.original_filename, "inline")


@router.delete("/resume/uploaded/{resume_id}")
async def delete_my_uploaded_resume(
    resume_id: int,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    student = _current_student(token, db)
    record = db.query(UploadedResume).filter(
        UploadedResume.id == resume_id, UploadedResume.user_id == student.id
    ).first()
    if not record:
        raise HTTPException(404, "Resume not found")

    old_location = record.storage_path
    try:
        content = await run_in_threadpool(read_stored_resume, old_location)
        await run_in_threadpool(delete_stored_resume, old_location)
    except RuntimeError as exc:
        raise HTTPException(503, "Resume storage is temporarily unavailable; no database changes were made.") from exc

    try:
        db.delete(record)
        db.commit()
    except Exception:
        db.rollback()
        try:
            await run_in_threadpool(restore_stored_resume, old_location, content)
        except RuntimeError as restore_exc:
            logger.critical(
                "Resume file restoration failed after a database delete failure for record %s.",
                resume_id,
                exc_info=True,
            )
            raise HTTPException(
                500,
                "Resume deletion could not be completed; administrator recovery is required.",
            ) from restore_exc
        raise
    return {"message": "Uploaded PDF resume deleted successfully"}


@router.get("/admin/students/{student_id}/resume")
def admin_view_student_resume(student_id: int, admin=Depends(admin_required), db: Session = Depends(get_db)):
    """Admin-only access for authorized placement-cell review."""
    record = db.query(UploadedResume).filter(UploadedResume.user_id == student_id).first()
    if not record:
        raise HTTPException(404, "This student has not uploaded a PDF resume")
    return resume_response(record.storage_path, record.original_filename, "inline")
