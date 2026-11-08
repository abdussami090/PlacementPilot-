import asyncio
from pathlib import Path

from app import resume_storage


def test_local_resume_storage_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(resume_storage, "RESUME_STORAGE_BACKEND", "local")
    monkeypatch.setattr(resume_storage, "RESUME_DIRECTORY", tmp_path)

    content = b"%PDF-test-document"
    location = resume_storage.store_resume(7, "example-resume.pdf", content)

    stored_path = Path(location)
    assert stored_path.parent == tmp_path.resolve()
    assert stored_path.read_bytes() == content

    response = resume_storage.resume_response(location, "my-resume.pdf", "attachment")
    assert response.path == str(stored_path)
    assert response.media_type == "application/pdf"

    resume_storage.delete_stored_resume(location)
    assert not stored_path.exists()


def test_s3_storage_uses_private_object_key(monkeypatch):
    class FakeClient:
        def __init__(self):
            self.uploaded = None
            self.deleted = None

        def put_object(self, **kwargs):
            self.uploaded = kwargs

        def delete_object(self, **kwargs):
            self.deleted = kwargs

    fake = FakeClient()
    monkeypatch.setattr(resume_storage, "RESUME_STORAGE_BACKEND", "s3")
    monkeypatch.setattr(resume_storage, "S3_BUCKET_NAME", "private-test-bucket")
    monkeypatch.setattr(resume_storage, "_client", lambda: fake)

    key = resume_storage.store_resume(12, "a" * 32 + ".pdf", b"%PDF-test")
    assert key == f"resumes/12/{'a' * 32}.pdf"
    assert fake.uploaded["Bucket"] == "private-test-bucket"
    assert fake.uploaded["Key"] == key
    assert fake.uploaded["ContentType"] == "application/pdf"
    assert fake.uploaded["CacheControl"] == "private, no-store, max-age=0"

    resume_storage.delete_stored_resume(key)
    assert fake.deleted == {"Bucket": "private-test-bucket", "Key": key}


def test_local_resume_can_be_restored_to_its_original_location(tmp_path, monkeypatch):
    monkeypatch.setattr(resume_storage, "RESUME_STORAGE_BACKEND", "local")
    monkeypatch.setattr(resume_storage, "RESUME_DIRECTORY", tmp_path)
    content = b"%PDF-test-document"
    location = resume_storage.store_resume(7, "a" * 32 + ".pdf", content)

    assert resume_storage.read_stored_resume(location) == content
    resume_storage.delete_stored_resume(location)
    resume_storage.restore_stored_resume(location, content)

    assert Path(location).read_bytes() == content


def test_local_storage_rejects_paths_outside_resume_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(resume_storage, "RESUME_DIRECTORY", tmp_path / "resumes")

    try:
        resume_storage.read_stored_resume(str(tmp_path / "outside.pdf"))
    except RuntimeError as exc:
        assert str(exc) == "Resume storage is temporarily unavailable."
    else:
        raise AssertionError("Expected out-of-directory resume paths to be rejected")


def test_s3_storage_errors_are_sanitized(monkeypatch):
    class BrokenClient:
        def put_object(self, **_kwargs):
            raise OSError("provider details must not reach the caller")

    monkeypatch.setattr(resume_storage, "RESUME_STORAGE_BACKEND", "s3")
    monkeypatch.setattr(resume_storage, "_client", lambda: BrokenClient())

    try:
        resume_storage.store_resume(12, "a" * 32 + ".pdf", b"%PDF-test")
    except RuntimeError as exc:
        assert str(exc) == "Resume storage is temporarily unavailable."
    else:
        raise AssertionError("Expected storage errors to be surfaced")


def test_s3_read_closes_body_and_rejects_storage_failures(monkeypatch):
    class Body:
        closed = False

        def read(self, size):
            assert size == resume_storage.MAX_RESUME_BYTES + 1
            return b"%PDF-test"

        def close(self):
            self.closed = True

    body = Body()

    class FakeClient:
        def get_object(self, **kwargs):
            assert kwargs == {
                "Bucket": "private-test-bucket",
                "Key": f"resumes/12/{'a' * 32}.pdf",
            }
            return {"Body": body}

    monkeypatch.setattr(resume_storage, "RESUME_STORAGE_BACKEND", "s3")
    monkeypatch.setattr(resume_storage, "S3_BUCKET_NAME", "private-test-bucket")
    monkeypatch.setattr(resume_storage, "_client", lambda: FakeClient())
    key = f"resumes/12/{'a' * 32}.pdf"

    assert resume_storage.read_stored_resume(key) == b"%PDF-test"
    assert body.closed

    class BrokenClient:
        def get_object(self, **kwargs):
            raise OSError("private provider response")

    monkeypatch.setattr(resume_storage, "_client", lambda: BrokenClient())
    try:
        resume_storage.read_stored_resume(key)
    except RuntimeError as exc:
        assert str(exc) == "Resume storage is temporarily unavailable."
        assert "private provider response" not in str(exc)
    else:
        raise AssertionError("Expected failed S3 reads to be surfaced")


def test_s3_response_is_streamed_private_and_closes_body(monkeypatch):
    class Body:
        closed = False

        def __init__(self):
            self.chunks = [b"%PDF-test", b""]

        def read(self, size):
            assert size == 64 * 1024
            return self.chunks.pop(0)

        def close(self):
            self.closed = True

    body = Body()

    class FakeClient:
        def get_object(self, **kwargs):
            assert kwargs == {
                "Bucket": "private-test-bucket",
                "Key": f"resumes/12/{'a' * 32}.pdf",
            }
            return {"Body": body, "ContentLength": 9}

    monkeypatch.setattr(resume_storage, "RESUME_STORAGE_BACKEND", "s3")
    monkeypatch.setattr(resume_storage, "S3_BUCKET_NAME", "private-test-bucket")
    monkeypatch.setattr(resume_storage, "_client", lambda: FakeClient())

    response = resume_storage.resume_response(
        f"resumes/12/{'a' * 32}.pdf",
        "../../private resume.pdf",
    )
    assert response.headers["cache-control"] == "private, no-store, max-age=0"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-type"] == "application/pdf"
    assert "private resume.pdf" not in response.headers["content-disposition"].split("filename=")[1].split(";")[0]
    async def collect():
        return [chunk async for chunk in response.body_iterator]

    assert b"".join(asyncio.run(collect())) == b"%PDF-test"
    assert body.closed


def test_s3_delete_and_restore_failures_are_reported(monkeypatch):
    class BrokenClient:
        def delete_object(self, **kwargs):
            raise OSError("provider delete details")

        def put_object(self, **kwargs):
            raise OSError("provider restore details")

    monkeypatch.setattr(resume_storage, "RESUME_STORAGE_BACKEND", "s3")
    monkeypatch.setattr(resume_storage, "_client", lambda: BrokenClient())
    location = f"resumes/12/{'a' * 32}.pdf"

    for operation in (
        lambda: resume_storage.delete_stored_resume(location),
        lambda: resume_storage.restore_stored_resume(location, b"%PDF-test"),
    ):
        try:
            operation()
        except RuntimeError as exc:
            assert str(exc) == "Resume storage is temporarily unavailable."
            assert "provider" not in str(exc)
        else:
            raise AssertionError("Expected S3 operation failure to be surfaced")
