import json
import os
import time
from contextlib import contextmanager
import subprocess
import sys
from pathlib import Path

import pytest

from postgres_test_safety import (
    AUTH_FILE_ENV,
    AUTH_NONCE_ENV,
    AUTH_RUN_ID_ENV,
    DISPOSABLE_DATABASE_COMMENT,
    consume_run_authorization,
    create_verified_postgres_test_engine,
    issue_run_authorization,
    target_from_authorization,
    validate_container_inspection,
    validate_local_docker_context,
    validate_postgres_server_identity,
    validate_test_network,
)


RUN_ID = "a" * 32
NONCE = "b" * 64
CONTAINER_ID = "c" * 64
DATABASE = f"placementpilot_test_{RUN_ID}"
USERNAME = f"pp_test_{RUN_ID}"
DATABASE_URL = (
    f"postgresql+psycopg://{USERNAME}:unit-test-password@127.0.0.1:49152/{DATABASE}"
)


def issue_authorization(tmp_path, *, issued_at=None, run_id=RUN_ID, nonce=NONCE):
    authorization_path = tmp_path / "authorization.json"
    issue_run_authorization(
        authorization_path,
        run_id=run_id,
        nonce=nonce,
        parent_pid=1234,
        target_metadata={
            "database": DATABASE,
            "username": USERNAME,
            "host_port": 49152,
            "container_address": "172.20.0.2",
            "container_id": CONTAINER_ID,
        },
        issued_at=int(time.time()) if issued_at is None else issued_at,
    )
    return authorization_path


def authorization_environment(authorization_path, *, run_id=RUN_ID, nonce=NONCE):
    return {
        AUTH_FILE_ENV: str(authorization_path),
        AUTH_RUN_ID_ENV: run_id,
        AUTH_NONCE_ENV: nonce,
        "DATABASE_URL": DATABASE_URL,
    }


def valid_target(tmp_path):
    authorization_path = issue_authorization(tmp_path)
    authorization = consume_run_authorization(
        authorization_environment(authorization_path),
        parent_pid=1234,
    )
    return target_from_authorization(authorization, DATABASE_URL)


@pytest.mark.parametrize(
    "environment",
    [
        {},
        {AUTH_FILE_ENV: "grant.json"},
        {AUTH_FILE_ENV: "grant.json", AUTH_RUN_ID_ENV: RUN_ID},
    ],
)
def test_missing_or_partial_authorization_fails_before_engine_creation(
    environment,
):
    engine_calls = []

    def engine_factory(*args, **kwargs):
        engine_calls.append((args, kwargs))
        raise AssertionError("Engine creation must not precede authorization.")

    with pytest.raises(RuntimeError, match="authorization"):
        authorization = consume_run_authorization(environment, parent_pid=1234)
        target = target_from_authorization(
            authorization,
            environment.get("DATABASE_URL", ""),
        )
        create_verified_postgres_test_engine(target, engine_factory)
    assert engine_calls == []


def test_authorization_is_one_time(tmp_path):
    authorization_path = issue_authorization(tmp_path)
    environment = authorization_environment(authorization_path)
    consume_run_authorization(environment, parent_pid=1234)
    with pytest.raises(RuntimeError, match="missing or invalid"):
        consume_run_authorization(environment, parent_pid=1234)


@pytest.mark.parametrize(
    ("run_id", "nonce", "parent_pid", "issued_at"),
    [
        ("d" * 32, NONCE, 1234, None),
        (RUN_ID, "e" * 64, 1234, None),
        (RUN_ID, NONCE, 9876, None),
        (RUN_ID, NONCE, 1234, 1),
    ],
)
def test_wrong_run_nonce_parent_or_stale_grant_is_rejected(
    tmp_path, run_id, nonce, parent_pid, issued_at
):
    authorization_path = issue_authorization(
        tmp_path,
        run_id=RUN_ID,
        nonce=NONCE,
        issued_at=issued_at,
    )
    environment = authorization_environment(
        authorization_path,
        run_id=run_id,
        nonce=nonce,
    )
    with pytest.raises(RuntimeError, match="stale or does not match"):
        consume_run_authorization(
            environment,
            parent_pid=parent_pid,
            now=int(time.time()),
        )


@pytest.mark.parametrize(
    "database_url",
    [
        "not-a-url",
        "postgresql://test@127.0.0.1:49152/placementpilot_test_" + RUN_ID,
        "postgresql+psycopg://other@127.0.0.1:49152/" + DATABASE,
        "postgresql+psycopg://"
        + USERNAME
        + "@127.0.0.1:49152/placementpilot_test_wrong",
        DATABASE_URL + "?host=remote.example",
        DATABASE_URL.replace("127.0.0.1", "remote.example"),
    ],
)
def test_invalid_or_mismatched_target_url_is_rejected(tmp_path, database_url):
    authorization_path = issue_authorization(tmp_path)
    authorization = consume_run_authorization(
        authorization_environment(authorization_path),
        parent_pid=1234,
    )
    with pytest.raises(RuntimeError):
        target_from_authorization(authorization, database_url)


