"""What a node template is. The templates themselves are JSON files."""

import re
from typing import Literal, Self

from pydantic import Field, model_validator

from app.engine.base import FrozenBaseModel
from app.engine.nodes.base import NodeContext
from app.engine.nodes.http_request import HttpRequestData, HttpRequestNode
from app.engine.templates import TemplateError, references

TEMPLATE_ID = re.compile(r"[a-z][a-z0-9_]{0,63}")
INPUT_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}")
SECRET_NAME = re.compile(r"[A-Z][A-Z0-9_]{0,63}")


class TemplateConnection(FrozenBaseModel):
    type: str
    # Suggested values when the user creates the connection, such as the allowed hosts.
    values: dict[str, str] = Field(default_factory=dict)


class TemplateInput(FrozenBaseModel):
    name: str
    type: Literal["string", "number", "boolean", "object", "array"] = "string"
    description: str = ""


class NodeTemplate(FrozenBaseModel):
    schema_version: Literal[1] = 1
    version: str = Field("1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    id: str
    name: str
    description: str
    icon: str = "plug"
    docs_url: str = ""
    tags: list[str] = Field(default_factory=list)
    node_type: Literal["http_request"]
    connection: TemplateConnection | None = None
    # Secrets the data reads as `{{ secrets.NAME }}`, so the card can say what to create.
    secrets: list[str] = Field(default_factory=list)
    # Flow inputs the data reads as `{{ input.name }}`; shown on the card, not added to a flow.
    inputs: list[TemplateInput] = Field(default_factory=list)
    data: HttpRequestData

    @model_validator(mode="after")
    def _check(self) -> Self:
        """A file is data, so it must be a valid node and only use what it declares."""
        problems: list[str] = []
        if not TEMPLATE_ID.fullmatch(self.id):
            problems.append("id must be lowercase letters, digits and underscores")
        if bad := next((s for s in self.secrets if not SECRET_NAME.fullmatch(s)), None):
            problems.append(f"secret '{bad}' must be capitals, digits and underscores")
        if len(set(self.secrets)) != len(self.secrets):
            problems.append("secrets must be unique")
        names = [i.name for i in self.inputs]
        if len(set(names)) != len(names):
            problems.append("input names must be unique")
        if bad := next((n for n in names if not INPUT_NAME.fullmatch(n)), None):
            problems.append(f"input '{bad}' is not a valid name")
        if self.data.connection_id:
            problems.append("data must not set connection_id; the user picks the connection")

        node = HttpRequestNode(id="template", type="http_request", data=self.data)
        problems += [issue.message for issue in node.check(NodeContext(variables=[]))]
        problems += self._reference_problems(node)
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def _reference_problems(self, node: HttpRequestNode) -> list[str]:
        problems: list[str] = []
        used_secrets: set[str] = set()
        secret_fields = node.secret_fields()
        for field, text in node.templates().items():
            try:
                found = references(text)
            except TemplateError as exc:
                problems.append(f"{field}: {exc}")
                continue
            for ref in found:
                name = ref.path[0] if ref.path else ""
                if ref.scope == "input":
                    if name not in {i.name for i in self.inputs}:
                        problems.append(
                            f"{field} reads input '{name}' that is not listed in inputs"
                        )
                elif ref.scope == "secrets":
                    used_secrets.add(name)
                    if field not in secret_fields:
                        problems.append(f"{field} cannot use a secret")
                    elif name not in self.secrets:
                        problems.append(
                            f"{field} uses secret '{name}' that is not listed in secrets"
                        )
                else:
                    problems.append(
                        f"{field} uses '{ref.scope}'; only input and secrets are allowed"
                    )
        problems += [
            f"secret '{s}' is listed but never used" for s in self.secrets if s not in used_secrets
        ]
        return problems


class NodeTemplateList(FrozenBaseModel):
    items: list[NodeTemplate]
