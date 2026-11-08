"""Private resume storage with local development and S3-compatible production backends."""

import logging
import re
from pathlib import Path
from urllib.parse import quote

from fastapi import HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from app.config import (
    RESUME_STORAGE_BACKEND,
    S3_ACCESS_KEY_ID,
    S3_BUCKET_NAME,
    S3_ENDPOINT_URL,
    S3_REGION,
    S3_SECRET_ACCESS_KEY,
)

logger = logging.getLogger(__name__)
BACKEND_DIR = Path(__file__).resolve().parents[1]
RESUME_DIRECTORY = BACKEND_DIR / "storage" / "resumes"
MAX_RESUME_BYTES = 5 * 1024 * 1024

_s3_client = None


def _client():
    global _s3_client
    if _s3_client is None:
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("boto3 is required when RESUME_STORAGE_BACKEND=s3.") from exc
        _s3_client = boto3.client(
            "s3",
            endpoint_url=S3_ENDPOINT_URL,
            aws_access_key_id=S3_ACCESS_KEY_ID,
            aws_secret_access_key=S3_SECRET_ACCESS_KEY,
            region_name=S3_REGION,
        )
    return _s3_client


def is_remote_key(location: str) -> bool:
    return isinstance(location, str) and bool(
        re.fullmatch(r"resumes/\d+/[A-Fa-f0-9]{32}\.pdf", location)
    )


def store_resume(student_id: int, stored_filename: str, content: bytes) -> str:
    """Store bytes and return a local path or private object key for the DB."""
    if RESUME_STORAGE_BACKEND == "local":
        destination = _local_path(str(RESUME_DIRECTORY / Path(stored_filename).name))
        try:
            RESUME_DIRECTORY.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        except OSError as exc:
            logger.exception("Unable to store resume in local storage.")
            raise RuntimeError("Resume storage is temporarily unavailable.") from exc
        return str(destination)

    object_key = f"resumes/{student_id}/{Path(stored_filename).name}"
    try:
        _client().put_object(
            Bucket=S3_BUCKET_NAME,
            Key=object_key,
            Body=content,
            ContentType="application/pdf",
            CacheControl="private, no-store, max-age=0",
        )
    except Exception as exc:
        logger.exception("Unable to store resume in private object storage.")
        raise RuntimeError("Resume storage is temporarily unavailable.") from exc
    return object_key


def _local_path(location: str) -> Path:
    directory = RESUME_DIRECTORY.resolve()
    path = Path(location).resolve()
    if path.parent != directory or path.suffix.lower() != ".pdf":
        raise ValueError("Invalid resume storage path.")
    return path


def read_stored_resume(location: str) -> bytes:
    """Read one bounded private PDF for a compensating delete transaction."""
    if is_remote_key(location):
        body = None
        try:
            result = _client().get_object(Bucket=S3_BUCKET_NAME, Key=location)
            body = result["Body"]
            content = body.read(MAX_RESUME_BYTES + 1)
            if len(content) > MAX_RESUME_BYTES:
                raise RuntimeError("Stored resume exceeds the supported size.")
            return content
        except RuntimeError:
            raise
        except Exception as exc:
            logger.exception("Unable to read resume from private object storage.")
            raise RuntimeError("Resume storage is temporarily unavailable.") from exc
        finally:
            if body is not None:
                body.close()

    try:
        path = _local_path(location)
        if not path.is_file() or path.stat().st_size > MAX_RESUME_BYTES:
            raise RuntimeError("Stored resume is unavailable.")
        return path.read_bytes()
    except (OSError, ValueError) as exc:
        logger.exception("Unable to read resume from local storage.")
        raise RuntimeError("Resume storage is temporarily unavailable.") from exc


def restore_stored_resume(location: str, content: bytes) -> None:
    """Restore a resume at its original private location after a failed DB commit."""
    if is_remote_key(location):
        try:
            _client().put_object(
                Bucket=S3_BUCKET_NAME,
                Key=location,
                Body=content,
                ContentType="application/pdf",
                CacheControl="private, no-store, max-age=0",
            )
        except Exception as exc:
            logger.exception("Unable to restore resume in private object storage.")
            raise RuntimeError("Resume storage is temporarily unavailable.") from exc
        return

    try:
        path = _local_path(location)
        path.write_bytes(content)
    except (OSError, ValueError) as exc:
        logger.exception("Unable to restore resume in local storage.")
        raise RuntimeError("Resume storage is temporarily unavailable.") from exc


def delete_stored_resume(location: str) -> None:
    """Delete one private stored resume. Local paths are restricted to the resume directory."""
    if is_remote_key(location):
        try:
            _client().delete_object(Bucket=S3_BUCKET_NAME, Key=location)
        except Exception as exc:
            logger.exception("Unable to delete resume object from private storage.")
            raise RuntimeError("Resume storage is temporarily unavailable.") from exc
        return

    try:
        _local_path(location).unlink(missing_ok=True)
    except (OSError, ValueError) as exc:
        logger.exception("Unable to delete resume from local storage.")
        raise RuntimeError("Resume storage is temporarily unavailable.") from exc


def _safe_filename(filename: str) -> str:
    name = (filename or "resume.pdf").replace("\\", "/").split("/")[-1]
    name = "".join(character for character in name if ord(character) >= 32 and character not in {'"', "\\"})
    return name[:255] or "resume.pdf"


def resume_response(location: str, original_filename: str, disposition: str = "attachment"):
    """Return a protected local file response or a streamed private object response."""
    safe_name = _safe_filename(original_filename)

    if is_remote_key(location):
        try:
            result = _client().get_object(Bucket=S3_BUCKET_NAME, Key=location)
            body = result["Body"]
        except Exception as exc:
            logger.exception("Unable to retrieve resume from private object storage.")
            raise HTTPException(status_code=503, detail="Resume storage is temporarily unavailable.") from exc

        def chunks():
            try:
                while True:
                    chunk = body.read(64 * 1024)
                    if not chunk:
                        break
                    yield chunk
            finally:
                body.close()

        ascii_name = re.sub(r"[^A-Za-z0-9._-]", "_", safe_name)
        headers = {
            "Content-Disposition": f"{disposition}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(safe_name)}",
            "Content-Length": str(result.get("ContentLength", "")),
            "Cache-Control": "private, no-store, max-age=0",
            "X-Content-Type-Options": "nosniff",
        }
        headers = {key: value for key, value in headers.items() if value}
        return StreamingResponse(chunks(), media_type="application/pdf", headers=headers)

    path = Path(location).resolve()
    if path.parent != RESUME_DIRECTORY.resolve() or path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=410, detail="Resume file is unavailable")
    if not path.is_file():
        raise HTTPException(status_code=410, detail="Resume file is missing from storage")
    return FileResponse(
        path=str(path),
        media_type="application/pdf",
        filename=safe_name,
        content_disposition_type=disposition,
        headers={"Cache-Control": "private, no-store, max-age=0", "X-Content-Type-Options": "nosniff"},
    )
