import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class InstalledItem(Base):
    __tablename__ = "installed_items"
    __table_args__ = (UniqueConstraint("workspace_id", "kind", "item_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(32))
    item_id: Mapped[str] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(32))
    hash: Mapped[str] = mapped_column(String(80))
    # A copy of the file, so the item keeps working when the catalog changes or goes away.
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB)
    installed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    installed_at: Mapped[datetime] = mapped_column(server_default=func.now())
