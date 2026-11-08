from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy.exc import IntegrityError

from app.company import Company
from app.models import User
from app.security import hash_password
from conftest import POSTGRES_TEST_AUTHORIZED, TestingSessionLocal


pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_AUTHORIZED,
    reason="Run through scripts.run_postgres_integration_tests to provision an isolated database.",
)


def _login(client, email: str) -> str:
    response = client.post(
        "/auth/login",
        data={"username": email, "password": "TestPassword123!"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_two_open_jobs_in_cycle(client, admin_headers):
    company = client.post(
        "/admin/companies",
        headers=admin_headers,
        json={"name": "Isolated PG Test Partner"},
    )
    assert company.status_code == 200, company.text

    cycle = client.post(
        "/admin/cycles",
        headers=admin_headers,
        json={"name": "Isolated PG Test Cycle", "academic_year": "2098-2099", "status": "Active"},
    )
    assert cycle.status_code == 200, cycle.text
    cycle_id = cycle.json()["cycle"]["id"]

    policy = client.post(
        f"/admin/cycles/{cycle_id}/policy",
        headers=admin_headers,
        json={"max_active_applications": 1},
    )
    assert policy.status_code == 200, policy.text

    jobs = []
    for number in (1, 2):
        drive = client.post(
            "/admin/recruitment-drives",
            headers=admin_headers,
            json={
                "company_id": company.json()["company"]["id"],
                "placement_cycle_id": cycle_id,
                "name": f"Isolated PG Test Drive {number}",
                "status": "Published",
            },
        )
        assert drive.status_code == 200, drive.text
        job = client.post(
            "/admin/jobs",
            headers=admin_headers,
            json={
                "recruitment_drive_id": drive.json()["drive"]["id"],
                "role": f"Isolated Test Role {number}",
                "status": "Open",
            },
        )
        assert job.status_code == 200, job.text
        jobs.append(job.json()["job"]["id"])
    return jobs


def test_postgresql_enforces_unique_and_foreign_key_constraints_and_rollback(
    create_user,
):
    user_id = create_user("pg-constraint@example.test", "student")
    db = TestingSessionLocal()
    try:
        db.add(
            User(
                name="Duplicate Test User",
                email="pg-constraint@example.test",
                password=hash_password("TestPassword123!"),
                role="student",
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        db.add(Company(name="Invalid FK test", created_by=user_id + 1000000))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        rolled_back = User(
            name="Rolled Back Test User",
            email="rolled-back@example.test",
            password=hash_password("TestPassword123!"),
            role="student",
        )
        db.add(rolled_back)
        db.flush()
        db.rollback()
    finally:
        db.close()

    verification = TestingSessionLocal()
    try:
        assert verification.query(User).filter_by(email="pg-constraint@example.test").count() == 1
        assert verification.query(User).filter_by(email="rolled-back@example.test").count() == 0
    finally:
        verification.close()


def test_postgresql_concurrent_applications_respect_cycle_limit(
    client, create_user
):
    create_user("pg-admin@example.test", "admin")
    admin_headers = _headers(_login(client, "pg-admin@example.test"))
    create_user("pg-student@example.test", "student")
    student_headers = _headers(_login(client, "pg-student@example.test"))
    jobs = _make_two_open_jobs_in_cycle(client, admin_headers)
    barrier = Barrier(2)

    def apply(job_id):
        barrier.wait(timeout=10)
        return client.post("/apply", headers=student_headers, json={"job_id": job_id})

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(apply, jobs))

    assert sorted(response.status_code for response in responses) == [200, 400]


def test_postgresql_concurrent_offer_acceptance_is_serialized(client, create_user):
    create_user("offer-admin@example.test", "admin")
    admin_headers = _headers(_login(client, "offer-admin@example.test"))
    create_user("offer-student@example.test", "student")
    student_headers = _headers(_login(client, "offer-student@example.test"))
    jobs = _make_two_open_jobs_in_cycle(client, admin_headers)

    application = client.post(
        "/apply",
        headers=student_headers,
        json={"job_id": jobs[0]},
    )
    assert application.status_code == 200, application.text
    application_id = application.json()["application_id"]

    for status in ("Selected", "Offer Released"):
        changed = client.put(
            f"/admin/applications/{application_id}/status",
            headers=admin_headers,
            json={"status": status},
        )
        assert changed.status_code == 200, changed.text

    barrier = Barrier(2)

    def accept_offer():
        barrier.wait(timeout=10)
        return client.post(
            f"/application/{application_id}/offer-response",
            headers=student_headers,
            json={"decision": "accept"},
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: accept_offer(), range(2)))

    assert sorted(response.status_code for response in responses) == [200, 409]
    with TestingSessionLocal() as db:
        stored = db.query(User).filter_by(email="offer-student@example.test").one()
        application_record = next(
            application
            for application in stored.applications
            if application.id == application_id
        )
        assert application_record.status == "Offer Accepted"
