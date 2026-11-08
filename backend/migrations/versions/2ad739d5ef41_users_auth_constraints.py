"""Require non-null email and role for user accounts.

Revision ID: 2ad739d5ef41
Revises: c453ba1678f4
Create Date: 2026-11-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "2ad739d5ef41"
down_revision: Union[str, None] = "c453ba1678f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fail safely if unexpected legacy rows would make the constraints invalid.
    bind = op.get_bind()
    for column_name in ("email", "role"):
        missing_count = bind.execute(
            sa.text(f"SELECT COUNT(*) FROM users WHERE {column_name} IS NULL")
        ).scalar_one()
        if missing_count:
            raise RuntimeError(
                f"Cannot enforce users.{column_name} NOT NULL: "
                f"{missing_count} existing row(s) have NULL values. "
                "Resolve those records explicitly, then rerun the migration."
            )

    op.alter_column(
        "users",
        "email",
        existing_type=sa.String(),
        nullable=False,
    )
    op.alter_column(
        "users",
        "role",
        existing_type=sa.String(),
        nullable=False,
        server_default=sa.text("'student'"),
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "role",
        existing_type=sa.String(),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "users",
        "email",
        existing_type=sa.String(),
        nullable=True,
    )
