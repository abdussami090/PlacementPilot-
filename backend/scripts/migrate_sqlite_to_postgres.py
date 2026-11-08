"""Safely transfer PlacementPilot data from SQLite to PostgreSQL.

Default mode is DRY RUN. Add --execute to perform the transfer.
Run from the backend folder with its virtual environment activated:
    python -m scripts.migrate_sqlite_to_postgres
    python -m scripts.migrate_sqlite_to_postgres --execute
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, JSON, inspect, text

# Import every SQLAlchemy model before accessing Base.metadata.
from app import model_registry  # noqa: F401
from app.database import Base, engine

BACKEND_DIR = Path(__file__).resolve().parents[1]
SQLITE_PATH = BACKEND_DIR / "placementpilot.db"

# Parent tables must be inserted before tables that reference them.
TABLE_ORDER = [
    "users",
    "companies",
    "educations",
    "placement_cycles",
    "profiles",
    "resumes",
    "skills",
    "uploaded_resumes",
    "company_recruitment_drives",
    "placement_policies",
    "jobs",
    "placement_rounds",
    "applications",
    "job_eligibilities",
    "saved_jobs",
    "candidate_rounds",
]


def open_sqlite_read_only() -> sqlite3.Connection:
    if not SQLITE_PATH.is_file():
        raise FileNotFoundError(f"SQLite database not found: {SQLITE_PATH}")
    uri = SQLITE_PATH.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def rows_for(connection: sqlite3.Connection, table_name: str) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(f'SELECT * FROM "{table_name}"')]


def normalize_number(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value)).normalize()
    except InvalidOperation:
        return None


def validate_legacy_mappings(source: sqlite3.Connection) -> None:
    """Ensure legacy-only rows have a safe canonical equivalent before skipping them."""
    legacy_drives = rows_for(source, "placement_drives") if source.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='placement_drives'"
    ).fetchone() else []

    for old_drive in legacy_drives:
        current = source.execute(
            "SELECT * FROM company_recruitment_drives WHERE id = ?",
            (old_drive["id"],),
        ).fetchone()
        if current is None:
            raise RuntimeError(
                f"Legacy placement drive {old_drive['id']} has no matching "
                "company_recruitment_drives record. Migration stopped."
            )
        current = dict(current)
        for field in ("company_id", "name", "created_by"):
            if old_drive[field] != current[field]:
                raise RuntimeError(
                    f"Legacy drive {old_drive['id']} does not match its canonical "
                    f"recruitment drive on {field}. Migration stopped."
                )
        linked_jobs = source.execute(
            "SELECT id, recruitment_drive_id FROM jobs WHERE placement_drive_id = ?",
            (old_drive["id"],),
        ).fetchall()
        for job in linked_jobs:
            if job["recruitment_drive_id"] != current["id"]:
                raise RuntimeError(
                    f"Job {job['id']} is not linked to the matching canonical "
                    "recruitment drive. Migration stopped."
                )
        print(
            f"Legacy placement_drives ID {old_drive['id']} -> "
            f"canonical company_recruitment_drives ID {current['id']}: verified."
        )
        if (old_drive.get("application_start_date") != current.get("application_start_date")
                or old_drive.get("application_deadline") != current.get("application_deadline")):
            print(
                "  Note: legacy dates differ from the canonical drive. "
                "The newer canonical drive dates will be retained; the original "
                "legacy row remains in the untouched SQLite backup."
            )

    legacy_academics = rows_for(source, "student_academic_details") if source.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='student_academic_details'"
    ).fetchone() else []

    for old in legacy_academics:
        candidates = source.execute(
            "SELECT * FROM educations WHERE user_id = ?",
            (old["user_id"],),
        ).fetchall()
        matched = None
        for candidate_row in candidates:
            candidate = dict(candidate_row)
            degree_matches = (
                str(candidate.get("degree") or "").strip().casefold()
                == str(old.get("course") or "").strip().casefold()
            )
            cgpa_matches = normalize_number(candidate.get("cgpa")) == normalize_number(old.get("cgpa"))
            if (
                degree_matches
                and candidate.get("graduation_year") == old.get("graduation_year")
                and candidate.get("active_backlogs") == old.get("active_backlogs")
                and cgpa_matches
            ):
                matched = candidate
                break
        if matched is None:
            raise RuntimeError(
                f"Legacy academic record {old['id']} for user {old['user_id']} "
                "has no matching educations record. Migration stopped."
            )
        print(
            f"Legacy student_academic_details ID {old['id']} -> "
            f"existing educations ID {matched['id']}: verified duplicate; not inserted twice."
        )


def convert_value(column_type: Any, value: Any) -> Any:
    if value is None:
        return None
    if isinstance(column_type, JSON):
        if isinstance(value, str):
            return json.loads(value)
        return value
    if isinstance(column_type, DateTime):
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        return value
    if isinstance(column_type, Date):
        if isinstance(value, str):
            return date.fromisoformat(value[:10])
        return value
    if isinstance(column_type, Boolean):
        return bool(value)
    return value


def prepare_rows(source: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    source_table_names = {
        row[0]
        for row in source.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    missing_source = [name for name in TABLE_ORDER if name not in source_table_names]
    missing_models = [name for name in TABLE_ORDER if name not in Base.metadata.tables]
    if missing_source:
        raise RuntimeError(f"Missing expected SQLite tables: {missing_source}")
    if missing_models:
        raise RuntimeError(f"Missing registered SQLAlchemy models: {missing_models}")

    prepared: dict[str, list[dict[str, Any]]] = {}
    for table_name in TABLE_ORDER:
        source_rows = rows_for(source, table_name)
        target_table = Base.metadata.tables[table_name]
        target_column_names = {column.name for column in target_table.columns}
        converted_rows: list[dict[str, Any]] = []

        for source_row in source_rows:
            target_row: dict[str, Any] = {}
            for column in target_table.columns:
                if column.name in source_row:
                    target_row[column.name] = convert_value(
                        column.type, source_row[column.name]
                    )
                elif (
                    not column.nullable
                    and not column.primary_key
                    and column.server_default is None
                    and column.default is None
                ):
                    raise RuntimeError(
                        f"{table_name}: required PostgreSQL column '{column.name}' "
                        "has no source value or default. Migration stopped."
                    )
            # Legacy jobs columns 'company' and 'placement_drive_id' are intentionally omitted.
            extra_columns = set(source_row) - target_column_names
            if table_name == "jobs":
                unexpected = extra_columns - {"company", "placement_drive_id"}
                if unexpected:
                    raise RuntimeError(f"Unexpected legacy jobs columns: {sorted(unexpected)}")
            elif extra_columns:
                raise RuntimeError(
                    f"Unexpected source-only columns in {table_name}: {sorted(extra_columns)}"
                )
            converted_rows.append(target_row)
        prepared[table_name] = converted_rows

    # Confirm private PDF files still exist before any database write.
    for resume in prepared["uploaded_resumes"]:
        stored_path = Path(resume["storage_path"])
        if not stored_path.is_absolute():
            stored_path = BACKEND_DIR / stored_path
        if not stored_path.is_file():
            raise FileNotFoundError(
                f"Uploaded resume file is missing for resume ID {resume['id']}: {stored_path}"
            )

    return prepared


def verify_postgres_is_empty() -> None:
    if engine.dialect.name != "postgresql":
        raise RuntimeError(
            f"Configured database is '{engine.dialect.name}', not PostgreSQL. "
            "Check backend/.env before continuing."
        )
    inspector = inspect(engine)
    with engine.connect() as connection:
        non_empty: list[str] = []
        for table_name in TABLE_ORDER:
            if table_name not in inspector.get_table_names():
                raise RuntimeError(f"PostgreSQL table is missing: {table_name}")
            count = connection.execute(
                text(f'SELECT COUNT(*) FROM "{table_name}"')
            ).scalar_one()
            if count:
                non_empty.append(f"{table_name}={count}")
        if non_empty:
            raise RuntimeError(
                "PostgreSQL destination is not empty. No data was transferred. "
                "Existing rows: " + ", ".join(non_empty)
            )


def print_summary(prepared: dict[str, list[dict[str, Any]]]) -> None:
    total = 0
    print("\nPrepared transfer (SQLite -> PostgreSQL):")
    for table_name in TABLE_ORDER:
        count = len(prepared[table_name])
        total += count
        print(f"  {table_name}: {count}")
    print(f"Total application records: {total}")
    print("Legacy tables: placement_drives and student_academic_details are not inserted separately.")
    print("Uploaded PDF: file existence verified; its existing storage path will be retained.")


def execute_transfer(prepared: dict[str, list[dict[str, Any]]]) -> None:
    # The whole row transfer is one PostgreSQL transaction: a failed insert rolls it back.
    with engine.begin() as connection:
        for table_name in TABLE_ORDER:
            count = connection.execute(
                text(f'SELECT COUNT(*) FROM "{table_name}"')
            ).scalar_one()
            if count:
                raise RuntimeError(
                    f"PostgreSQL table {table_name} is no longer empty. Transfer aborted."
                )

        for table_name in TABLE_ORDER:
            records = prepared[table_name]
            if records:
                target_table = Base.metadata.tables[table_name]
                connection.execute(target_table.insert(), records)

        # Explicitly inserted IDs require their PostgreSQL sequences to be advanced.
        for table_name in TABLE_ORDER:
            target_table = Base.metadata.tables[table_name]
            if "id" not in target_table.c:
                continue
            sequence_name = connection.execute(
                text("SELECT pg_get_serial_sequence(:table_name, 'id')"),
                {"table_name": f"public.{table_name}"},
            ).scalar_one_or_none()
            if sequence_name:
                max_id = connection.execute(
                    text(f'SELECT MAX(id) FROM "{table_name}"')
                ).scalar_one_or_none()
                if max_id is None:
                    connection.execute(
                        text("SELECT setval(CAST(:sequence_name AS regclass), 1, false)"),
                        {"sequence_name": sequence_name},
                    )
                else:
                    connection.execute(
                        text("SELECT setval(CAST(:sequence_name AS regclass), :max_id, true)"),
                        {"sequence_name": sequence_name, "max_id": max_id},
                    )

    print("\nTransfer transaction committed.")
    with engine.connect() as connection:
        print("\nPostgreSQL verification counts:")
        for table_name in TABLE_ORDER:
            count = connection.execute(
                text(f'SELECT COUNT(*) FROM "{table_name}"')
            ).scalar_one()
            expected = len(prepared[table_name])
            print(f"  {table_name}: {count} (expected {expected})")
            if count != expected:
                raise RuntimeError(
                    f"Post-transfer count mismatch in {table_name}: "
                    f"expected {expected}, found {count}."
                )


def main() -> int:
    parser = argparse.ArgumentParser(description="Transfer PlacementPilot SQLite data to PostgreSQL.")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Perform the transfer. Without this flag, only a dry run is performed.",
    )
    args = parser.parse_args()

    print(f"SQLite source: {SQLITE_PATH}")
    print(f"PostgreSQL destination dialect: {engine.dialect.name}")

    source = open_sqlite_read_only()
    try:
        integrity = source.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity check failed: {integrity}")
        violations = source.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(
                f"SQLite contains foreign-key violations: {[tuple(row) for row in violations[:10]]}"
            )

        validate_legacy_mappings(source)
        prepared = prepare_rows(source)
    finally:
        source.close()

    verify_postgres_is_empty()
    print_summary(prepared)

    if not args.execute:
        print("\nDRY RUN ONLY: no PostgreSQL records were written.")
        print("Review this output. To perform the transfer, rerun with --execute.")
        return 0

    execute_transfer(prepared)
    print("\nSUCCESS: SQLite records have been copied to PostgreSQL.")
    print("The original SQLite database and backup were not modified.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\nMIGRATION STOPPED: {exc}", file=sys.stderr)
        raise SystemExit(1)
