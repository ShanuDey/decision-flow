"""run flow version

Revision ID: 0aa6b08c25a2
Revises: b5d7f9a1c3e5
Create Date: 2026-11-15 12:40:11.423094

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0aa6b08c25a2"
down_revision: str | Sequence[str] | None = "b5d7f9a1c3e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("flow_version", sa.Integer()))


def downgrade() -> None:
    op.drop_column("runs", "flow_version")
