"""the outside app's user a conversation belongs to

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-11-23 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agent_threads", sa.Column("external_user_id", sa.String(256), nullable=True))
    op.create_index(
        "agent_threads_external_user_idx", "agent_threads", ["workspace_id", "external_user_id"]
    )


def downgrade() -> None:
    op.drop_index("agent_threads_external_user_idx", table_name="agent_threads")
    op.drop_column("agent_threads", "external_user_id")
