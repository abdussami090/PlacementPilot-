from fastapi.routing import APIRoute

from app.dependencies import admin_required
from app.main import app


def login(client, email: str, password: str = "TestPassword123!") -> str:
    response = client.post("/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]



def test_admin_route_requires_authentication(client):
    response = client.get("/admin-test")
    assert response.status_code == 401


def test_student_cannot_access_admin_route(client, create_user):
    create_user("student@example.com", "student")
    token = login(client, "student@example.com")
    response = client.get("/admin-test", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_student_cannot_access_admin_api_families(client, create_user):
    create_user("student@example.com", "student")
    token = login(client, "student@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    paths = (
        "/admin/users",
        "/admin/companies",
        "/admin/cycles",
        "/admin/recruitment-drives",
        "/admin/jobs",
        "/admin/applications",
        "/admin/dashboard/overview",
        "/admin/jobs/1/eligibility",
        "/admin/recruitment-drives/1/rounds",
        "/admin/rounds/1/candidates",
        "/admin/students/1/resume",
    )

    for path in paths:
        response = client.get(path, headers=headers)
        assert response.status_code == 403, (path, response.text)


def test_every_admin_route_declares_admin_authorization():
    def contains_admin_dependency(dependant):
        return dependant.call is admin_required or any(
            contains_admin_dependency(child)
            for child in dependant.dependencies
        )

    def iter_routes(routes, prefix=""):
        for route in routes:
            if isinstance(route, APIRoute):
                yield prefix + route.path, route
            elif getattr(route, "original_router", None) is not None:
                context = getattr(route, "include_context", None)
                child_prefix = getattr(context, "prefix", "")
                yield from iter_routes(
                    route.original_router.routes,
                    prefix + child_prefix,
                )

    admin_routes = [
        (path, route)
        for path, route in iter_routes(app.routes)
        if path.startswith("/admin/")
    ]
    assert admin_routes
    unprotected = [
        f"{','.join(sorted(route.methods or []))} {path}"
        for path, route in admin_routes
        if not contains_admin_dependency(route.dependant)
    ]
    assert not unprotected, f"Admin routes without admin_required: {unprotected}"


def test_admin_can_access_admin_route(client, create_user):
    create_user("admin@example.com", "admin")
    token = login(client, "admin@example.com")
    response = client.get("/admin-test", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome Admin"}


def test_invalid_token_is_401_on_profile_routes(client):
    headers = {"Authorization": "Bearer invalid-token"}
    for path in ("/profile", "/skills", "/resume"):
        response = client.get(path, headers=headers)
        assert response.status_code == 401, (path, response.text)


def test_admin_is_not_allowed_to_use_student_profile_routes(client, create_user):
    create_user("admin@example.com", "admin")
    token = login(client, "admin@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    for path in ("/profile", "/skills", "/resume"):
        response = client.get(path, headers=headers)
        assert response.status_code == 403, (path, response.text)


def test_signup_rejects_short_password(client):
    response = client.post("/auth/signup", json={
        "name": "New Student",
        "email": "new@example.com",
        "password": "short",
    })
    assert response.status_code == 422


def test_login_uses_generic_invalid_credentials_message(client):
    response = client.post("/auth/login", data={
        "username": "unknown@example.com",
        "password": "WrongPassword123!",
    })
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_cors_preflight_allows_local_frontend(client):
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "GET" in response.headers["access-control-allow-methods"]
    assert "access-control-allow-credentials" not in response.headers
