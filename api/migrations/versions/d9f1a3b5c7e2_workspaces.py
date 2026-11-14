"""workspaces, users and flow/run ownership

Revision ID: d9f1a3b5c7e2
Revises: c8e2f4a6b1d3
Create Date: 2026-11-15 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d9f1a3b5c7e2"
down_revision: str | Sequence[str] | None = "c8e2f4a6b1d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("sub", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("provider", "sub"),
    )
    op.create_table(
        "workspace_members",
        sa.Column(
            "workspace_id",
            sa.Uuid(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workspace_members_user_id", "workspace_members", ["user_id"])

    for table in ("flows", "runs"):
        op.add_column(
            table,
            sa.Column(
                "workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id", ondelete="CASCADE")
            ),
        )
        op.add_column(
            table,
            sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        )
        op.create_index(f"ix_{table}_workspace_id", table, ["workspace_id"])
    op.add_column(
        "flows",
        sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
    )


def downgrade() -> None:
    op.drop_column("flows", "updated_by")
    for table in ("runs", "flows"):
        op.drop_index(f"ix_{table}_workspace_id", table_name=table)
        op.drop_column(table, "created_by")
        op.drop_column(table, "workspace_id")
    op.drop_index("ix_workspace_members_user_id", table_name="workspace_members")
    op.drop_table("workspace_members")
    op.drop_table("users")
    op.drop_table("workspaces")
