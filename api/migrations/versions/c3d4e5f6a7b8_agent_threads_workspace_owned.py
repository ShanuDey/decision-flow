"""agent threads belong to the workspace, not to the person who started them

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-11-23 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FK = "agent_threads_created_by_fkey"


def upgrade() -> None:
    op.alter_column("agent_threads", "created_by", existing_type=sa.Uuid(), nullable=True)
    op.drop_constraint(FK, "agent_threads", type_="foreignkey")
    op.create_foreign_key(FK, "agent_threads", "users", ["created_by"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.execute("DELETE FROM agent_threads WHERE created_by IS NULL")
    op.drop_constraint(FK, "agent_threads", type_="foreignkey")
    op.create_foreign_key(FK, "agent_threads", "users", ["created_by"], ["id"], ondelete="CASCADE")
    op.alter_column("agent_threads", "created_by", existing_type=sa.Uuid(), nullable=False)
