"""Provision and destroy a local, ephemeral PostgreSQL integration-test server."""

import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
TESTS_DIR = BACKEND_DIR / "tests"
sys.path.insert(0, str(TESTS_DIR))

from postgres_test_safety import (  # noqa: E402
    AUTH_FILE_ENV,
    AUTH_NONCE_ENV,
    AUTH_RUN_ID_ENV,
    DISPOSABLE_DATABASE_COMMENT,
    issue_run_authorization,
    validate_container_inspection,
    validate_local_docker_context,
    validate_test_network,
)


def _run(command: list[str], *, timeout: int = 30, input_text: str | None = None):
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {command[0]} "
            f"{' '.join(command[1:3])}; details suppressed."
        )
    return result.stdout.strip()


def _docker_context(docker: str) -> None:
    if os.environ.get("DOCKER_HOST", "").strip() or os.environ.get(
        "DOCKER_CONTEXT", ""
    ).strip():
        raise RuntimeError("DOCKER_HOST and DOCKER_CONTEXT overrides are not allowed.")
    context_name = _run([docker, "context", "show"])
    endpoint_info = _run(
        [docker, "context", "inspect", "--format", "{{json .Endpoints.docker}}"]
    )
    try:
        endpoint = json.loads(endpoint_info)["Host"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RuntimeError("Could not verify the active Docker endpoint.") from exc
    validate_local_docker_context(context_name, endpoint)
    _run([docker, "info", "--format", "{{.ServerVersion}}"], timeout=20)


def _wait_until_ready(docker: str, container_id: str, username: str, database: str):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        result = subprocess.run(
            [
                docker,
                "exec",
                container_id,
                "pg_isready",
                "--username",
                username,
                "--dbname",
                database,
            ],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(1)
    raise RuntimeError("Disposable PostgreSQL container did not become ready.")


def _inspect_container(docker: str, container_id: str) -> dict:
    inspection = json.loads(_run([docker, "inspect", container_id]))
    if not isinstance(inspection, list) or len(inspection) != 1:
        raise RuntimeError("Could not verify the disposable PostgreSQL container.")
    return inspection[0]


def _inspect_network(docker: str, network_id: str) -> dict:
    inspection = json.loads(_run([docker, "network", "inspect", network_id]))
    if not isinstance(inspection, list) or len(inspection) != 1:
        raise RuntimeError("Could not verify the isolated test network.")
    return inspection[0]


def _container_is_present(docker: str, container_id: str) -> bool | None:
    try:
        result = subprocess.run(
            [docker, "inspect", container_id],
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
    except subprocess.SubprocessError:
        return None
    if result.returncode == 0:
        return True
    if "no such object" in result.stderr.lower() or "not found" in result.stderr.lower():
        return False
    return None


def _network_is_present(docker: str, network: str) -> bool | None:
    try:
        result = subprocess.run(
            [docker, "network", "inspect", network],
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
    except subprocess.SubprocessError:
        return None
    if result.returncode == 0:
        return True
    if "no such network" in result.stderr.lower() or "not found" in result.stderr.lower():
        return False
    return None


def _configure_test_role(
    docker: str,
    container_id: str,
    bootstrap_user: str,
    database: str,
    test_user: str,
    test_password: str,
) -> None:
    escaped_password = test_password.replace("'", "''")
    sql = "\n".join(
        [
            f"CREATE ROLE {test_user} LOGIN PASSWORD '{escaped_password}';",
            f"ALTER DATABASE {database} OWNER TO {test_user};",
            f"ALTER SCHEMA public OWNER TO {test_user};",
            f"COMMENT ON DATABASE {database} IS '{DISPOSABLE_DATABASE_COMMENT}';",
        ]
    )
    _run(
        [
            docker,
            "exec",
            "-i",
            container_id,
            "psql",
            "--set",
            "ON_ERROR_STOP=1",
            "--username",
            bootstrap_user,
            "--dbname",
            database,
        ],
        input_text=sql,
    )


def _test_database_url(host_port: int, database: str, username: str, password: str):
    from sqlalchemy.engine import URL

    url = URL.create(
        "postgresql+psycopg",
        username=username,
        password=password,
        host="127.0.0.1",
        port=host_port,
        database=database,
    )
    return url.render_as_string(hide_password=False)


def main() -> int:
    docker = shutil.which("docker")
    if docker is None:
        print(
            "PostgreSQL integration tests were not run: Docker is unavailable. "
            "They remain disabled for direct pytest runs."
        )
        return 2

    try:
        _docker_context(docker)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"PostgreSQL integration tests were not run: {exc}")
        return 2

    run_id = uuid.uuid4().hex
    suffix = run_id
    database = f"placementpilot_test_{suffix}"
    bootstrap_user = f"pp_bootstrap_{suffix}"
    test_user = f"pp_test_{suffix}"
    bootstrap_password = secrets.token_urlsafe(36)
    test_password = secrets.token_urlsafe(36)
    container_name = f"placementpilot-pg-test-{suffix}"
    network_name = f"placementpilot-pg-net-{suffix}"
    environment_file = None
    container_id = None
    network_id = None
    container_attempted = False
    network_attempted = False
    auth_directory = None

    try:
        with tempfile.TemporaryDirectory(prefix="placementpilot-pg-test-") as temp_dir:
            temp_path = Path(temp_dir)
            environment_file = temp_path / "postgres.env"
            environment_file.write_text(
                "\n".join(
                    [
                        f"POSTGRES_USER={bootstrap_user}",
                        f"POSTGRES_PASSWORD={bootstrap_password}",
                        f"POSTGRES_DB={database}",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            if os.name != "nt":
                environment_file.chmod(0o600)

            network_attempted = True
            network_id = _run(
                [
                    docker,
                    "network",
                    "create",
                    "--driver",
                    "bridge",
                    "--internal",
                    "--label",
                    f"placementpilot.test.run={run_id}",
                    network_name,
                ]
            )
            validate_test_network(_inspect_network(docker, network_id), run_id)

            container_attempted = True
            container_id = _run(
                [
                    docker,
                    "run",
                    "--detach",
                    "--rm",
                    "--name",
                    container_name,
                    "--network",
                    network_name,
                    "--label",
                    f"placementpilot.test.run={run_id}",
                    "--env-file",
                    str(environment_file),
                    "--publish",
                    "127.0.0.1::5432",
                    "--tmpfs",
                    "/var/lib/postgresql:rw,nosuid,nodev,size=512m",
                    "postgres:18-alpine",
                ],
                timeout=60,
            )
            if len(container_id) != 64:
                raise RuntimeError("Docker returned an invalid container identity.")
            environment_file.unlink()
            environment_file = None

            inspection = _inspect_container(docker, container_id)
            host_port, container_address = validate_container_inspection(
                inspection, run_id, network_name
            )
            _wait_until_ready(docker, container_id, bootstrap_user, database)
            _configure_test_role(
                docker,
                container_id,
                bootstrap_user,
                database,
                test_user,
                test_password,
            )

            database_url = _test_database_url(
                host_port, database, test_user, test_password
            )
            auth_directory = Path(
                tempfile.mkdtemp(prefix="placementpilot-pg-auth-")
            )
            authorization_path = auth_directory / "authorization.json"
            nonce = secrets.token_hex(32)
            issue_run_authorization(
                authorization_path,
                run_id=run_id,
                nonce=nonce,
                parent_pid=os.getpid(),
                target_metadata={
                    "database": database,
                    "username": test_user,
                    "host_port": host_port,
                    "container_address": container_address,
                    "container_id": container_id,
                },
            )

            child_environment = os.environ.copy()
            for variable in (
                "DATABASE_URL",
                *(
                    "PLACEMENTPILOT_TEST_DATABASE_URL",
                    "PLACEMENTPILOT_ALLOW_DESTRUCTIVE_POSTGRES_TESTS",
                    "PLACEMENTPILOT_TEST_DATABASE_HOST",
                    "PLACEMENTPILOT_TEST_DATABASE_PORT",
                    "PLACEMENTPILOT_TEST_DATABASE_NAME",
                    "PLACEMENTPILOT_TEST_DATABASE_USER",
                ),
            ):
                child_environment.pop(variable, None)
            child_environment.update(
                {
                    "DATABASE_URL": database_url,
                    AUTH_FILE_ENV: str(authorization_path),
                    AUTH_RUN_ID_ENV: run_id,
                    AUTH_NONCE_ENV: nonce,
                }
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    "tests/test_postgresql_integration.py",
                ],
                cwd=BACKEND_DIR,
                env=child_environment,
                check=False,
            )
            return result.returncode
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"PostgreSQL integration tests were not run or failed: {exc}")
        return 1
    finally:
        if environment_file is not None:
            environment_file.unlink(missing_ok=True)
        if auth_directory is not None:
            shutil.rmtree(auth_directory, ignore_errors=True)
        cleanup_errors = []
        if container_attempted:
            container_reference = container_id or container_name
            try:
                stop_result = subprocess.run(
                    [docker, "stop", "--time", "10", container_reference],
                    text=True,
                    capture_output=True,
                    timeout=20,
                    check=False,
                )
            except subprocess.SubprocessError:
                stop_result = None
            container_present = _container_is_present(docker, container_reference)
            if (
                stop_result is None
                or stop_result.returncode
                or container_present is not False
            ):
                if container_present is not False:
                    try:
                        remove_result = subprocess.run(
                            [docker, "rm", "--force", container_reference],
                            text=True,
                            capture_output=True,
                            timeout=20,
                            check=False,
                        )
                    except subprocess.SubprocessError:
                        remove_result = None
                    container_present = _container_is_present(
                        docker, container_reference
                    )
                    if container_present is not False:
                        cleanup_errors.append("container removal could not be verified")
        if network_attempted:
            network_reference = network_id or network_name
            try:
                remove_network = subprocess.run(
                    [docker, "network", "rm", network_reference],
                    text=True,
                    capture_output=True,
                    timeout=20,
                    check=False,
                )
            except subprocess.SubprocessError:
                remove_network = None
            network_present = _network_is_present(docker, network_reference)
            if network_present is not False:
                cleanup_errors.append("test network removal could not be verified")
        if cleanup_errors:
            raise RuntimeError(
                "Disposable PostgreSQL cleanup failed: " + ", ".join(cleanup_errors)
            )


if __name__ == "__main__":
    raise SystemExit(main())
