"""HTTP only: lists the built-in templates. Logic lives in service.py."""

from fastapi import APIRouter

from app.templates import service
from app.templates.schemas import TemplateList

router = APIRouter(tags=["templates"])


@router.get("/templates")
async def list_templates() -> TemplateList:
    return TemplateList(items=list(service.load_templates()))
