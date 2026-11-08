def login(client, email: str, password: str = "TestPassword123!") -> str:
    response = client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_official_jobs(client, admin_headers):
    company_response = client.post(
        "/admin/companies",
        headers=admin_headers,
        json={"name": "Example Placement Partner"},
    )
    assert company_response.status_code == 200, company_response.text
    company_id = company_response.json()["company"]["id"]

    cycle_response = client.post(
        "/admin/cycles",
        headers=admin_headers,
        json={
            "name": "Test Placement Cycle",
            "academic_year": "2026-2027",
            "status": "Active",
        },
    )
    assert cycle_response.status_code == 200, cycle_response.text
    cycle_id = cycle_response.json()["cycle"]["id"]

    drive_response = client.post(
        "/admin/recruitment-drives",
        headers=admin_headers,
        json={
            "company_id": company_id,
            "placement_cycle_id": cycle_id,
            "name": "Official Test Hiring Drive",
            "status": "Published",
        },
    )
    assert drive_response.status_code == 200, drive_response.text
    published_drive_id = drive_response.json()["drive"]["id"]

    job_ids = []
    for role, location in (
        ("Software Engineer", "Remote"),
        ("Data Analyst", "Boston"),
    ):
        response = client.post(
            "/admin/jobs",
            headers=admin_headers,
            json={
                "recruitment_drive_id": published_drive_id,
                "role": role,
                "location": location,
                "package": "Confidential test fixture",
            },
        )
        assert response.status_code == 200, response.text
        job_ids.append(response.json()["job"]["id"])

    draft_response = client.post(
        "/admin/recruitment-drives",
        headers=admin_headers,
        json={
            "company_id": company_id,
            "placement_cycle_id": cycle_id,
            "name": "Unpublished Test Drive",
            "status": "Draft",
        },
    )
    assert draft_response.status_code == 200, draft_response.text
    draft_job = client.post(
        "/admin/jobs",
        headers=admin_headers,
        json={
            "recruitment_drive_id": draft_response.json()["drive"]["id"],
            "role": "Unpublished Test Role",
            "location": "Nowhere",
        },
    )
    assert draft_job.status_code == 200, draft_job.text

    second_drive = client.post(
        "/admin/recruitment-drives",
        headers=admin_headers,
        json={
            "company_id": company_id,
            "placement_cycle_id": cycle_id,
            "name": "Second Official Test Drive",
            "status": "Published",
        },
    )
    assert second_drive.status_code == 200, second_drive.text
    cross_drive_job = client.post(
        "/admin/jobs",
        headers=admin_headers,
        json={
            "recruitment_drive_id": second_drive.json()["drive"]["id"],
            "role": "Product Designer",
            "location": "Remote",
        },
    )
    assert cross_drive_job.status_code == 200, cross_drive_job.text
    job_ids.append(cross_drive_job.json()["job"]["id"])

    return job_ids


