import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Secret(Base):
    __tablename__ = "secrets"
    __table_args__ = (UniqueConstraint("workspace_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(64))
    value_encrypted: Mapped[str] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())
