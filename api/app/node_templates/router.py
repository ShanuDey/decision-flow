"""HTTP only: lists the node templates a workspace can use."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends

from app.catalog.service import installed_templates
from app.catalog.store import InstalledStore, get_installed_store
from app.limits import Limits, get_limits
from app.node_templates.catalog import TEMPLATES
from app.node_templates.schemas import NodeTemplateItem, NodeTemplateList
from app.security.policy import outbound_policy
from app.security.ssrf import static_url_problem
from app.settings import Settings, get_settings
from app.workspaces.deps import CurrentMember

router = APIRouter(tags=["node-templates"])


@router.get("/node-templates")
async def list_node_templates(
    limits: Annotated[Limits, Depends(get_limits)],
    settings: Annotated[Settings, Depends(get_settings)],
    installed: Annotated[InstalledStore, Depends(get_installed_store)],
    member: CurrentMember,
    node_type: Literal["http_request"] | None = None,
) -> NodeTemplateList:
    """Lists the ready-made settings for a node, such as an HTTP Request.

    The built-in templates plus the ones installed from the Marketplace. A template this server
    could not run is left out: its node type is turned off, or its URL points at a host the
    server does not allow. Applying one copies its settings into the node; nothing stays linked.
    """
    policy = outbound_policy(settings, limits)
    found = [NodeTemplateItem(source="builtin", template=t) for t in TEMPLATES] + [
        NodeTemplateItem(source="installed", template=t)
        for t in await installed_templates(installed, member)
    ]
    items = [
        item
        for item in found
        if (node_type is None or item.template.node_type == node_type)
        and item.template.node_type not in limits.disabled_node_types
        and static_url_problem(item.template.data.url, policy) is None
    ]
    return NodeTemplateList(items=items)
