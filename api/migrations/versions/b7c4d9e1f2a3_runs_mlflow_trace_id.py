"""runs.mlflow_trace_id

Revision ID: b7c4d9e1f2a3
Revises: a1f3c2d4e5b6
Create Date: 2026-11-09 19:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7c4d9e1f2a3"
down_revision: str | Sequence[str] | None = "a1f3c2d4e5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("mlflow_trace_id", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("runs", "mlflow_trace_id")
