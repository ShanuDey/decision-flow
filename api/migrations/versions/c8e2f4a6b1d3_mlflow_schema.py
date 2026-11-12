"""mlflow schema

Revision ID: c8e2f4a6b1d3
Revises: b7c4d9e1f2a3
Create Date: 2026-11-11 09:30:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "c8e2f4a6b1d3"
down_revision: str | Sequence[str] | None = "b7c4d9e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS mlflow")


def downgrade() -> None:
    # no CASCADE: refuses to drop a schema that still holds traces
    op.execute("DROP SCHEMA IF EXISTS mlflow")
