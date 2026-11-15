"""soft delete columns

Revision ID: b5d7f9a1c3e5
Revises: a4c6e8f0b2d4
Create Date: 2026-11-15 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b5d7f9a1c3e5"
down_revision: str | Sequence[str] | None = "a4c6e8f0b2d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("flows", "flow_versions")


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("deleted_at", sa.DateTime()))
        op.add_column(
            table,
            sa.Column(
                "deleted_by",
                sa.Uuid(),
                sa.ForeignKey("users.id", ondelete="RESTRICT", name=f"fk_{table}_deleted_by"),
            ),
        )


def downgrade() -> None:
    for table in TABLES:
        op.drop_constraint(f"fk_{table}_deleted_by", table, type_="foreignkey")
        op.drop_column(table, "deleted_by")
        op.drop_column(table, "deleted_at")
