# Backend tests

Ordinary backend tests use an in-memory SQLite database. `conftest.py`
overrides `DATABASE_URL` before importing the application, so neither the
process's database URL nor `backend/.env` selects the test database.

The PostgreSQL integration tests are skipped during direct `pytest` runs.
Their schema-reset fixture is available only through the dedicated provisioner:

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.run_postgres_integration_tests
```

The provisioner requires Docker using a local named-pipe endpoint on Windows
or a local Unix socket elsewhere. It rejects `DOCKER_HOST`, `DOCKER_CONTEXT`,
TCP, and SSH Docker endpoints. It creates a new PostgreSQL container with
unique credentials, publishes its port only on `127.0.0.1`, stores database
files in a container tmpfs, and creates a separate non-admin test role. It
does not mount a host directory or named volume. The container uses a
run-specific internal bridge network without external connectivity. The
provisioner checks the container's network, private address, port binding,
image, and mounts before authorizing a one-use, short-lived grant to the
pytest child process. It stops/removes the container and network after the
run, including on failure.

The database name, marker, and SQL session identity checks are defense in
depth; they do not prove physical locality. Isolation depends on the local
Docker endpoint and the provisioner-controlled container lifecycle. As with
any local destructive test tool, this trusts the machine's Docker daemon and
local account; it cannot detect a malicious proxy replacing that local socket.
Do not configure the workflow to use a remote Docker context, connect it to
external databases, or replace its generated credentials/target. Do not run
destructive PostgreSQL tests against any development or production database.

If Docker is unavailable or its local endpoint cannot be verified, the
provisioner exits without running the PostgreSQL tests. SQLite tests remain
available with the normal backend test command.
