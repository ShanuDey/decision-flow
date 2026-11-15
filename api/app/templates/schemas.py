from typing import Any

from app.engine.base import FrozenBaseModel


class Template(FrozenBaseModel):
    id: str
    title: str
    summary: str
    description: str
    category: str
    inputs: list[str]
    outputs: list[str]
    node_types: list[str]
    draft: dict[str, Any]


class TemplateList(FrozenBaseModel):
    items: list[Template]