@pytest.mark.parametrize(
    ("context", "endpoint", "environment"),
    [
        ("default", "ssh://docker.example", {}),
        ("remote", "tcp://docker.example:2376", {}),
        ("default", "https://docker.example", {}),
        ("remote", "unix://docker.example/var/run/docker.sock", {}),
        ("remote", "unix://relative/docker.sock", {}),
        ("default", "npipe:////./pipe/docker_engine", {"DOCKER_HOST": "tcp://remote"}),
        ("default", "unix:///var/run/docker.sock", {"DOCKER_CONTEXT": "remote"}),
        ("", "unix:///var/run/docker.sock", {}),
        ("default", "", {}),
    ],
)
def test_remote_or_overridden_docker_context_is_rejected(
    context, endpoint, environment
):
    with pytest.raises(RuntimeError):
        validate_local_docker_context(context, endpoint, environment)


def test_platform_local_docker_endpoint_is_accepted():
    endpoint = (
        "npipe:////./pipe/docker_engine"
        if os.name == "nt"
        else "unix:///var/run/docker.sock"
    )
    validate_local_docker_context("local-test", endpoint, {})


def test_remote_named_pipe_docker_endpoint_is_rejected(monkeypatch):
    import postgres_test_safety

    monkeypatch.setattr(postgres_test_safety.os, "name", "nt")
    with pytest.raises(RuntimeError, match="local named-pipe"):
        validate_local_docker_context(
            "remote-pipe",
            "npipe:////remote-host/pipe/docker_engine",
            {},
        )


def valid_container_inspection(run_id=RUN_ID):
    return {
        "Config": {
            "Image": "postgres:18-alpine",
            "Labels": {"placementpilot.test.run": run_id},
        },
        "State": {"Running": True},
        "HostConfig": {
            "Binds": [],
            "Tmpfs": {"/var/lib/postgresql": "rw,nosuid,nodev,size=512m"},
        },
        "Mounts": [
            {"Type": "tmpfs", "Destination": "/var/lib/postgresql"}
        ],
        "NetworkSettings": {
            "Ports": {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "49152"}]},
            "Networks": {
                "placementpilot-pg-net-" + RUN_ID: {
                    "IPAddress": "172.20.0.2/16"
                }
            },
        },
    }


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["Mounts"].append({"Type": "volume"}),
        lambda value: value["HostConfig"].update(
            {"Binds": ["/host/data:/var/lib/postgresql/data"]}
        ),
        lambda value: value["NetworkSettings"]["Ports"]["5432/tcp"][0].update(
            {"HostIp": "0.0.0.0"}
        ),
        lambda value: value["Config"]["Labels"].update(
            {"placementpilot.test.run": "d" * 32}
        ),
        lambda value: value["NetworkSettings"].update(
            {"Networks": {"unexpected": {"IPAddress": "172.20.0.2/16"}}}
        ),
        lambda value: value["State"].update({"Running": False}),
        lambda value: value["Config"].update({"Image": "custom/postgres:18"}),
    ],
)
def test_container_mounts_remote_bindings_and_wrong_identity_are_rejected(mutate):
    inspection = valid_container_inspection()
    mutate(inspection)
    with pytest.raises(RuntimeError):
        validate_container_inspection(
            inspection, RUN_ID, "placementpilot-pg-net-" + RUN_ID
        )


def test_internal_test_network_is_required():
    validate_test_network(
        {
            "Driver": "bridge",
            "Internal": True,
            "Labels": {"placementpilot.test.run": RUN_ID},
        },
        RUN_ID,
    )
    for network in (
        {
            "Driver": "bridge",
            "Internal": False,
            "Labels": {"placementpilot.test.run": RUN_ID},
        },
        {
            "Driver": "overlay",
            "Internal": True,
            "Labels": {"placementpilot.test.run": RUN_ID},
        },
        {
            "Driver": "bridge",
            "Internal": True,
            "Labels": {"placementpilot.test.run": "d" * 32},
        },
    ):
        with pytest.raises(RuntimeError):
            validate_test_network(network, RUN_ID)


def valid_identity(target):
    return {
        "database_name": target.database,
        "role_name": target.username,
        "server_address": target.server_address,
        "server_port": 5432,
        "database_comment": DISPOSABLE_DATABASE_COMMENT,
        "database_owner": target.username,
        "schema_owner": target.username,
        "can_login": True,
        "role_membership_count": 0,
        "is_superuser": False,
        "can_create_database": False,
        "can_create_role": False,
        "can_replicate": False,
        "can_bypass_row_security": False,
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"database_name": "placementpilot"},
        {"role_name": "placementpilot_runtime"},
        {"database_owner": "postgres"},
        {"schema_owner": "postgres"},
        {"server_address": None},
        {"server_port": 5433},
        {"database_comment": "ordinary database"},
        {"is_superuser": True},
        {"can_create_database": True},
        {"can_create_role": True},
        {"can_replicate": True},
        {"can_bypass_row_security": True},
        {"role_membership_count": 1},
        {"can_login": False},
    ],
)
def test_wrong_database_identity_and_privileged_roles_are_rejected(
    tmp_path, changes
):
    target = valid_target(tmp_path)
    identity = valid_identity(target)
    identity.update(changes)
    with pytest.raises(RuntimeError):
        validate_postgres_server_identity(target, identity)


