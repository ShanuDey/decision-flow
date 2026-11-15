"""flow versions

Revision ID: a4c6e8f0b2d4
Revises: f3b5c7d9e1a2
Create Date: 2026-11-15 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a4c6e8f0b2d4"
down_revision: str | Sequence[str] | None = "f3b5c7d9e1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "flow_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "flow_id", sa.Uuid(), sa.ForeignKey("flows.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("graph", postgresql.JSONB(), nullable=False),
        sa.Column("source_draft_version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("flow_id", "version"),
    )
    op.create_index("ix_flow_versions_flow_id", "flow_versions", ["flow_id"])
    op.add_column("flows", sa.Column("published_version", sa.Integer()))
    op.add_column("flows", sa.Column("published_draft_version", sa.Integer()))
    op.add_column("flows", sa.Column("published_at", sa.DateTime()))


def downgrade() -> None:
    op.drop_column("flows", "published_at")
    op.drop_column("flows", "published_draft_version")
    op.drop_column("flows", "published_version")
    op.drop_index("ix_flow_versions_flow_id", table_name="flow_versions")
    op.drop_table("flow_versions")
