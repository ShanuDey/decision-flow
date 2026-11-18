"""HTTP only: lists the built-in node templates."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends

from app.limits import Limits, get_limits
from app.node_templates.catalog import TEMPLATES
from app.node_templates.schemas import NodeTemplateList
from app.security.policy import outbound_policy
from app.security.ssrf import static_url_problem
from app.settings import Settings, get_settings

router = APIRouter(tags=["node-templates"])


@router.get("/node-templates")
async def list_node_templates(
    limits: Annotated[Limits, Depends(get_limits)],
    settings: Annotated[Settings, Depends(get_settings)],
    node_type: Literal["http_request"] | None = None,
) -> NodeTemplateList:
    """Lists the ready-made settings for a node, such as an HTTP Request.

    A template this server could not run is left out: its node type is turned off, or its URL
    points at a host the server does not allow. Applying one copies its settings into the node;
    nothing stays linked to it.
    """
    policy = outbound_policy(settings, limits)
    items = [
        t
        for t in TEMPLATES
        if (node_type is None or t.node_type == node_type)
        and t.node_type not in limits.disabled_node_types
        and static_url_problem(t.data.url, policy) is None
    ]
    return NodeTemplateList(items=items)
