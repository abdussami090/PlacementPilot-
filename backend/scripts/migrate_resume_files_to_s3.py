"""Copy existing local uploaded resumes to private S3-compatible object storage.

Run from backend after setting RESUME_STORAGE_BACKEND=s3 and the S3_* variables.
The old local files are deliberately retained so this operation can be rolled back.
"""

from pathlib import Path

from app.config import RESUME_STORAGE_BACKEND
from app.database import SessionLocal
from app.resume_file import UploadedResume
from app.resume_storage import is_remote_key, store_resume


def main() -> None:
    if RESUME_STORAGE_BACKEND != "s3":
        raise SystemExit("Set RESUME_STORAGE_BACKEND=s3 and the S3_* variables first.")

    db = SessionLocal()
    migrated = 0
    skipped = 0
    missing = []
    try:
        records = db.query(UploadedResume).order_by(UploadedResume.id).all()
        for record in records:
            if is_remote_key(record.storage_path):
                skipped += 1
                continue

            local_path = Path(record.storage_path)
            if not local_path.is_file():
                missing.append(record.id)
                continue

            content = local_path.read_bytes()
            object_key = store_resume(record.user_id, record.stored_filename, content)
            record.storage_path = object_key
            db.commit()
            migrated += 1
            print(f"Migrated resume record {record.id}.")

        print(f"Migration complete. Migrated={migrated}, already_remote={skipped}, missing_local_files={len(missing)}")
        if missing:
            print("Missing resume record IDs:", ", ".join(map(str, missing)))
            raise SystemExit(2)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
