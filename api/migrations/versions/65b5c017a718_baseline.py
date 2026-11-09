"""baseline

Revision ID: 65b5c017a718
Revises:
Create Date: 2026-11-09 16:12:57.957041

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "65b5c017a718"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
