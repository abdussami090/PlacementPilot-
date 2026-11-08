from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app import resume_storage
from app.routes import resume_file_routes


def login(client, email: str, password: str = "TestPassword123!") -> str:
    response = client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def upload(
    client,
    token: str,
    content: bytes = b"%PDF-1.7\ntest document\n%%EOF\n",
    filename: str = "resume.pdf",
):
    return client.post(
        "/resume/upload",
        headers=authorization(token),
        files={"file": (filename, content, "application/pdf")},
    )


def test_student_upload_replace_download_and_delete(client, create_user, tmp_path, monkeypatch):
    create_user("student@example.com", "student")
    token = login(client, "student@example.com")
    monkeypatch.setattr(resume_storage, "RESUME_DIRECTORY", tmp_path)

    first_content = b"%PDF-1.7\nfirst test document\n%%EOF\n"
    created = upload(client, token, content=first_content, filename="../../original.pdf")
    assert created.status_code == 201
    first = created.json()["resume"]
    assert first["original_filename"] == "original.pdf"
    first_path = next(tmp_path.glob("*.pdf"))
    assert first_path.read_bytes() == first_content

    downloaded = client.get(
        f"/resume/uploaded/{first['id']}/download",
        headers=authorization(token),
    )
    assert downloaded.status_code == 200
    assert downloaded.content == first_content
    assert downloaded.headers["cache-control"] == "private, no-store, max-age=0"
    assert downloaded.headers["x-content-type-options"] == "nosniff"

    replacement_content = b"%PDF-1.7\nreplacement document\n%%EOF\n"
    replaced = upload(client, token, replacement_content, "replacement.pdf")
    assert replaced.status_code == 201
    second = replaced.json()["resume"]
    assert second["id"] == first["id"]
    assert not first_path.exists()
    second_path = next(tmp_path.glob("*.pdf"))
    assert second_path.read_bytes() == replacement_content

    deleted = client.delete(
        f"/resume/uploaded/{second['id']}",
        headers=authorization(token),
    )
    assert deleted.status_code == 200
    assert not second_path.exists()
    assert client.get("/resume/uploaded", headers=authorization(token)).json() is None


def test_resume_access_is_limited_to_owner_and_admin(client, create_user, tmp_path, monkeypatch):
    owner_id = create_user("owner@example.com", "student")
    owner_token = login(client, "owner@example.com")
    monkeypatch.setattr(resume_storage, "RESUME_DIRECTORY", tmp_path)
    created = upload(client, owner_token)
    resume_id = created.json()["resume"]["id"]

    create_user("other@example.com", "student")
    other_token = login(client, "other@example.com")
    assert client.get(
        f"/resume/uploaded/{resume_id}/download",
        headers=authorization(other_token),
    ).status_code == 404
    assert client.delete(
        f"/resume/uploaded/{resume_id}",
        headers=authorization(other_token),
    ).status_code == 404
    assert client.get(f"/admin/students/{owner_id}/resume").status_code == 401
    assert client.get(
        f"/admin/students/{owner_id}/resume",
        headers=authorization(other_token),
    ).status_code == 403

    create_user("admin@example.com", "admin")
    admin_token = login(client, "admin@example.com")
    admin_upload = upload(client, admin_token)
    assert admin_upload.status_code == 403
    admin_response = client.get(
        f"/admin/students/{owner_id}/resume",
        headers=authorization(admin_token),
    )
    assert admin_response.status_code == 200
    assert admin_response.content == b"%PDF-1.7\ntest document\n%%EOF\n"


