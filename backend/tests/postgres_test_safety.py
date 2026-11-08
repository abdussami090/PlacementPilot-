"""Fail-closed authorization and identity checks for disposable PostgreSQL tests."""

import ipaddress
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

AUTH_FILE_ENV = "PLACEMENTPILOT_PG_TEST_AUTH_FILE"
AUTH_RUN_ID_ENV = "PLACEMENTPILOT_PG_TEST_RUN_ID"
AUTH_NONCE_ENV = "PLACEMENTPILOT_PG_TEST_NONCE"
LEGACY_POSTGRES_SETTINGS = (
    "PLACEMENTPILOT_TEST_DATABASE_URL",
    "PLACEMENTPILOT_ALLOW_DESTRUCTIVE_POSTGRES_TESTS",
    "PLACEMENTPILOT_TEST_DATABASE_HOST",
    "PLACEMENTPILOT_TEST_DATABASE_PORT",
    "PLACEMENTPILOT_TEST_DATABASE_NAME",
    "PLACEMENTPILOT_TEST_DATABASE_USER",
)
DISPOSABLE_DATABASE_COMMENT = "PlacementPilot disposable test database"
_DISPOSABLE_DATABASE_NAME = re.compile(
    r"^placementpilot_test_[a-f0-9]{32}$"
)
_AUTHORIZATION_TTL_SECONDS = 600

_IDENTITY_QUERY = text(
    """
    SELECT current_database() AS database_name,
           current_user AS role_name,
           inet_server_addr()::text AS server_address,
           inet_server_port() AS server_port,
           shobj_description(db_catalog.oid, 'pg_database') AS database_comment,
           role_catalog.rolcanlogin AS can_login,
           role_catalog.rolsuper AS is_superuser,
           role_catalog.rolcreatedb AS can_create_database,
           role_catalog.rolcreaterole AS can_create_role,
           role_catalog.rolreplication AS can_replicate,
           role_catalog.rolbypassrls AS can_bypass_row_security,
           (SELECT count(*)
            FROM pg_roles AS granted_role
            WHERE granted_role.oid <> role_catalog.oid
              AND pg_has_role(role_catalog.oid, granted_role.oid, 'MEMBER')
           ) AS role_membership_count,
           pg_get_userbyid(db_catalog.datdba) AS database_owner,
           pg_get_userbyid(schema_catalog.nspowner) AS schema_owner
    FROM pg_database AS db_catalog
    JOIN pg_roles AS role_catalog ON role_catalog.rolname = current_user
    JOIN pg_namespace AS schema_catalog ON schema_catalog.nspname = 'public'
    WHERE db_catalog.datname = current_database()
    """
)


@dataclass(frozen=True)
class PostgresTestTarget:
    url: URL = field(repr=False)
    host: str
    port: int
    database: str
    username: str
    server_port: int
    server_address: str
    container_id: str
    run_id: str


def validate_local_docker_context(
    context_name: str,
    endpoint: str,
    environment: Mapping[str, str] | None = None,
) -> None:
    """Reject configured overrides and Docker endpoints that can be remote."""
    env = os.environ if environment is None else environment
    if env.get("DOCKER_HOST", "").strip() or env.get("DOCKER_CONTEXT", "").strip():
        raise RuntimeError("Docker environment overrides are not allowed for PostgreSQL tests.")
    if not context_name.strip() or not endpoint.strip():
        raise RuntimeError("Could not verify the active local Docker context.")
    if endpoint.startswith(("ssh://", "tcp://", "http://", "https://")):
        raise RuntimeError("Remote Docker contexts are not allowed for PostgreSQL tests.")
    if os.name == "nt":
        local_endpoint = re.fullmatch(
            r"npipe:////\./pipe/[^/]+",
            endpoint.lower(),
        ) is not None
    else:
        parsed_endpoint = urlsplit(endpoint)
        local_endpoint = (
            parsed_endpoint.scheme == "unix"
            and not parsed_endpoint.netloc
            and parsed_endpoint.path.startswith("/")
            and ".." not in Path(parsed_endpoint.path).parts
        )
    if not local_endpoint:
        raise RuntimeError("Docker must use a local named-pipe or Unix-socket endpoint.")


