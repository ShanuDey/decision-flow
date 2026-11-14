import uuid

from app.engine.base import FrozenBaseModel


class Member(FrozenBaseModel):
    user_id: uuid.UUID
    workspace_id: uuid.UUID
