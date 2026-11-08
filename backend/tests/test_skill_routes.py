def login(client, email: str) -> str:
    response = client.post(
        "/auth/login",
        data={"username": email, "password": "TestPassword123!"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_students_can_only_list_or_delete_their_own_skills(client, create_user):
    create_user("owner@example.com", "student")
    create_user("other@example.com", "student")
    owner_headers = headers(login(client, "owner@example.com"))
    other_headers = headers(login(client, "other@example.com"))

    created = client.post(
        "/skill",
        headers=owner_headers,
        json={"skill_name": "Python"},
    )
    assert created.status_code == 200, created.text

    owner_skills = client.get("/skills", headers=owner_headers)
    assert [skill["skill_name"] for skill in owner_skills.json()] == ["Python"]
    assert client.get("/skills", headers=other_headers).json() == []

    skill_id = owner_skills.json()[0]["id"]
    assert client.delete(
        f"/skill/{skill_id}",
        headers=other_headers,
    ).status_code == 404
    assert client.get("/skills", headers=owner_headers).json()[0]["id"] == skill_id