def test_official_jobs_search_save_apply_and_withdraw_workflow(
    client, create_user, monkeypatch
):
    create_user("admin@example.com", "admin")
    admin_headers = authorization(login(client, "admin@example.com"))
    student_id = create_user("student@example.com", "student")
    student_headers = authorization(login(client, "student@example.com"))

    job_ids = create_official_jobs(client, admin_headers)

    unauthorized_job = client.post(
        "/admin/jobs",
        headers=student_headers,
        json={"recruitment_drive_id": 1, "role": "Unauthorized Role"},
    )
    assert unauthorized_job.status_code == 403

    first_page = client.get(
        "/student/jobs?page=1&page_size=1",
        headers=student_headers,
    )
    assert first_page.status_code == 200
    assert first_page.json()["pagination"] == {
        "page": 1,
        "page_size": 1,
        "total_items": 3,
        "total_pages": 3,
        "has_next": True,
        "has_previous": False,
    }
    assert first_page.json()["items"][0]["role"] == "Product Designer"
    assert first_page.json()["items"][0]["eligibility"]["eligible"] is True

    searched = client.get(
        "/student/jobs?search=Engineer&location=Remote",
        headers=student_headers,
    )
    assert [item["role"] for item in searched.json()["items"]] == ["Software Engineer"]
    assert client.get(
        "/student/jobs?search=Unpublished",
        headers=student_headers,
    ).json()["items"] == []

    saved = client.post(
        f"/student/saved-jobs/{job_ids[0]}",
        headers=student_headers,
    )
    assert saved.status_code == 201
    assert client.post(
        f"/student/saved-jobs/{job_ids[0]}",
        headers=student_headers,
    ).status_code == 200
    assert len(client.get("/student/saved-jobs", headers=student_headers).json()["items"]) == 1
    assert client.delete(
        f"/student/saved-jobs/{job_ids[0]}",
        headers=student_headers,
    ).status_code == 200
    assert client.get("/student/saved-jobs", headers=student_headers).json()["items"] == []

    application = client.post(
        "/apply",
        headers=student_headers,
        json={"job_id": job_ids[0]},
    )
    assert application.status_code == 200, application.text
    application_id = application.json()["application_id"]
    assert client.post(
        "/apply",
        headers=student_headers,
        json={"job_id": job_ids[0]},
    ).status_code == 400

    history = client.get("/applications", headers=student_headers)
    assert history.status_code == 200
    assert history.json()[0]["status"] == "Applied"

    withdrawn = client.delete(
        f"/application/{application_id}",
        headers=student_headers,
    )
    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "Withdrawn"
    reapplied = client.post(
        "/apply",
        headers=student_headers,
        json={"job_id": job_ids[0]},
    )
    assert reapplied.status_code == 200

    active_limit = client.post(
        "/apply",
        headers=student_headers,
        json={"job_id": job_ids[1]},
    )
    assert active_limit.status_code == 400
    assert "another position in this company recruitment drive" in active_limit.json()["detail"]

    cycle_limit = client.post(
        "/apply",
        headers=student_headers,
        json={"job_id": job_ids[2]},
    )
    assert cycle_limit.status_code == 400
    assert "only 1 active application" in cycle_limit.json()["detail"]

    application_id = reapplied.json()["application_id"]
    selected = client.put(
        f"/admin/applications/{application_id}/status",
        headers=admin_headers,
        json={"status": "Selected"},
    )
    assert selected.status_code == 200, selected.text
    released = client.put(
        f"/admin/applications/{application_id}/status",
        headers=admin_headers,
        json={"status": "Offer Released"},
    )
    assert released.status_code == 200, released.text
    from app.routes import application_routes

    original_lock = application_routes.lock_student_for_application_updates
    locked_user_ids = []

    def tracking_lock(db, user_id):
        locked_user_ids.append(user_id)
        return original_lock(db, user_id)

    monkeypatch.setattr(
        application_routes,
        "lock_student_for_application_updates",
        tracking_lock,
    )
    accepted = client.post(
        f"/application/{application_id}/offer-response",
        headers=student_headers,
        json={"decision": "accept"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "Offer Accepted"
    assert locked_user_ids == [student_id]

    locked_application = client.post(
        "/apply",
        headers=student_headers,
        json={"job_id": job_ids[2]},
    )
    assert locked_application.status_code == 400
    assert "already accepted an offer" in locked_application.json()["detail"]

    reopened_offer = client.put(
        f"/admin/applications/{application_id}/status",
        headers=admin_headers,
        json={"status": "Selected"},
    )
    assert reopened_offer.status_code == 409

    invalid_status = client.put(
        f"/admin/applications/{application_id}/status",
        headers=admin_headers,
        json={"status": "Withdrawn"},
    )
    assert invalid_status.status_code == 400


def test_student_profiles_and_applications_are_scoped_to_the_owner(client, create_user):
    create_user("admin@example.com", "admin")
    admin_headers = authorization(login(client, "admin@example.com"))
    create_user("owner@example.com", "student")
    owner_headers = authorization(login(client, "owner@example.com"))
    create_user("other@example.com", "student")
    other_headers = authorization(login(client, "other@example.com"))
    job_ids = create_official_jobs(client, admin_headers)

    profile = client.post(
        "/profile",
        headers=owner_headers,
        json={
            "college": "Isolated Test College",
            "branch": "Computing",
            "year": "Final",
            "linkedin": "",
            "github": "",
            "skills": "",
        },
    )
    assert profile.status_code == 200, profile.text
    assert client.get("/profile", headers=other_headers).status_code == 404

    application = client.post(
        "/apply",
        headers=owner_headers,
        json={"job_id": job_ids[0]},
    )
    assert application.status_code == 200, application.text
    application_id = application.json()["application_id"]
    assert client.get("/applications", headers=other_headers).json() == []
    assert client.delete(
        f"/application/{application_id}",
        headers=other_headers,
    ).status_code == 404


def test_admin_round_results_progress_to_next_round(client, create_user):
    create_user("admin@example.com", "admin")
    admin_headers = authorization(login(client, "admin@example.com"))
    create_user("student@example.com", "student")
    student_headers = authorization(login(client, "student@example.com"))

    job_ids = create_official_jobs(client, admin_headers)
    drives = client.get("/admin/recruitment-drives", headers=admin_headers).json()
    drive_id = next(
        drive["id"]
        for drive in drives
        if drive["name"] == "Official Test Hiring Drive"
    )
    application = client.post(
        "/apply",
        headers=student_headers,
        json={"job_id": job_ids[0]},
    )
    assert application.status_code == 200
    application_id = application.json()["application_id"]

    first_round_response = client.post(
        f"/admin/recruitment-drives/{drive_id}/rounds",
        headers=admin_headers,
        json={
            "name": "First Technical Round",
            "sequence": 1,
            "scheduled_at": "2099-01-10T10:00:00",
            "venue": "Online",
            "status": "Scheduled",
        },
    )
    assert first_round_response.status_code == 200, first_round_response.text
    first_round_id = first_round_response.json()["round"]["id"]
    assignments = client.post(
        f"/admin/rounds/{first_round_id}/assign-candidates",
        headers=admin_headers,
    )
    assert assignments.status_code == 200
    assert assignments.json()["assigned_count"] == 1

    result = client.put(
        f"/admin/rounds/{first_round_id}/candidates/{application_id}/result",
        headers=admin_headers,
        json={
            "attendance": "Present",
            "result": "Pass",
            "score": 92.5,
            "feedback": "Passed test fixture evaluation",
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["result"] == "Pass"

    second_round_response = client.post(
        f"/admin/recruitment-drives/{drive_id}/rounds",
        headers=admin_headers,
        json={
            "name": "Final Interview",
            "sequence": 2,
            "scheduled_at": "2099-01-20T10:00:00",
            "status": "Scheduled",
        },
    )
    assert second_round_response.status_code == 200, second_round_response.text
    second_round_id = second_round_response.json()["round"]["id"]
    progressed = client.post(
        f"/admin/rounds/{second_round_id}/assign-candidates",
        headers=admin_headers,
    )
    assert progressed.status_code == 200
    assert progressed.json()["assigned_count"] == 1
    assert progressed.json()["progression_rule"] == "Candidates who passed round 1"

    student_rounds = client.get("/student/rounds", headers=student_headers)
    assert student_rounds.status_code == 200
    assert [item["round_sequence"] for item in student_rounds.json()] == [1, 2]
    assert student_rounds.json()[0]["result"] == "Pass"
    dashboard = client.get("/student/dashboard", headers=student_headers)
    assert dashboard.status_code == 200
    assert len(dashboard.json()["upcoming_rounds"]) == 2


def test_job_eligibility_is_enforced_by_the_api(client, create_user):
    create_user("admin@example.com", "admin")
    admin_headers = authorization(login(client, "admin@example.com"))
    create_user("student@example.com", "student")
    student_headers = authorization(login(client, "student@example.com"))
    job_ids = create_official_jobs(client, admin_headers)

    criteria = {
        "eligible_courses": ["BSc Computer Science"],
        "eligible_branches": ["Computer Science"],
        "graduation_years": [2026],
        "min_cgpa": 3.5,
        "max_active_backlogs": 0,
    }
    configured = client.post(
        f"/admin/jobs/{job_ids[0]}/eligibility",
        headers=admin_headers,
        json=criteria,
    )
    assert configured.status_code == 201, configured.text

    discovery = client.get(
        "/student/jobs?search=Engineer",
        headers=student_headers,
    )
    assert discovery.json()["items"][0]["eligibility"]["eligible"] is False
    rejected = client.post(
        "/apply",
        headers=student_headers,
        json={"job_id": job_ids[0]},
    )
    assert rejected.status_code == 403

    profile = client.post(
        "/profile",
        headers=student_headers,
        json={
            "college": "Test University",
            "branch": "Computer Science",
            "year": "2022-2026",
            "linkedin": "",
            "github": "",
            "skills": "Python",
        },
    )
    assert profile.status_code == 200, profile.text
    education = client.post(
        "/education",
        headers=student_headers,
        json={
            "degree": "BSc Computer Science",
            "college": "Test University",
            "year": "2022-2026",
            "cgpa": "3.8",
            "graduation_year": 2026,
            "active_backlogs": 0,
        },
    )
    assert education.status_code == 200, education.text

    now_eligible = client.get(
        "/student/jobs?search=Engineer",
        headers=student_headers,
    )
    assert now_eligible.json()["items"][0]["eligibility"]["eligible"] is True
    assert client.post(
        "/apply",
        headers=student_headers,
        json={"job_id": job_ids[0]},
    ).status_code == 200