def test_upload_rejects_invalid_extension_mime_signature_and_size(client, create_user):
    create_user("student@example.com", "student")
    token = login(client, "student@example.com")
    headers = authorization(token)

    bad_extension = client.post(
        "/resume/upload",
        headers=headers,
        files={"file": ("resume.txt", b"%PDF-1.7 test", "application/pdf")},
    )
    assert bad_extension.status_code == 400

    bad_mime = client.post(
        "/resume/upload",
        headers=headers,
        files={"file": ("resume.pdf", b"%PDF-1.7 test", "application/octet-stream")},
    )
    assert bad_mime.status_code == 415

    bad_signature = client.post(
        "/resume/upload",
        headers=headers,
        files={"file": ("resume.pdf", b"not a PDF", "application/pdf")},
    )
    assert bad_signature.status_code == 400

    missing_eof = client.post(
        "/resume/upload",
        headers=headers,
        files={"file": ("resume.pdf", b"%PDF-1.7 no end marker", "application/pdf")},
    )
    assert missing_eof.status_code == 400

    empty = client.post(
        "/resume/upload",
        headers=headers,
        files={"file": ("resume.pdf", b"", "application/pdf")},
    )
    assert empty.status_code == 400

    oversized = client.post(
        "/resume/upload",
        headers=headers,
        files={"file": ("resume.pdf", b"%PDF-" + b"x" * (5 * 1024 * 1024), "application/pdf")},
    )
    assert oversized.status_code == 413


def test_storage_failure_does_not_create_resume_record(client, create_user, monkeypatch):
    create_user("student@example.com", "student")
    token = login(client, "student@example.com")

    def fail_store(*_args):
        raise RuntimeError("Resume storage is temporarily unavailable.")

    monkeypatch.setattr(resume_file_routes, "store_resume", fail_store)
    response = upload(client, token)
    assert response.status_code == 503
    assert client.get("/resume/uploaded", headers=authorization(token)).json() is None


def test_failed_storage_delete_preserves_resume_record_and_file(
    client, create_user, tmp_path, monkeypatch
):
    create_user("student@example.com", "student")
    token = login(client, "student@example.com")
    monkeypatch.setattr(resume_storage, "RESUME_DIRECTORY", tmp_path)
    created = upload(client, token)
    resume = created.json()["resume"]

    def fail_delete(_location):
        raise RuntimeError("Resume storage is temporarily unavailable.")

    monkeypatch.setattr(resume_file_routes, "delete_stored_resume", fail_delete)
    response = client.delete(
        f"/resume/uploaded/{resume['id']}",
        headers=authorization(token),
    )
    assert response.status_code == 503
    assert client.get("/resume/uploaded", headers=authorization(token)).json()["id"] == resume["id"]
    assert len(list(tmp_path.glob("*.pdf"))) == 1


def test_database_delete_failure_restores_resume_file(
    client, create_user, tmp_path, monkeypatch
):
    create_user("student@example.com", "student")
    token = login(client, "student@example.com")
    monkeypatch.setattr(resume_storage, "RESUME_DIRECTORY", tmp_path)
    created = upload(client, token)
    resume = created.json()["resume"]
    stored_file = next(tmp_path.glob("*.pdf"))
    fail_next_commit = True

    def reject_commit_once(_session):
        nonlocal fail_next_commit
        if fail_next_commit:
            fail_next_commit = False
            raise RuntimeError("simulated database commit failure")

    event.listen(Session, "before_commit", reject_commit_once)
    try:
        with TestClient(client.app, raise_server_exceptions=False) as no_raise_client:
            response = no_raise_client.delete(
                f"/resume/uploaded/{resume['id']}",
                headers=authorization(token),
            )
    finally:
        event.remove(Session, "before_commit", reject_commit_once)

    assert response.status_code == 500
    assert client.get("/resume/uploaded", headers=authorization(token)).json()["id"] == resume["id"]
    assert stored_file.read_bytes() == b"%PDF-1.7\ntest document\n%%EOF\n"


def test_replacement_reports_previous_file_cleanup_failure(
    client, create_user, tmp_path, monkeypatch
):
    create_user("student@example.com", "student")
    token = login(client, "student@example.com")
    monkeypatch.setattr(resume_storage, "RESUME_DIRECTORY", tmp_path)
    first = upload(client, token, b"%PDF-1.7\nfirst\n%%EOF\n").json()["resume"]
    first_path = next(tmp_path.glob("*.pdf"))

    def fail_delete(_location):
        raise RuntimeError("Resume storage is temporarily unavailable.")

    monkeypatch.setattr(resume_file_routes, "delete_stored_resume", fail_delete)
    replaced = upload(client, token, b"%PDF-1.7\nnew file\n%%EOF\n")
    assert replaced.status_code == 201
    assert replaced.json()["cleanup_warning"] is True
    files = list(tmp_path.glob("*.pdf"))
    assert len(files) == 2
    assert first_path in files
    assert any(path != first_path for path in files)
