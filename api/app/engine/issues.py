"""A validation finding, reported with the node and field it concerns."""

from app.engine.base import FrozenBaseModel


class Issue(FrozenBaseModel):
    code: str
    message: str
    node_id: str | None = None
    field: str | None = None
