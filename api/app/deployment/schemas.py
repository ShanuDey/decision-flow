from typing import Literal

from app.engine.base import FrozenBaseModel


class AppConfig(FrozenBaseModel):
    delete_mode: Literal["hard", "soft"]
    disabled_node_types: list[str]
    # Largest flow; 0 means no limit.
    max_nodes: int
    max_edges: int
    limit_notice: str
    limit_notice_url: str
