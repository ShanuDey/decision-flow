"""Persistence for installed items. Tests swap this class for an in-memory fake."""

from collections.abc import Sequence
from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.models import InstalledItem
from app.db import get_session
from app.engine.base import FrozenBaseModel
from app.workspaces.schemas import Member


class ItemDraft(FrozenBaseModel):
    kind: str
    item_id: str
    version: str
    hash: str
    definition: dict[str, Any]


class InstalledStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_items(self, member: Member, kind: str | None = None) -> list[InstalledItem]:
        query = select(InstalledItem).where(InstalledItem.workspace_id == member.workspace_id)
        if kind is not None:
            query = query.where(InstalledItem.kind == kind)
        rows = await self.session.scalars(query.order_by(InstalledItem.kind, InstalledItem.item_id))
        return list(rows)

    async def get(self, member: Member, kind: str, item_id: str) -> InstalledItem | None:
        return await self.session.scalar(
            select(InstalledItem).where(
                InstalledItem.workspace_id == member.workspace_id,
                InstalledItem.kind == kind,
                InstalledItem.item_id == item_id,
            )
        )

    async def count(self, member: Member) -> int:
        return (
            await self.session.scalar(
                select(func.count())
                .select_from(InstalledItem)
                .where(InstalledItem.workspace_id == member.workspace_id)
            )
            or 0
        )

    async def put(
        self,
        member: Member,
        kind: str,
        item_id: str,
        version: str,
        content_hash: str,
        definition: dict[str, Any],
    ) -> InstalledItem:
        draft = ItemDraft(
            kind=kind,
            item_id=item_id,
            version=version,
            hash=content_hash,
            definition=definition,
        )
        return (await self.put_all(member, [draft]))[0]

    async def put_all(self, member: Member, drafts: Sequence[ItemDraft]) -> list[InstalledItem]:
        """Installs or updates every draft in one transaction: all of them, or none."""
        items: list[InstalledItem] = []
        try:
            for draft in drafts:
                items.append(await self._upsert(member, draft))
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return items

    async def _upsert(self, member: Member, draft: ItemDraft) -> InstalledItem:
        values = {
            "version": draft.version,
            "hash": draft.hash,
            "definition": draft.definition,
            "installed_by": member.user_id,
        }
        statement = (
            insert(InstalledItem)
            .values(
                workspace_id=member.workspace_id,
                kind=draft.kind,
                item_id=draft.item_id,
                **values,
            )
            .on_conflict_do_update(
                index_elements=[
                    InstalledItem.workspace_id,
                    InstalledItem.kind,
                    InstalledItem.item_id,
                ],
                set_={**values, "installed_at": func.now()},
            )
            .returning(InstalledItem)
            .execution_options(populate_existing=True)
        )
        item = await self.session.scalar(statement)
        assert item is not None
        return item

    async def delete(self, member: Member, kind: str, item_id: str) -> bool:
        result = await self.session.execute(
            delete(InstalledItem)
            .where(
                InstalledItem.workspace_id == member.workspace_id,
                InstalledItem.kind == kind,
                InstalledItem.item_id == item_id,
            )
            .returning(InstalledItem.id)
        )
        await self.session.commit()
        return result.first() is not None


def get_installed_store(session: Annotated[AsyncSession, Depends(get_session)]) -> InstalledStore:
    return InstalledStore(session)