def test_missing_identity_information_is_rejected(tmp_path):
    target = valid_target(tmp_path)
    with pytest.raises(RuntimeError, match="identity"):
        validate_postgres_server_identity(target, None)
    with pytest.raises(RuntimeError, match="incomplete"):
        validate_postgres_server_identity(target, {"database_name": target.database})


def test_tunnel_or_proxy_url_without_provisioner_grant_cannot_authorize(
    tmp_path,
):
    tunnel_environment = {
        AUTH_FILE_ENV: "",
        AUTH_RUN_ID_ENV: RUN_ID,
        AUTH_NONCE_ENV: NONCE,
        "DATABASE_URL": DATABASE_URL,
    }
    with pytest.raises(RuntimeError, match="authorization"):
        consume_run_authorization(tunnel_environment, parent_pid=1234)


def test_loopback_server_address_is_only_defense_in_depth(tmp_path):
    target = valid_target(tmp_path)
    tunneled_identity = valid_identity(target)
    tunneled_identity["server_address"] = "127.0.0.1"
    with pytest.raises(RuntimeError, match="did not match"):
        validate_postgres_server_identity(target, tunneled_identity)

    wrong_database = dict(tunneled_identity, database_name="placementpilot")
    with pytest.raises(RuntimeError, match="did not match"):
        validate_postgres_server_identity(target, wrong_database)


def test_connection_verification_failure_disposes_engine(tmp_path):
    target = valid_target(tmp_path)

    class FakeResult:
        def mappings(self):
            return self

        def one_or_none(self):
            return None

    class FakeConnection:
        def execute(self, query):
            assert str(query).lstrip().upper().startswith("SELECT")
            return FakeResult()

    class FakeEngine:
        disposed = False

        @contextmanager
        def connect(self):
            yield FakeConnection()

        def dispose(self):
            self.disposed = True

    engine = FakeEngine()
    with pytest.raises(RuntimeError):
        create_verified_postgres_test_engine(
            target,
            engine_factory=lambda *args, **kwargs: engine,
        )
    assert engine.disposed


def test_authorization_json_does_not_store_password(tmp_path):
    authorization_path = issue_authorization(tmp_path)
    payload = json.loads(authorization_path.read_text(encoding="utf-8"))
    assert "password" not in payload
    assert "database_url" not in payload


def test_direct_pytest_setup_ignores_application_database_url():
    backend_dir = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    for name in (
        AUTH_FILE_ENV,
        AUTH_RUN_ID_ENV,
        AUTH_NONCE_ENV,
        "PLACEMENTPILOT_TEST_DATABASE_URL",
        "PLACEMENTPILOT_ALLOW_DESTRUCTIVE_POSTGRES_TESTS",
        "PLACEMENTPILOT_TEST_DATABASE_HOST",
        "PLACEMENTPILOT_TEST_DATABASE_PORT",
        "PLACEMENTPILOT_TEST_DATABASE_NAME",
        "PLACEMENTPILOT_TEST_DATABASE_USER",
    ):
        environment.pop(name, None)
    environment["DATABASE_URL"] = (
        "postgresql+psycopg://synthetic:synthetic@remote.invalid/production"
    )
    code = (
        "import sys; sys.path.insert(0, 'tests'); import conftest; "
        "import app.database as db; "
        "assert conftest.TEST_ENGINE.dialect.name == 'sqlite'; "
        "assert db.engine.dialect.name == 'sqlite'; "
        "assert not conftest.POSTGRES_TEST_AUTHORIZED"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=backend_dir,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, "Direct test setup did not stay isolated on SQLite."


def test_legacy_postgres_opt_in_is_rejected_without_provisioner():
    backend_dir = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    for name in (
        AUTH_FILE_ENV,
        AUTH_RUN_ID_ENV,
        AUTH_NONCE_ENV,
        "PLACEMENTPILOT_TEST_DATABASE_URL",
        "PLACEMENTPILOT_ALLOW_DESTRUCTIVE_POSTGRES_TESTS",
        "PLACEMENTPILOT_TEST_DATABASE_HOST",
        "PLACEMENTPILOT_TEST_DATABASE_PORT",
        "PLACEMENTPILOT_TEST_DATABASE_NAME",
        "PLACEMENTPILOT_TEST_DATABASE_USER",
    ):
        environment.pop(name, None)
    environment["PLACEMENTPILOT_TEST_DATABASE_URL"] = DATABASE_URL
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, 'tests'); import conftest",
        ],
        cwd=backend_dir,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode != 0
    assert "without provisioner authorization" in result.stderr
