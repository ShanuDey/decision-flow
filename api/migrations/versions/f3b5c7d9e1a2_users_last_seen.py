"""users last_seen_at, for retention

Revision ID: f3b5c7d9e1a2
Revises: e2a4b6c8d0f1
Create Date: 2026-11-15 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3b5c7d9e1a2"
down_revision: str | Sequence[str] | None = "e2a4b6c8d0f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("last_seen_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "last_seen_at")
