"""flows and runs

Revision ID: a1f3c2d4e5b6
Revises: 65b5c017a718
Create Date: 2026-11-09 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1f3c2d4e5b6"
down_revision: str | Sequence[str] | None = "65b5c017a718"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "flows",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("draft", postgresql.JSONB(), nullable=False),
        sa.Column("draft_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("flow_id", sa.Uuid(), sa.ForeignKey("flows.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("test", sa.Boolean(), nullable=False),
        sa.Column("input", postgresql.JSONB(), nullable=False),
        sa.Column("output", postgresql.JSONB(), nullable=True),
        sa.Column("error", postgresql.JSONB(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_runs_flow_id", "runs", ["flow_id"])


def downgrade() -> None:
    op.drop_index("ix_runs_flow_id", table_name="runs")
    op.drop_table("runs")
    op.drop_table("flows")
