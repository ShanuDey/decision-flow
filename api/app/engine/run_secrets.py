"""Secret values for one run. They live only in memory and never enter flow state."""

from typing import TYPE_CHECKING

from pydantic import Field, SecretStr

from app.engine.base import FrozenBaseModel
from app.engine.templates import references

if TYPE_CHECKING:
    from app.engine.graph import Graph


class RunSecrets(FrozenBaseModel):
    values: dict[str, SecretStr] = Field(default_factory=dict)

    def as_scope(self) -> dict[str, str]:
        return {name: value.get_secret_value() for name, value in self.values.items()}


def referenced_secret_names(graph: "Graph") -> set[str]:
    names: set[str] = set()
    for node in graph.nodes:
        templates = node.templates()
        for field in node.secret_fields() & templates.keys():
            names.update(r.path[0] for r in references(templates[field]) if r.scope == "secrets")
    return names
