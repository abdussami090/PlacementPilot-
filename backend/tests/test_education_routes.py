def login(client, email: str, password: str = "TestPassword123!") -> str:
    response = client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def education_payload(**overrides) -> dict:
    return {
        "degree": "BSc Computer Science",
        "college": "Example University",
        "year": "2022-2026",
        "cgpa": "3.8",
        "graduation_year": 2026,
        "active_backlogs": 0,
        **overrides,
    }


def test_student_can_manage_education(client, create_user):
    student_id = create_user("student@example.com", "student")
    headers = authorization(login(client, "student@example.com"))

    created = client.post("/education", json=education_payload(), headers=headers)
    assert created.status_code == 200
    education_id = created.json()["education_id"]

    listed = client.get("/education", headers=headers)
    assert listed.status_code == 200
    assert listed.json() == [
        {
            "id": education_id,
            "user_id": student_id,
            "degree": "BSc Computer Science",
            "college": "Example University",
            "year": "2022-2026",
            "cgpa": "3.8",
            "graduation_year": 2026,
            "active_backlogs": 0,
        }
    ]

    updated = client.put(
        f"/education/{education_id}",
        json=education_payload(degree="MSc Computer Science", cgpa="3.9"),
        headers=headers,
    )
    assert updated.status_code == 200
    assert client.get("/education", headers=headers).json()[0]["degree"] == "MSc Computer Science"

    deleted = client.delete(f"/education/{education_id}", headers=headers)
    assert deleted.status_code == 200
    assert client.get("/education", headers=headers).json() == []


def test_student_cannot_access_another_students_education(client, create_user):
    create_user("owner@example.com", "student")
    owner_headers = authorization(login(client, "owner@example.com"))
    created = client.post("/education", json=education_payload(), headers=owner_headers)
    education_id = created.json()["education_id"]

    create_user("other@example.com", "student")
    other_headers = authorization(login(client, "other@example.com"))

    assert client.get("/education", headers=other_headers).json() == []
    assert client.put(
        f"/education/{education_id}",
        json=education_payload(degree="Unauthorized update"),
        headers=other_headers,
    ).status_code == 404
    assert client.delete(
        f"/education/{education_id}",
        headers=other_headers,
    ).status_code == 404
    assert client.get("/education", headers=owner_headers).json()[0]["degree"] == "BSc Computer Science"


def test_admin_cannot_manage_student_education(client, create_user):
    create_user("admin@example.com", "admin")
    headers = authorization(login(client, "admin@example.com"))

    assert client.get("/education", headers=headers).status_code == 403
    assert client.post(
        "/education",
        json=education_payload(),
        headers=headers,
    ).status_code == 403


def test_education_validates_academic_constraints(client, create_user):
    create_user("student@example.com", "student")
    headers = authorization(login(client, "student@example.com"))

    for payload in (
        education_payload(graduation_year=2019),
        education_payload(active_backlogs=-1),
        education_payload(active_backlogs=51),
    ):
        response = client.post("/education", json=payload, headers=headers)
        assert response.status_code == 422
