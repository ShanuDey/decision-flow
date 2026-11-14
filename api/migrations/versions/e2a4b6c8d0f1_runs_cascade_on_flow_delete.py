"""runs cascade on flow delete

Revision ID: e2a4b6c8d0f1
Revises: d9f1a3b5c7e2
Create Date: 2026-11-15 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "e2a4b6c8d0f1"
down_revision: str | Sequence[str] | None = "d9f1a3b5c7e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("runs_flow_id_fkey", "runs", type_="foreignkey")
    op.create_foreign_key(
        "runs_flow_id_fkey", "runs", "flows", ["flow_id"], ["id"], ondelete="CASCADE"
    )


def downgrade() -> None:
    op.drop_constraint("runs_flow_id_fkey", "runs", type_="foreignkey")
    op.create_foreign_key("runs_flow_id_fkey", "runs", "flows", ["flow_id"], ["id"])