def validate_container_inspection(
    inspection: Mapping[str, Any],
    expected_run_id: str,
    expected_network_name: str,
) -> tuple[int, str]:
    """Require a running, unmounted PostgreSQL container published on loopback."""
    config = inspection.get("Config") or {}
    state = inspection.get("State") or {}
    host_config = inspection.get("HostConfig") or {}
    mounts = inspection.get("Mounts") or []
    tmpfs_configuration = host_config.get("Tmpfs") or {}
    ephemeral_mounts = all(
        mount.get("Type") == "tmpfs"
        and mount.get("Destination") == "/var/lib/postgresql"
        for mount in mounts
    )
    if (
        not state.get("Running")
        or not str(config.get("Image", "")).startswith("postgres:")
        or (host_config.get("Binds") or [])
        or (host_config.get("VolumesFrom") or [])
        or set(tmpfs_configuration) != {"/var/lib/postgresql"}
        or len(mounts) != 1
        or not ephemeral_mounts
    ):
        raise RuntimeError("PostgreSQL test container is not a fresh unmounted container.")
    labels = config.get("Labels") or {}
    if labels.get("placementpilot.test.run") != expected_run_id:
        raise RuntimeError("PostgreSQL test container does not match the provisioner run.")
    ports = ((inspection.get("NetworkSettings") or {}).get("Ports") or {}).get(
        "5432/tcp"
    )
    if not isinstance(ports, list) or len(ports) != 1:
        raise RuntimeError("PostgreSQL test container must have one loopback-only port mapping.")
    binding = ports[0]
    if binding.get("HostIp") != "127.0.0.1":
        raise RuntimeError("PostgreSQL test container port must bind only to IPv4 loopback.")
    try:
        host_port = int(binding["HostPort"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("PostgreSQL test container host port is invalid.") from exc
    if not 1 <= host_port <= 65535:
        raise RuntimeError("PostgreSQL test container host port is invalid.")
    networks = (inspection.get("NetworkSettings") or {}).get("Networks") or {}
    if set(networks) != {expected_network_name}:
        raise RuntimeError("PostgreSQL test container must use one isolated network.")
    try:
        container_address = ipaddress.ip_interface(
            next(iter(networks.values()))["IPAddress"]
        ).ip
    except (KeyError, StopIteration, ValueError) as exc:
        raise RuntimeError("PostgreSQL test container address is invalid.") from exc
    if (
        not isinstance(container_address, ipaddress.IPv4Address)
        or not container_address.is_private
    ):
        raise RuntimeError("PostgreSQL test container must have a private IPv4 address.")
    return host_port, str(container_address)


def validate_test_network(network: Mapping[str, Any], expected_run_id: str) -> None:
    """Require a run-specific internal bridge without external connectivity."""
    labels = network.get("Labels") or {}
    if (
        network.get("Driver") != "bridge"
        or network.get("Internal") is not True
        or labels.get("placementpilot.test.run") != expected_run_id
    ):
        raise RuntimeError("PostgreSQL test network is not an isolated internal bridge.")


def issue_run_authorization(
    authorization_path: Path,
    *,
    run_id: str,
    nonce: str,
    parent_pid: int,
    target_metadata: Mapping[str, Any],
    issued_at: int | None = None,
) -> None:
    """Write a short-lived, one-use capability for a single pytest child."""
    issued = int(time.time()) if issued_at is None else issued_at
    payload = {
        "version": 1,
        "run_id": run_id,
        "nonce": nonce,
        "parent_pid": parent_pid,
        "issued_at": issued,
        "expires_at": issued + _AUTHORIZATION_TTL_SECONDS,
        **target_metadata,
    }
    descriptor = os.open(
        authorization_path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as authorization_file:
        json.dump(payload, authorization_file)


def consume_run_authorization(
    environment: Mapping[str, str] | None = None,
    *,
    parent_pid: int | None = None,
    now: int | None = None,
) -> dict[str, Any]:
    """Consume and validate the provisioner's one-run pytest capability."""
    env = os.environ if environment is None else environment
    path_value = env.get(AUTH_FILE_ENV, "").strip()
    run_id = env.get(AUTH_RUN_ID_ENV, "").strip()
    nonce = env.get(AUTH_NONCE_ENV, "").strip()
    if not path_value or not run_id or not nonce:
        raise RuntimeError("PostgreSQL tests require authorization from the test provisioner.")
    path = Path(path_value)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("PostgreSQL test authorization is missing or invalid.") from exc
    try:
        path.unlink()
    except OSError as exc:
        raise RuntimeError("PostgreSQL test authorization could not be consumed.") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("PostgreSQL test authorization is invalid.")

    timestamp = int(time.time()) if now is None else now
    expected_parent_pid = os.getppid() if parent_pid is None else parent_pid
    if (
        payload.get("version") != 1
        or payload.get("run_id") != run_id
        or payload.get("nonce") != nonce
        or payload.get("parent_pid") != expected_parent_pid
        or not isinstance(payload.get("issued_at"), int)
        or not isinstance(payload.get("expires_at"), int)
        or payload["issued_at"] > timestamp
        or payload["expires_at"] <= timestamp
        or payload["expires_at"] - payload["issued_at"] > _AUTHORIZATION_TTL_SECONDS
    ):
        raise RuntimeError("PostgreSQL test authorization is stale or does not match this run.")
    return payload


def target_from_authorization(
    authorization: Mapping[str, Any],
    database_url: str,
) -> PostgresTestTarget:
    """Validate the test target values supplied by the provisioner."""
    try:
        url = make_url(database_url)
    except (ArgumentError, TypeError, ValueError) as exc:
        raise RuntimeError("Provisioned PostgreSQL test URL is invalid.") from exc
    database = str(authorization.get("database", ""))
    username = str(authorization.get("username", ""))
    container_id = str(authorization.get("container_id", ""))
    container_address = str(authorization.get("container_address", ""))
    run_id = str(authorization.get("run_id", ""))
    try:
        port = int(authorization.get("host_port"))
        url_port = url.port
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Provisioned PostgreSQL test port is invalid.") from exc
    try:
        container_address_value = ipaddress.ip_address(container_address)
    except ValueError as exc:
        raise RuntimeError("Provisioned PostgreSQL container address is invalid.") from exc
    if (
        url.drivername != "postgresql+psycopg"
        or url.host != "127.0.0.1"
        or url.query
        or url.database != database
        or url.username != username
        or not url.password
        or url_port != port
        or not 1 <= port <= 65535
        or not _DISPOSABLE_DATABASE_NAME.fullmatch(database)
        or not re.fullmatch(r"[a-f0-9]{64}", container_id)
        or not re.fullmatch(r"[a-f0-9]{32}", run_id)
        or not re.fullmatch(r"[a-f0-9]{64}", str(authorization.get("nonce", "")))
        or not isinstance(container_address_value, ipaddress.IPv4Address)
        or not container_address_value.is_private
    ):
        raise RuntimeError("Provisioned PostgreSQL target does not match its authorization.")
    return PostgresTestTarget(
        url=url,
        host="127.0.0.1",
        port=port,
        database=database,
        username=username,
        server_port=5432,
        server_address=str(container_address_value),
        container_id=container_id,
        run_id=run_id,
    )


def validate_postgres_server_identity(
    target: PostgresTestTarget,
    identity: Mapping[str, Any] | None,
) -> None:
    """Check session identity as defense in depth, not locality proof."""
    if identity is None:
        raise RuntimeError("Could not verify PostgreSQL test database identity.")
    required_fields = {
        "database_name",
        "role_name",
        "database_comment",
        "server_port",
        "database_owner",
        "schema_owner",
        "server_address",
        "can_login",
        "role_membership_count",
        "is_superuser",
        "can_create_database",
        "can_create_role",
        "can_replicate",
        "can_bypass_row_security",
    }
    if not required_fields.issubset(identity):
        raise RuntimeError("PostgreSQL test server identity information is incomplete.")
    if (
        identity["database_name"] != target.database
        or identity["role_name"] != target.username
        or identity["database_comment"] != DISPOSABLE_DATABASE_COMMENT
        or identity["server_port"] != target.server_port
        or identity["database_owner"] != target.username
        or identity["schema_owner"] != target.username
        or identity["server_address"] != target.server_address
    ):
        raise RuntimeError("Connected PostgreSQL server did not match the provisioned test target.")
    if not identity["can_login"] or identity["role_membership_count"] != 0:
        raise RuntimeError(
            "PostgreSQL test role must be a standalone login without role memberships."
        )
    if any(
        identity[flag]
        for flag in (
            "is_superuser",
            "can_create_database",
            "can_create_role",
            "can_replicate",
            "can_bypass_row_security",
        )
    ):
        raise RuntimeError("PostgreSQL test role must not have administrative privileges.")


def create_verified_postgres_test_engine(
    target: PostgresTestTarget,
    engine_factory: Callable[..., Any] = create_engine,
) -> Any:
    """Verify PostgreSQL identity before exposing its engine to destructive fixtures."""
    engine = engine_factory(target.url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            identity = connection.execute(_IDENTITY_QUERY).mappings().one_or_none()
        validate_postgres_server_identity(target, identity)
    except Exception:
        engine.dispose()
        raise
    return engine
