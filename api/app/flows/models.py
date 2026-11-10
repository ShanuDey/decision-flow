import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Flow(Base):
    __tablename__ = "flows"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    # Stored as raw JSON: an invalid draft must still be saveable.
    draft: Mapped[dict[str, Any]] = mapped_column(JSONB)
    draft_version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())
