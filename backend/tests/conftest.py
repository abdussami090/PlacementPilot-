"""Use isolated SQLite by default; PostgreSQL requires its one-run provisioner."""

import os

from postgres_test_safety import (
    AUTH_FILE_ENV,
    AUTH_NONCE_ENV,
    AUTH_RUN_ID_ENV,
    LEGACY_POSTGRES_SETTINGS,
    consume_run_authorization,
    create_verified_postgres_test_engine,
    target_from_authorization,
)

os.environ["ENVIRONMENT"] = "test"
os.environ["JWT_SECRET_KEY"] = "test-only-secret-key-not-used-in-production-123456789"
os.environ["RESUME_STORAGE_BACKEND"] = "local"

_authorization_requested = any(
    os.environ.get(name, "").strip()
    for name in (AUTH_FILE_ENV, AUTH_RUN_ID_ENV, AUTH_NONCE_ENV)
)
_legacy_postgres_configuration = any(
    os.environ.get(name, "").strip() for name in LEGACY_POSTGRES_SETTINGS
)

if _authorization_requested:
    if not all(
        os.environ.get(name, "").strip()
        for name in (AUTH_FILE_ENV, AUTH_RUN_ID_ENV, AUTH_NONCE_ENV)
    ):
        raise RuntimeError("PostgreSQL test authorization is incomplete.")
    if _legacy_postgres_configuration:
        raise RuntimeError(
            "Legacy PostgreSQL test settings are forbidden; use the isolated provisioner."
        )
    _authorization = consume_run_authorization()
    POSTGRES_TEST_TARGET = target_from_authorization(
        _authorization,
        os.environ.get("DATABASE_URL", ""),
    )
    os.environ["DATABASE_URL"] = POSTGRES_TEST_TARGET.url.render_as_string(
        hide_password=False
    )
    POSTGRES_TEST_AUTHORIZED = True
else:
    if _legacy_postgres_configuration:
        raise RuntimeError(
            "PostgreSQL test settings were found without provisioner authorization."
        )
    POSTGRES_TEST_TARGET = None
    POSTGRES_TEST_AUTHORIZED = False
    os.environ["DATABASE_URL"] = "sqlite://"

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

if POSTGRES_TEST_AUTHORIZED:
    TEST_ENGINE = create_verified_postgres_test_engine(POSTGRES_TEST_TARGET)
else:
    TEST_ENGINE = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

from app.main import app
from app.database import Base
from app import model_registry  # noqa: F401 - register all database models

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _override_all_get_db_dependencies(dependant):
    if getattr(getattr(dependant, "call", None), "__name__", "") == "get_db":
        app.dependency_overrides[dependant.call] = override_get_db
    for child in getattr(dependant, "dependencies", []):
        _override_all_get_db_dependencies(child)


for route in app.routes:
    if isinstance(route, APIRoute):
        _override_all_get_db_dependencies(route.dependant)


@pytest.fixture(autouse=True)
def reset_test_database():
    Base.metadata.drop_all(bind=TEST_ENGINE)
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def create_user():
    def factory(email: str, role: str, password: str = "TestPassword123!"):
        from app.models import User
        from app.security import hash_password

        db = TestingSessionLocal()
        try:
            user = User(
                name="Test User",
                email=email,
                password=hash_password(password),
                role=role,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return user.id
        finally:
            db.close()

    return factory
